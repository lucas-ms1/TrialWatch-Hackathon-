"""Review workflow checks using temporary synthetic data only."""
from copy import deepcopy
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from reviewdesk.server import APIError, MAX_BODY, ReviewServer, ReviewStore, render_markdown


def fixture():
    source = {"id": "source_1", "title": "Fictional bulletin", "publisher": "Synthetic publisher",
              "url": "https://example.invalid/bulletin", "publication_date": "2026-09-01", "retrieved_at": None,
              "language": "en", "translation_status": "Original synthetic English",
              "access_note": "Fictional fixture", "lineage_note": "No real corroboration"}
    claim = {"id": "claim_1", "text": "The fictional bulletin reports a complaint.", "source_id": "source_1",
             "excerpt": "A complaint names Fictional Reporter A.", "locator": "Paragraph 1",
             "event_date": None, "date_note": "Filing date not stated", "attribution": "Synthetic publisher"}
    candidate = {"id": "candidate_1", "title": "Fictional complaint", "person": "Fictional Reporter A",
                 "proceeding": "Fictional proceeding", "country": "Philippines", "material_type": "synthetic",
                 "as_of": "2026-09-01", "summary": "Fictional source for workflow testing.",
                 "suggested_decision": "uncertain", "review_reasons": ["Synthetic review example"],
                 "unknowns": ["Filing date is unknown"], "sources": [source], "claims": [claim],
                 "related_candidate_ids": [], "notes": ["Fictional; not measured evaluation"]}
    other = deepcopy(candidate)
    other["id"] = "candidate_2"
    return {"schema_version": 1, "dataset": {"id": "synthetic_test", "label": "Synthetic test", "kind": "synthetic", "description": "Testing only"},
            "candidates": [candidate, other]}


def review(**changes):
    value = {"expected_revision": 0, "reviewer": "Synthetic test reviewer", "decision": "include",
             "reason": "The supplied passage supports retaining this fictional candidate for review.",
             "duplicate_of": None, "corrections": [], "included_claim_ids": ["claim_1"]}
    value.update(changes)
    return value


def intake(**changes):
    value = {"title": "Fictional manual entry", "person": "Fictional Reporter B", "country": "Philippines",
             "source_title": "Fictional supplied report", "url": "https://example.invalid/manual", "publisher": "Synthetic publisher",
             "publication_date": "2026-09-01", "source_text": "A fictional complaint was reported. No filing date was supplied.",
             "summary": "The user reports a fictional complaint.", "excerpt": "A fictional complaint was reported.", "locator": "Paragraph 1"}
    value.update(changes)
    return value


class ReviewStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.seed = self.root / "seed.json"
        self.seed.write_text(json.dumps(fixture()), encoding="utf-8")
        self.original_hash = hashlib.sha256(self.seed.read_bytes()).hexdigest()
        self.store = ReviewStore(self.seed, self.root / "state")

    def test_correction_export_and_append_only_history_survive_restart(self):
        correction = {"claim_id": "claim_1", "text": "The fictional source names Reporter A in a complaint; filing date unknown.",
                      "event_date": None, "source_id": "source_1", "excerpt": "A complaint names Fictional Reporter A.", "locator": "Paragraph 1"}
        first = self.store.review("candidate_1", review(corrections=[correction]))
        self.assertEqual(first["revision"], 1)
        self.assertTrue(first["reviewed_at"].endswith("+00:00"))
        restarted = ReviewStore(self.seed, self.root / "state")
        brief = restarted.export("candidate_1")
        self.assertEqual(brief["claims"][0]["text"], correction["text"])
        self.assertIsNone(brief["claims"][0]["event_date"])
        self.assertEqual(brief["claims"][0]["original"]["text"], fixture()["candidates"][0]["claims"][0]["text"])
        self.assertIn("not independently verified", brief["claims"][0]["verification"])
        text = render_markdown(brief)
        self.assertIn("https://example.invalid/bulletin", text)
        self.assertIn("Original statement preserved", text)
        self.assertIn("no whole-card", first["scope"])
        second = restarted.review("candidate_1", review(expected_revision=1, decision="defer", corrections=[correction]))
        self.assertEqual(second["revision"], 2)
        self.assertEqual(restarted.state()["history"]["candidate_1"][0], first)
        self.assertEqual(hashlib.sha256(self.seed.read_bytes()).hexdigest(), self.original_hash)

    def test_revision_conflict_does_not_overwrite_decision(self):
        first = self.store.review("candidate_1", review())
        with self.assertRaises(APIError) as caught:
            ReviewStore(self.seed, self.root / "state").review("candidate_1", review(decision="exclude"))
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.store.state()["reviews"]["candidate_1"], first)
        self.assertEqual(len(self.store.state()["history"]["candidate_1"]), 1)

    def test_selected_claims_and_pending_status_export_honestly(self):
        self.assertEqual(self.store.export("candidate_1")["brief_status"], "pending_draft")
        self.assertIn("Pending draft", render_markdown(self.store.export("candidate_1")))
        self.store.review("candidate_1", review(decision="exclude", included_claim_ids=[]))
        exported = self.store.export("candidate_1")
        self.assertEqual(exported["claims"], [])
        self.assertEqual(exported["sources"], [])
        self.assertEqual(exported["review"]["decision"], "exclude")
        self.assertIn("Current status has not been verified", exported["disclaimer"])

    def test_invalid_review_fields_do_not_create_history(self):
        invalid = [review(reviewer=" "), review(reason=""), review(decision=[]), review(expected_revision=True),
                   review(included_claim_ids=["missing"]), review(included_claim_ids=[]),
                   review(duplicate_of="candidate_2"), review(corrections=[{"claim_id": "claim_1"}])]
        correction = {"claim_id": "claim_1", "text": "Synthetic corrected text", "event_date": "2026-02-30",
                      "source_id": "source_1", "excerpt": "Exact text", "locator": "Paragraph 1"}
        invalid.append(review(corrections=[correction]))
        correction = {**correction, "event_date": None, "source_id": "missing"}
        invalid.append(review(corrections=[correction]))
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(APIError):
                self.store.review("candidate_1", payload)
        self.assertEqual(self.store.state()["reviews"], {})

    def test_duplicate_links_keep_evidence_separate_and_prevent_cycles(self):
        for target in ("candidate_1", "missing"):
            with self.assertRaises(APIError):
                self.store.review("candidate_1", review(decision="duplicate", duplicate_of=target))
        self.store.review("candidate_2", review(decision="duplicate", duplicate_of="candidate_1"))
        with self.assertRaises(APIError):
            self.store.review("candidate_1", review(decision="duplicate", duplicate_of="candidate_2"))
        self.assertEqual(len(self.store.state()["candidates"]), 2)
        self.assertEqual(self.store.export("candidate_2")["review"]["duplicate_of"], "candidate_1")

    def test_intake_requires_exact_quote_keeps_date_unknown_and_stores_text_privately(self):
        for payload in (intake(excerpt="Missing sentence"), intake(url="javascript:alert(1)"),
                        intake(url="https://user:secret@example.invalid/"), intake(publication_date="yesterday")):
            with self.assertRaises(APIError):
                self.store.intake(payload)
        candidate = self.store.intake(intake())
        self.assertEqual(candidate["material_type"], "manual_intake")
        self.assertIsNone(candidate["claims"][0]["event_date"])
        self.assertIsNone(candidate["as_of"])
        self.assertIn("not AI extracted", candidate["notes"][0])
        restarted = ReviewStore(self.seed, self.root / "state")
        state = restarted.state()
        self.assertEqual(len(state["candidates"]), 3)
        self.assertNotIn("source_text", json.dumps(state))
        bad_correction = {"claim_id": "claim_1", "text": "Unsupported change", "event_date": None,
                          "source_id": "source_1", "excerpt": "No such quote", "locator": "Paragraph 1"}
        with self.assertRaises(APIError):
            restarted.review(candidate["id"], review(corrections=[bad_correction]))
        self.assertNotIn(candidate["id"], state["reviews"])

    def test_changed_seed_cannot_silently_reuse_review_state(self):
        self.store.review("candidate_1", review())
        changed = fixture()
        changed["candidates"][0]["claims"][0]["text"] = "Different evidence"
        self.seed.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(APIError) as caught:
            ReviewStore(self.seed, self.root / "state")
        self.assertEqual(caught.exception.code, "seed_changed")

    def test_export_escapes_untrusted_markdown_and_html(self):
        self.store.review("candidate_1", review(reason='<script>alert(1)</script> ![tracking](https://bad.invalid/image)'))
        rendered = render_markdown(self.store.export("candidate_1"))
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("![tracking]", rendered)
        self.assertIn("&lt;script&gt;", rendered)


class ReviewHTTPTests(unittest.TestCase):
    # HTTP checks use the same isolated synthetic setup; no real experiment runs.
    def setUp(self):
        ReviewStoreTests.setUp(self)
        static = self.root / "static"
        static.mkdir()
        (static / "index.html").write_text("<!doctype html><title>Fixture</title>", encoding="utf-8")
        self.server = ReviewServer(self.store, port=0, static_dir=static)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, value=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        body = json.dumps(value) if value is not None else None
        headers = {"Content-Type": "application/json", **(headers or {})}
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_http_loopback_review_export_and_security_boundaries(self):
        status, headers, body = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["candidates"]), 2)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("GET", "/api/state", headers={"Host": "attacker.invalid"})[0], 403)
        self.assertEqual(self.request("POST", "/api/reviews/candidate_1", review(), {"Origin": "https://attacker.invalid"})[0], 403)
        self.assertEqual(self.request("POST", "/api/reviews/candidate_1", review(), {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/api/reviews/candidate_1", review(), {"Content-Length": str(MAX_BODY + 1)})[0], 413)
        self.assertEqual(self.request("GET", "/%2e%2e/seed.json")[0], 404)
        self.assertEqual(self.request("GET", "/reviewdesk.sqlite3")[0], 404)
        self.assertEqual(self.request("POST", "/api/reviews/candidate_1", review())[0], 201)
        self.assertEqual(self.request("POST", "/api/reviews/candidate_1", review())[0], 409)
        status, headers, body = self.request("GET", "/api/export/candidate_1?format=json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["review"]["revision"], 1)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(self.request("GET", "/api/export/candidate_1?format=html")[0], 400)

    def test_http_rejects_nonobjects_and_malformed_field_types(self):
        self.assertEqual(self.request("POST", "/api/intake", ["not", "object"])[0], 400)
        self.assertEqual(self.request("POST", "/api/reviews/candidate_1", review(decision={}))[0], 400)
        self.assertEqual(self.store.state()["reviews"], {})


if __name__ == "__main__":
    unittest.main()
