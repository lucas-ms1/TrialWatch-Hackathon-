"""Contract checks for mistakes that could corrupt the human review queue."""

from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_data import load_json, validate_document  # noqa: E402


class CaseContractTests(unittest.TestCase):
    def setUp(self):
        self.document = deepcopy(load_json(ROOT / "examples" / "cases.synthetic.json"))
        self.case = self.document["cases"][0]

    def assert_error(self, fragment):
        errors = validate_document(self.document)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_synthetic_examples_are_valid_and_marked(self):
        self.assertEqual([], validate_document(self.document))
        self.assertTrue(all(case["synthetic"] for case in self.document["cases"]))

    def test_missing_source_provenance_is_rejected(self):
        for field in ("source_id", "url", "publisher", "published_date", "retrieved_at", "language"):
            with self.subTest(field=field):
                altered = deepcopy(self.document)
                del altered["cases"][0]["sources"][0][field]
                self.assertTrue(any(f".{field}: required field missing" in error for error in validate_document(altered)))

    def test_duplicate_case_source_and_claim_ids_are_rejected(self):
        self.document["cases"].append(deepcopy(self.case))
        self.case["sources"].append(deepcopy(self.case["sources"][0]))
        self.case["claims"].append(deepcopy(self.case["claims"][0]))
        for kind in ("case", "source", "claim"):
            self.assert_error(f"duplicate {kind} ID")

    def test_unsupported_claim_is_rejected(self):
        self.case["claims"][0]["evidence"] = []
        self.assert_error("evidence: requires at least 1")

    def test_unresolved_source_reference_is_rejected(self):
        self.case["claims"][0]["evidence"][0]["source_id"] = "missing-source"
        self.assert_error("unknown source")

    def test_impossible_and_ambiguous_dates_are_rejected(self):
        for value in ("2026-02-30", "10/01/2026", "2026-1-1", "unknown"):
            with self.subTest(value=value):
                self.case["claims"][0]["event_date"] = value
                self.assert_error("event_date: invalid date")

    def test_timestamp_requires_timezone_and_real_date(self):
        for value in ("2026-10-06T12:00:00", "2026-02-30T12:00:00Z", "2026-10-06", "2026-10-06T12:00:00+01:99"):
            with self.subTest(value=value):
                self.case["sources"][0]["retrieved_at"] = value
                self.assert_error("retrieved_at: invalid date-time")

    def test_null_unknown_dates_are_valid(self):
        self.case["claims"][0]["event_date"] = None
        self.case["sources"][0]["published_date"] = None
        self.assertEqual([], validate_document(self.document))

    def test_expert_review_queue_requires_human_review_metadata(self):
        self.case["review"]["status"] = "ready_for_expert_review"
        self.assert_error("requires reviewer and reviewed_at")
        self.case["review"].update(reviewer="Synthetic Reviewer", reviewed_at="2026-10-06T13:00:00Z")
        self.assertEqual([], validate_document(self.document))

    def test_numeric_risk_score_is_outside_contract(self):
        self.case["risk_score"] = 0.8
        self.assert_error("risk_score: unexpected field")

    def test_translation_requires_explicit_method_and_language(self):
        evidence = self.case["claims"][0]["evidence"][0]
        evidence["translation"] = {"text": "Synthetic translated excerpt", "reviewer": None}
        self.assert_error("translation.language: required field missing")
        self.assert_error("translation.method: required field missing")
        evidence["translation"].update(language="fr", method="machine")
        self.assertEqual([], validate_document(self.document))

    def test_duplicate_json_keys_do_not_silently_overwrite_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version":"1.0","schema_version":"2.0"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_json(path)


if __name__ == "__main__":
    unittest.main()
