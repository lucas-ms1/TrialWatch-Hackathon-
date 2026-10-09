"""Research handoff import checks use synthetic records and isolated output only."""
import csv
from pathlib import Path
import tempfile
import unittest

from reviewdesk.server import APIError, ReviewStore
from scripts.build_research_seed import FIELDS, ROOT, build_seed, write_seed
from scripts.package_submission import validate_blank_research_template


def record(**changes):
    row = dict.fromkeys(FIELDS, "")
    row.update({
        "dossier_id": "fictional_a", "dossier_title": "Fictional proceedings A", "person": "Fictional Person",
        "proceeding": "Fictional proceeding A; identity supplied by team", "country": "Philippines",
        "dossier_unknowns": "Fictional source coverage is incomplete.",
        "source_id": "report_a", "source_title": "Fictional report", "publisher": "Fictional publisher",
        "url": "https://example.invalid/report-a", "publication_date": "2026-09-02",
        "retrieved_at": "2026-10-08T10:00:00-04:00", "language": "en", "translation_status": "Original English; no translation",
        "access_note": "Synthetic fixture; no source fetched", "lineage_note": "Fictional report; independence unknown",
        "observation_id": "observation_a", "event_id": "fictional_event_1", "summary": "The fictional group reported holding an event.",
        "excerpt": "We held a fictional event.", "locator": "Fictional paragraph 2", "event_date": "2026-09-01",
        "date_note": "Fictional source explicitly supplies date", "attribution": "Fictional group, as quoted by fictional publisher",
        "attribution_type": "reported_activity", "observation_category": "campaign_action", "review_status": "unreviewed",
        "notes": "Fixture only; do not treat as a real event.",
    })
    row.update(changes)
    return row


class ResearchSeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_records(self, rows, header=FIELDS):
        path = self.root / "records.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_multiple_sources_and_observations_join_only_by_explicit_dossier(self):
        rows = [record(), record(observation_id="observation_b", summary="A second fictional observation."),
                record(observation_id="observation_c", source_id="report_b", source_title="Second fictional report",
                       url="https://example.invalid/report-b", publisher="Second fictional publisher"),
                record(dossier_id="fictional_b", dossier_title="Separate fictional proceeding", proceeding="Fictional proceeding B",
                       observation_id="observation_d")]
        seed = build_seed(self.write_records(rows))
        self.assertEqual(len(seed["candidates"]), 2)
        first, second = seed["candidates"]
        self.assertEqual((len(first["sources"]), len(first["claims"])), (2, 3))
        self.assertEqual(first["person"], second["person"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["claims"][2]["source_id"], "report_b")
        self.assertEqual(first["sources"][0]["lineage_note"], rows[0]["lineage_note"])
        self.assertEqual({claim["event_id"] for claim in first["claims"]}, {"fictional_event_1"})
        self.assertIn("repeated reports do not establish additional activity", first["claims"][0]["attribution"])

    def test_import_stays_pending_preserves_ai_check_and_never_saves_classifications(self):
        row = record(review_status="ai_feasibility_only", checked_by="Fictional AI checker", checked_at="2026-10-08T14:00:00Z")
        seed = build_seed(self.write_records([row]))
        path = write_seed(seed, self.root / "seed.json")
        store = ReviewStore(path, self.root / "state")
        self.assertEqual(store.state()["reviews"], {})
        self.assertEqual(store.state()["campaigns"], {})
        claim = store.export("fictional_a")["claims"][0]
        self.assertEqual(claim["record_review"]["status"], "ai_feasibility_only")
        self.assertIn("not human review", claim["attribution"])
        self.assertIn("not independently verified", claim["verification"])
        self.assertEqual(claim["suggested_category"], "campaign_action")
        self.assertNotIn("demo_category", claim)
        self.assertEqual(claim["record_notes"], row["notes"])
        self.assertEqual(seed["dataset"]["kind"], "manual_intake")

    def test_unknown_dates_are_null_and_never_borrow_publication_date(self):
        seed = build_seed(self.write_records([record(event_date="unknown", event_id="unknown", publication_date="2026-09-02", retrieved_at="", date_note="")]))
        candidate = seed["candidates"][0]
        self.assertIsNone(candidate["claims"][0]["event_date"])
        self.assertIsNone(candidate["claims"][0]["event_id"])
        self.assertEqual(candidate["sources"][0]["publication_date"], "2026-09-02")
        self.assertIsNone(candidate["sources"][0]["retrieved_at"])
        self.assertIsNone(candidate["as_of"])
        self.assertIn("publication date is not substituted", candidate["claims"][0]["date_note"])

    def test_bad_ids_urls_dates_timestamps_and_choices_rejected(self):
        for changes in ({"dossier_id": "bad/id"}, {"observation_id": "bad id"}, {"source_id": "<bad>"},
                        {"url": "javascript:alert(1)"}, {"url": "https://user:secret@example.invalid"},
                        {"event_date": "2026-02-30"}, {"event_date": "September 1"},
                        {"publication_date": "2026-09"}, {"retrieved_at": "2026-10-08T14:00:00"},
                        {"retrieved_at": "2026-02-30T14:00:00Z"}, {"attribution_type": "legal_truth"},
                        {"observation_category": "impact"}, {"excerpt": ""}, {"locator": ""}):
            with self.subTest(changes=changes), self.assertRaises(APIError):
                build_seed(self.write_records([record(**changes)]))

    def test_duplicate_observation_ids_and_conflicting_metadata_rejected(self):
        first = record()
        conflicts = [record(), record(dossier_id="different", observation_id="observation_a"),
                     record(observation_id="observation_b", proceeding="Different proceeding"),
                     record(observation_id="observation_b", dossier_unknowns="Different gaps"),
                     record(observation_id="observation_b", url="https://example.invalid/other"),
                     record(observation_id="observation_b", publication_date="2026-09-03")]
        for second in conflicts:
            with self.subTest(second=second), self.assertRaises(APIError):
                build_seed(self.write_records([first, second]))

    def test_check_status_requires_audit_details_without_promoting_to_app_review(self):
        for changes in ({"review_status": "human_checked"}, {"review_status": "ai_feasibility_only", "checked_by": "AI"},
                        {"checked_by": "Human"}, {"checked_at": "2026-10-08T14:00:00Z"},
                        {"review_status": "human_checked", "checked_by": "Human", "checked_at": "2026-10-08"}):
            with self.subTest(changes=changes), self.assertRaises(APIError):
                build_seed(self.write_records([record(**changes)]))
        seed = build_seed(self.write_records([record(review_status="human_checked", checked_by="Fictional checker", checked_at="2026-10-08T14:00:00Z")]))
        self.assertEqual(seed["candidates"][0]["suggested_decision"], "uncertain")
        self.assertIn("not whole-dossier approval", seed["candidates"][0]["claims"][0]["attribution"])

    def test_empty_template_builds_empty_non_synthetic_workspace(self):
        seed = build_seed(ROOT / "examples/research_records.template.csv")
        self.assertEqual(seed["candidates"], [])
        path = write_seed(seed, self.root / "empty.json")
        store = ReviewStore(path, self.root / "empty-state")
        self.assertEqual(store.state()["candidates"], [])
        self.assertEqual(store.state()["dataset"]["kind"], "manual_intake")

    def test_output_refuses_overwrite_and_public_locations(self):
        seed = build_seed(self.write_records([record()]))
        path = write_seed(seed, self.root / "seed.json")
        original = path.read_bytes()
        with self.assertRaises(FileExistsError):
            write_seed({"different": "content"}, path)
        self.assertEqual(path.read_bytes(), original)
        for output in (ROOT / "reviewdesk/new-research.json", ROOT / "examples/new-research.json", self.root / "seed.csv"):
            with self.subTest(output=output), self.assertRaises(APIError):
                write_seed(seed, output)
            self.assertFalse(output.exists())

    def test_csv_headers_and_ragged_rows_rejected(self):
        path = self.root / "bad.csv"
        for text in ("dossier_id,dossier_id\na,a\n", ",".join(FIELDS) + "\na,b\n",
                     ",".join(FIELDS) + "\n" + ",".join(["x"] * (len(FIELDS) + 1)) + "\n"):
            path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(APIError):
                build_seed(path)

    def test_package_rejects_filled_or_malformed_public_template(self):
        path = self.write_records([])
        validate_blank_research_template(path)
        path = self.write_records([record()])
        with self.assertRaisesRegex(ValueError, "contains data rows"):
            validate_blank_research_template(path)
        for text in ("", "dossier_id,summary\n", ",".join(FIELDS) + '\n"unterminated'):
            path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises((ValueError, csv.Error)):
                validate_blank_research_template(path)


if __name__ == "__main__":
    unittest.main()
