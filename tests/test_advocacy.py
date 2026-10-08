"""Evidence-to-advocacy workflow checks; isolated synthetic data, not impact evidence."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from reviewdesk.server import APIError, ReviewServer, ReviewStore, render_advocacy_markdown


def fixture():
    source = {"id": "source_1", "title": "Fictional bulletin", "publisher": "Synthetic publisher",
              "url": "https://example.invalid/fixture", "publication_date": "2026-09-07", "retrieved_at": None,
              "language": "en", "translation_status": "Original synthetic English",
              "access_note": "Fictional fixture only", "lineage_note": "Not independent corroboration"}
    claims = []
    for cid, event_date in (("later", "2026-09-06"), ("undated", None), ("earlier", "2026-09-01"), ("omitted", "2026-08-01")):
        claims.append({"id": cid, "text": "Fictional report: " + cid, "source_id": "source_1",
                       "excerpt": "Fictional source passage: " + cid, "locator": "Paragraph " + cid,
                       "event_date": event_date, "date_note": "Synthetic event date, not publication date",
                       "attribution": "Synthetic source allegation, not a court finding"})
    candidate = {"id": "candidate_1", "title": "Fictional advocacy case", "person": "Fictional Reporter A",
                 "proceeding": "Fictional proceeding", "country": "Philippines", "material_type": "synthetic",
                 "as_of": "2026-09-07", "summary": "Fictional source for software testing.",
                 "suggested_decision": "uncertain", "review_reasons": ["Synthetic review example"],
                 "unknowns": ["Current status remains unknown"], "sources": [source], "claims": claims,
                 "related_candidate_ids": [], "notes": ["Fictional; not measured evaluation"]}
    second_source = {**source, "id": "source_2", "url": "https://example.invalid/correction", "title": "Second fictional bulletin",
                     "language": "fil", "translation_status": "Analyst translation; not independently checked"}
    candidate["sources"].append(second_source)
    return {"schema_version": 1, "dataset": {"id": "advocacy_test", "label": "Synthetic advocacy test", "kind": "synthetic",
                                            "description": "Testing only"}, "candidates": [candidate]}


def review(**changes):
    value = {"expected_revision": 0, "reviewer": "Fictional reviewer", "decision": "include",
             "reason": "Selected statements retained for fictional advocacy planning.", "duplicate_of": None,
             "corrections": [], "included_claim_ids": ["later", "undated", "earlier"]}
    value.update(changes)
    return value


def plan(**changes):
    value = {"expected_revision": 0, "expected_review_revision": 1, "analyst": "Fictional analyst",
             "objective": "Clarify the fictional next hearing date", "audience": "Fictional legal liaison",
             "requested_action": "Consider requesting the public scheduling order", "rationale": "The missing schedule affects preparation.",
             "risks": "Verify identity and avoid attributing unverified allegations as findings.",
             "success_indicator": "A dated order becomes available; this would not prove advocacy caused it.",
             "follow_up_date": "2026-10-10", "additional_gaps": "Next hearing date\nSource independence"}
    value.update(changes)
    return value


def followup(**changes):
    value = {"expected_plan_revision": 1, "author": "Fictional analyst", "kind": "planned_action",
             "event_date": None, "text": "Consider obtaining the fictional order.", "source_url": None, "excerpt": "", "locator": ""}
    value.update(changes)
    return value


class AdvocacyStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.seed = self.root / "seed.json"
        self.seed.write_text(json.dumps(fixture()), encoding="utf-8")
        self.original_hash = hashlib.sha256(self.seed.read_bytes()).hexdigest()
        self.store = ReviewStore(self.seed, self.root / "state")

    def save_plan(self, **changes):
        self.store.review("candidate_1", review())
        return self.store.advocacy("candidate_1", plan(**changes))

    def test_requires_included_review_and_rejects_unknown_candidate(self):
        with self.assertRaises(APIError) as caught:
            self.store.advocacy("candidate_1", plan(expected_review_revision=0))
        self.assertEqual(caught.exception.code, "review_required")
        self.store.review("candidate_1", review(decision="defer"))
        with self.assertRaises(APIError) as caught:
            self.store.advocacy("candidate_1", plan())
        self.assertEqual(caught.exception.code, "review_required")
        for action in (lambda: self.store.advocacy("missing", plan()), lambda: self.store.advocacy_export("missing"),
                       lambda: self.store.followup("missing", followup())):
            with self.assertRaises(APIError) as caught:
                action()
            self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.store.state()["advocacy"], {})

    def test_plan_snapshot_preserves_selected_corrected_evidence_and_survives_restart(self):
        correction = {"claim_id": "earlier", "text": "Fictional corrected statement", "event_date": "2026-08-31",
                      "source_id": "source_2", "excerpt": "The second fictional bulletin gives a corrected date.", "locator": "Paragraph 2"}
        self.store.review("candidate_1", review(corrections=[correction]))
        first = self.store.advocacy("candidate_1", plan())
        restarted = ReviewStore(self.seed, self.root / "state")
        self.assertEqual(restarted.state()["advocacy"]["candidate_1"], first)
        snapshot = first["evidence_snapshot"]
        self.assertNotIn("omitted", [claim["id"] for claim in snapshot["claims"]])
        corrected = next(claim for claim in snapshot["claims"] if claim["id"] == "earlier")
        self.assertEqual(corrected["text"], correction["text"])
        self.assertEqual(corrected["original"]["event_date"], "2026-09-01")
        self.assertEqual({source["id"] for source in snapshot["sources"]}, {"source_1", "source_2"})
        restarted.review("candidate_1", review(expected_revision=1, decision="exclude", included_claim_ids=[]))
        exported = restarted.advocacy_export("candidate_1")
        self.assertTrue(exported["stale_review"])
        self.assertEqual(exported["current_review_decision"], "exclude")
        self.assertEqual(exported["plan"], first)
        self.assertEqual(exported["plan"]["evidence_snapshot"], snapshot)
        self.assertIn("REVIEW CHANGED", render_advocacy_markdown(exported))
        self.assertEqual(hashlib.sha256(self.seed.read_bytes()).hexdigest(), self.original_hash)

    def test_plan_and_review_revision_conflicts_preserve_append_only_history(self):
        first = self.save_plan()
        with self.assertRaises(APIError) as caught:
            self.store.advocacy("candidate_1", plan())
        self.assertEqual(caught.exception.code, "revision_conflict")
        self.store.review("candidate_1", review(expected_revision=1, included_claim_ids=["undated"]))
        with self.assertRaises(APIError) as caught:
            self.store.advocacy("candidate_1", plan(expected_revision=1))
        self.assertEqual(caught.exception.code, "review_revision_conflict")
        second = self.store.advocacy("candidate_1", plan(expected_revision=1, expected_review_revision=2, objective="A revised fictional objective"))
        history = self.store.state()["advocacy_history"]["candidate_1"]
        self.assertEqual(history, [first, second])
        self.assertEqual(len(second["evidence_snapshot"]["claims"]), 1)
        self.assertFalse(self.store.advocacy_export("candidate_1")["stale_review"])

    def test_concurrent_plan_writers_cannot_overwrite_each_other(self):
        self.store.review("candidate_1", review())
        second_store = ReviewStore(self.seed, self.root / "state")
        barrier = threading.Barrier(2)

        def write(store, analyst):
            barrier.wait(timeout=3)
            try:
                return store.advocacy("candidate_1", plan(analyst=analyst))["revision"]
            except APIError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(write, store, name) for store, name in ((self.store, "First analyst"), (second_store, "Second analyst"))]
            results = [job.result(timeout=10) for job in jobs]
        self.assertCountEqual(results, [1, "revision_conflict"])
        self.assertEqual(len(self.store.state()["advocacy_history"]["candidate_1"]), 1)

    def test_invalid_plan_payloads_never_save(self):
        self.store.review("candidate_1", review())
        bad = [plan(analyst=" "), plan(objective=""), plan(rationale=[]), plan(risks="x" * 8001),
               plan(expected_revision=True), plan(expected_review_revision=-1), plan(follow_up_date="2026-02-30"),
               plan(additional_gaps=None), plan(unexpected="value"), []]
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(APIError):
                self.store.advocacy("candidate_1", payload)
        self.assertEqual(self.store.state()["advocacy_history"], {})

    def test_dated_timeline_unknowns_provenance_and_markdown_escaping(self):
        self.save_plan(rationale='<script>alert(1)</script> ![tracking](https://bad.invalid/pixel)', follow_up_date=None)
        brief = self.store.advocacy_export("candidate_1")
        self.assertEqual([claim["id"] for claim in brief["evidence_timeline"]["dated"]], ["earlier", "later"])
        self.assertEqual([claim["id"] for claim in brief["evidence_timeline"]["undated"]], ["undated"])
        self.assertEqual(brief["gaps"]["analyst_identified"], ["Next hearing date", "Source independence"])
        self.assertEqual(brief["material_type"], "synthetic")
        rendered = render_advocacy_markdown(brief)
        self.assertLess(rendered.index("Fictional report: earlier"), rendered.index("Fictional report: later"))
        self.assertLess(rendered.index("## Event date unknown"), rendered.index("Fictional report: undated"))
        self.assertIn("https://example.invalid/fixture", rendered)
        self.assertIn("Exact excerpt:", rendered)
        self.assertIn("Language/translation:", rendered)
        self.assertIn("Chronology does not establish causation", rendered)
        self.assertIn("not source-attributed facts", rendered)
        self.assertIn("Current status remains unknown", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("![tracking]", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_followup_requires_plan_and_evidence_for_completed_or_observed_entries(self):
        with self.assertRaises(APIError) as caught:
            self.store.followup("candidate_1", followup())
        self.assertEqual(caught.exception.code, "plan_required")
        self.save_plan()
        bad = [followup(kind="completed_action"), followup(kind="observed_outcome"),
               followup(kind="observed_outcome", source_url="https://example.invalid/order", excerpt="", locator="p1"),
               followup(kind="completed_action", source_url="https://example.invalid/order", excerpt="Text", locator=""),
               followup(kind=[]), followup(expected_plan_revision=True), followup(event_date="2026-13-01"),
               followup(source_url="javascript:alert(1)"), followup(source_url="https://user:password@example.invalid/")]
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(APIError):
                self.store.followup("candidate_1", payload)
        self.assertEqual(self.store.state()["followups"], {})

    def test_followup_logs_keep_date_roles_revision_and_append_only_records(self):
        self.save_plan()
        first = self.store.followup("candidate_1", followup())
        second = self.store.followup("candidate_1", followup(kind="observed_outcome", event_date="2026-09-12",
                    text="Fictional report states a hearing date became available.", source_url="https://example.invalid/order",
                    excerpt="Fictional hearing listed for 15 October.", locator="Paragraph 1"))
        self.assertIsNone(first["event_date"])
        self.assertEqual(second["event_date"], "2026-09-12")
        self.assertTrue(second["recorded_at"].endswith("+00:00"))
        self.assertIn("not independently verified", second["provenance"])
        self.store.advocacy("candidate_1", plan(expected_revision=1))
        with self.assertRaises(APIError) as caught:
            self.store.followup("candidate_1", followup())
        self.assertEqual(caught.exception.code, "revision_conflict")
        third = self.store.followup("candidate_1", followup(expected_plan_revision=2, text="A second proposed action."))
        restarted = ReviewStore(self.seed, self.root / "state")
        self.assertEqual(restarted.state()["followups"]["candidate_1"], [first, second, third])
        self.assertEqual([entry["sequence"] for entry in restarted.advocacy_export("candidate_1")["followups"]], [1, 2, 3])
        self.assertEqual([entry["plan_revision"] for entry in restarted.advocacy_export("candidate_1")["followups"]], [1, 1, 2])
        rendered = render_advocacy_markdown(restarted.advocacy_export("candidate_1"))
        self.assertIn("observed outcome", rendered)
        self.assertIn("Event date: 2026", rendered)
        self.assertIn("Recorded:", rendered)
        self.assertIn("https://example.invalid/order", rendered)


class AdvocacyHTTPTests(unittest.TestCase):
    def setUp(self):
        AdvocacyStoreTests.setUp(self)
        self.server = ReviewServer(self.store, port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, value=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(method, path, body=json.dumps(value) if value is not None else None,
                               headers={"Content-Type": "application/json", **(headers or {})})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_http_workflow_snapshot_downloads_and_security_boundaries(self):
        self.assertEqual(self.request("GET", "/api/advocacy-export/candidate_1")[0], 409)
        self.assertEqual(self.request("POST", "/api/reviews/candidate_1", review())[0], 201)
        self.assertEqual(self.request("POST", "/api/advocacy/candidate_1", plan(), {"Origin": "https://attacker.invalid"})[0], 403)
        self.assertEqual(self.request("POST", "/api/advocacy/candidate_1", plan())[0], 201)
        self.assertEqual(self.request("POST", "/api/followups/candidate_1", followup(), {"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.request("POST", "/api/followups/candidate_1", followup())[0], 201)
        state = json.loads(self.request("GET", "/api/state")[2])
        self.assertEqual(state["advocacy"]["candidate_1"]["revision"], 1)
        self.assertEqual(len(state["followups"]["candidate_1"]), 1)
        status, headers, body = self.request("GET", "/api/advocacy-export/candidate_1?format=json")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["stale_review"])
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, headers, body = self.request("GET", "/api/advocacy-export/candidate_1?format=md")
        self.assertEqual(status, 200)
        self.assertIn(b"Dated evidence timeline", body)
        self.assertIn("text/markdown", headers["Content-Type"])
        self.assertEqual(self.request("GET", "/api/advocacy-export/candidate_1?format=html")[0], 400)
        self.assertEqual(self.request("POST", "/api/advocacy/candidate_1", ["not an object"])[0], 400)


if __name__ == "__main__":
    unittest.main()
