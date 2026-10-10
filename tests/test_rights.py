"""Rights contract and workflow behavior; these tests do not establish legal accuracy."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from reviewdesk.rights import DIMENSIONS, RUBRIC_VERSION, RUBRIC_V1, blank_dimensions, render_rights_markdown
from reviewdesk.server import APIError, ReviewServer, ReviewStore, markdown_text

ROOT = Path(__file__).resolve().parents[1]


def dimension(document, did="notice_charges"):
    return next(item for item in document["dimensions"] if item["dimension_id"] == did)


class RightsStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.seed = ROOT / "reviewdesk/rights.synthetic.v2.json"
        self.store = ReviewStore(self.seed, self.root / "state")

    def payload(self, cid="rights_demo_1", **changes):
        result = {"expected_revision": 0, "expected_evidence_revision": 0, "rubric_version": RUBRIC_VERSION,
                  "analyst": "Fictional analyst", "preparation": "synthetic_prepared", "dimensions": deepcopy(self.store.rights.prepared[cid])}
        result.update(changes)
        return result

    def review_payload(self, **changes):
        result = {"expected_assessment_revision": 1, "expected_review_revision": 0, "expected_evidence_revision": 0,
                  "reviewer": "Fictional reviewer", "reason": "Review only the notice assessment and both positions, keeping original-document gaps.",
                  "decision": "approve", "dimension_ids": ["notice_charges"], "claim_ids": ["a_notice", "a_minutes", "a_reply"]}
        result.update(changes)
        return result

    def evidence_review(self, **changes):
        result = {"expected_revision": 0, "reviewer": "Fictional evidence reviewer", "decision": "include", "reason": "Selected observation only; no legal decision.", "duplicate_of": None, "corrections": [], "included_claim_ids": ["a_notice"]}
        result.update(changes)
        return result

    def test_missingness_is_distinct_from_zero_and_zero_needs_affirmative_support(self):
        payload = self.payload(dimensions=blank_dimensions())
        saved = self.store.rights.save("rights_demo_1", payload)
        self.assertTrue(all(item["score"] is None for item in saved["dimensions"]))
        self.assertEqual(saved["dimensions"][0]["status"], "not_assessed")
        bad = self.payload(expected_revision=1)
        dimension(bad).update(concern_level="none_documented", support_claim_ids=[])
        with self.assertRaises(APIError):
            self.store.rights.save("rights_demo_1", bad)
        saved_b = self.store.rights.save("rights_demo_2", self.payload("rights_demo_2"))
        self.assertEqual(dimension(saved_b)["score"], 0)
        self.assertEqual(dimension(saved_b, "challenge_evidence")["status"], "insufficient_evidence")
        self.assertIsNone(dimension(saved_b, "challenge_evidence")["score"])
        na = self.payload(expected_revision=1)
        dimension(na).update(status="not_applicable", concern_level=None, explanation="This hypothetical dimension is outside the applicable proceeding scope.", applicability="Explicit scope reason; not a missingness inference.")
        record = self.store.rights.save("rights_demo_1", na)
        self.assertIsNone(dimension(record)["score"])
        self.assertEqual(dimension(record)["status"], "not_applicable")

    def test_duplicate_reports_do_not_automatically_change_concern_or_confidence(self):
        first = self.store.rights.draft("rights_demo_1", self.payload())
        second_payload = self.payload()
        dimension(second_payload)["support_claim_ids"].append("a_repeat")
        second = self.store.rights.draft("rights_demo_1", second_payload)
        self.assertEqual(dimension(first)["score"], dimension(second)["score"])
        self.assertEqual(dimension(first)["confidence"], dimension(second)["confidence"])
        sources = second["evidence_snapshot"]["sources"]
        self.assertIn("same upstream", next(item for item in sources if item["id"] == "a_repeat_report")["lineage_note"])
        self.assertEqual(self.store.rights.state()["history"], {})

    def test_all_support_and_contrary_citations_resolve_even_outside_triage_scope(self):
        self.store.review("rights_demo_1", self.evidence_review())
        saved = self.store.rights.save("rights_demo_1", self.payload(expected_evidence_revision=1))
        claims = {item["id"]: item for item in saved["evidence_snapshot"]["claims"]}
        self.assertIn("a_reply", claims)
        self.assertEqual(saved["evidence_snapshot"]["review"]["included_claim_ids"], ["a_notice"])
        for dim in saved["dimensions"]:
            for cid in dim["support_claim_ids"] + dim["contrary_claim_ids"]:
                self.assertTrue(claims[cid]["excerpt"] and claims[cid]["locator"])
                self.assertIn(claims[cid]["source_id"], {item["id"] for item in saved["evidence_snapshot"]["sources"]})
        rendered = render_rights_markdown(self.store.rights.export("rights_demo_1"))
        self.assertIn("Contrary evidence / competing account", rendered)
        self.assertIn(markdown_text(claims["a_reply"]["excerpt"]), rendered)

    def test_country_context_cannot_change_scores_and_score_adjustment_fields_reject(self):
        original = self.store.rights.draft("rights_demo_1", self.payload())["dimensions"]
        document = json.loads(self.seed.read_text(encoding="utf-8"))
        metadata = document["candidates"][0]["rights_metadata"]
        metadata["country_context"] = [{"label": "Synthetic contextual indicator", "value": "Low contextual value", "year": 2024, "methodology": "Fictional country-year context, no individual legal evidence.", "url": "https://example.invalid/context", "reuse_note": "Synthetic only"}]
        contextual_seed = self.root / "contextual.json"
        contextual_seed.write_text(json.dumps(document), encoding="utf-8")
        other = ReviewStore(contextual_seed, self.root / "context-state")
        self.assertEqual(original, other.rights.draft("rights_demo_1", self.payload())["dimensions"])
        metadata["score_adjustment"] = 2
        contextual_seed.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(APIError):
            ReviewStore(contextual_seed, self.root / "reject-state")

    def test_contract_fails_closed_for_bad_states_citations_versions_and_types(self):
        cases = []
        for key, value in (("status", []), ("concern_level", 0), ("support_claim_ids", ["missing"]), ("support_claim_ids", ["a_notice", "a_notice"]), ("contrary_claim_ids", ["a_notice"]), ("confidence", {}), ("completeness", "perfect"), ("score", 0), ("explanation", " ")):
            payload = self.payload()
            dimension(payload)[key] = value
            cases.append(payload)
        cases.extend([self.payload(rubric_version="unknown"), self.payload(expected_revision=True), self.payload(extra="bad"), self.payload(dimensions=[]), self.payload(preparation={}), []])
        duplicate_dim = self.payload()
        duplicate_dim["dimensions"][1] = deepcopy(duplicate_dim["dimensions"][0])
        cases.append(duplicate_dim)
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(APIError):
                self.store.rights.save("rights_demo_1", payload)
        self.assertEqual(self.store.rights.state()["history"], {})

    def test_correction_stales_assessment_without_rewriting_snapshot_or_approval(self):
        saved = self.store.rights.save("rights_demo_1", self.payload())
        self.store.rights.review("rights_demo_1", self.review_payload())
        correction = {"claim_id": "a_notice", "text": "The defence disputes notice timing; original documents still missing.", "event_date": None, "source_id": "a_report", "excerpt": saved["evidence_snapshot"]["claims"][0]["excerpt"], "locator": "Corrected fictional locator"}
        self.store.review("rights_demo_1", self.evidence_review(corrections=[correction]))
        exported = self.store.rights.export("rights_demo_1")
        self.assertTrue(exported["case_profile"]["stale_evidence"])
        self.assertEqual(exported["case_profile"]["assessment"], saved)
        self.assertEqual(exported["case_profile"]["review_status"], "stale")
        with self.assertRaises(APIError) as caught:
            self.store.rights.review("rights_demo_1", self.review_payload(expected_review_revision=1, expected_evidence_revision=1))
        self.assertEqual(caught.exception.code, "stale_evidence")
        self.assertIn("STALE EVIDENCE", render_rights_markdown(exported))
        second = self.store.rights.save("rights_demo_1", self.payload(expected_revision=1, expected_evidence_revision=1))
        changed = next(item for item in second["evidence_snapshot"]["claims"] if item["id"] == "a_notice")
        self.assertEqual(changed["text"], correction["text"])
        self.assertEqual(changed["original"]["text"], saved["evidence_snapshot"]["claims"][0]["text"])
        self.assertEqual(self.store.rights.state()["case_profiles"]["rights_demo_1"]["dimension_reviews"], {})

    def test_source_changed_correction_is_analyst_proposition_with_original_type_preserved(self):
        original = self.store.rights.save("rights_demo_1", self.payload())
        reply = next(item for item in original["evidence_snapshot"]["claims"] if item["id"] == "a_reply")
        correction = {"claim_id": "a_notice", "text": "Reviewer supplies the government's competing account.", "event_date": None,
                      "source_id": reply["source_id"], "excerpt": reply["excerpt"], "locator": reply["locator"]}
        self.store.review("rights_demo_1", self.evidence_review(corrections=[correction]))
        saved = self.store.rights.save("rights_demo_1", self.payload(expected_revision=1, expected_evidence_revision=1))
        corrected = next(item for item in saved["evidence_snapshot"]["claims"] if item["id"] == "a_notice")
        self.assertEqual(corrected["attribution_kind"], "analyst_proposition")
        self.assertEqual(corrected["source_id"], "a_reply_source")
        self.assertEqual(corrected["original"]["attribution_kind"], "source_allegation")
        self.assertEqual(corrected["original"]["source_id"], "a_report")
        self.assertIn("Human reviewer correction", corrected["attribution"])
        self.assertIn(markdown_text("analyst_proposition"), render_rights_markdown(self.store.rights.export("rights_demo_1")))

    def test_save_reopen_export_preserves_partial_review_exact_scope_and_history(self):
        saved = self.store.rights.save("rights_demo_1", self.payload())
        review = self.store.rights.review("rights_demo_1", self.review_payload())
        restarted = ReviewStore(self.seed, self.root / "state")
        doc = restarted.rights.export("rights_demo_1")
        profile = doc["case_profile"]
        self.assertEqual(profile["assessment"], saved)
        self.assertEqual(profile["review_status"], "partially_approved")
        self.assertEqual(profile["coverage"]["approved_dimensions"], 1)
        self.assertEqual(set(profile["dimension_reviews"]), {"notice_charges"})
        self.assertEqual(doc["rights_review_history"], [review])
        self.assertEqual(profile["current_evidence_review"], None)
        self.assertIn("human review pending", profile["preparation_provenance"][0].lower())
        rendered = render_rights_markdown(doc)
        for expected in ("not an official TrialWatch", "Evidence confidence", "Completeness", "ICCPR", markdown_text("Article 14(3)(a)"), "Exact excerpt", "Next verification", "Alternative", "exact cited observations"):
            # Context JSON uses lower case alternative_explanations.
            self.assertIn(expected.lower(), rendered.lower())

    def test_review_scope_cannot_omit_counterevidence_or_approve_unassessed(self):
        self.store.rights.save("rights_demo_1", self.payload())
        invalid = [self.review_payload(claim_ids=["a_notice", "a_minutes"]), self.review_payload(claim_ids=["a_notice", "a_minutes", "a_reply", "a_repeat"]), self.review_payload(dimension_ids=["missing"]), self.review_payload(dimension_ids=[], claim_ids=[]), self.review_payload(dimension_ids=["presumption_innocence"], claim_ids=[])]
        # Insufficient evidence can be approved as an explicit gap judgment; not_assessed cannot.
        invalid[-1] = self.review_payload(dimension_ids=["expression_scope"], claim_ids=[])
        payload = self.payload(expected_revision=1)
        next(item for item in payload["dimensions"] if item["dimension_id"] == "expression_scope").update(status="not_assessed")
        self.store.rights.save("rights_demo_1", payload)
        invalid = [{**entry, "expected_assessment_revision": 2} for entry in invalid]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(APIError):
                self.store.rights.review("rights_demo_1", payload)
        self.assertEqual(self.store.rights.state()["review_history"], {})

    def test_structured_intake_exact_source_excerpt_and_then_complete_workflow(self):
        payload = json.loads((ROOT / "examples/rights-intake.synthetic.v2.json").read_text(encoding="utf-8"))
        bad = deepcopy(payload)
        bad["source_texts"]["b_record"] = "A different document without the required excerpts."
        with self.assertRaises(APIError):
            self.store.rights.intake(bad)
        candidate = self.store.rights.intake(payload)
        cid = candidate["id"]
        wrong_source = {"claim_id": "b_notice", "source_id": "b_news", "text": "Wrong-source correction", "event_date": None, "excerpt": candidate["claims"][0]["excerpt"], "locator": "Wrong source"}
        with self.assertRaises(APIError):
            self.store.review(cid, self.evidence_review(corrections=[wrong_source], included_claim_ids=["b_notice"]))
        saved = self.store.rights.save(cid, self.payload(dimensions=payload["prepared_mappings"]))
        self.store.rights.review(cid, self.review_payload(dimension_ids=["notice_charges", "legal_assistance"], claim_ids=["b_notice", "b_counsel"]))
        restarted = ReviewStore(self.seed, self.root / "state")
        self.assertEqual(restarted.rights.export(cid)["case_profile"]["assessment"], saved)
        self.assertEqual(restarted.rights.state()["case_profiles"][cid]["coverage"]["approved_dimensions"], 2)
        self.assertNotIn("source_texts", json.dumps(restarted.state()))
        with self.assertRaises(APIError):
            self.store.rights.intake(payload)

    def test_two_writers_cannot_overwrite_revision(self):
        other = ReviewStore(self.seed, self.root / "state")
        barrier = threading.Barrier(2)
        def write(service):
            barrier.wait(timeout=3)
            try:
                return service.save("rights_demo_1", self.payload())["revision"]
            except APIError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(write, service) for service in (self.store.rights, other.rights)]
            self.assertCountEqual([job.result(timeout=10) for job in jobs], [1, "revision_conflict"])

    def test_v2_defines13_fair_trial3_conditional4_expression_without_umbrella_or_detention_score(self):
        expected = {"tribunal_law", "equality_arms", "publicity", "presumption_innocence", "notice_charges", "preparation_facilities", "legal_assistance", "participation", "challenge_evidence", "interpretation", "self_incrimination", "undue_delay", "appeal_review", "juvenile_safeguards", "double_jeopardy", "miscarriage_compensation", "expression_scope", "expression_legal_basis", "expression_legitimate_aim", "expression_necessity"}
        self.assertEqual({item["id"] for item in DIMENSIONS}, expected)
        conditional = [item for item in DIMENSIONS if item["conditional"]]
        self.assertEqual({item["id"] for item in conditional}, {"juvenile_safeguards", "double_jeopardy", "miscarriage_compensation"})
        self.assertEqual(sum(item["group"] == "fair_trial" and not item["conditional"] for item in DIMENSIONS), 13)
        for item in DIMENSIONS:
            self.assertTrue(item["questions"] and item["components"] and item["stage"] and item["exceptions"] and item["jurisdiction"] and item["citations"])
        state = self.store.rights.state()
        self.assertEqual(len(state["blank_dimensions"]), 20)
        self.assertIn("Article 9", state["rubric"]["related_detention_guarantees"][0]["locator"])
        publicity = next(item for item in DIMENSIONS if item["id"] == "publicity")
        self.assertIn("missing web copies", " ".join(publicity["components"]))

    def test_v1_reopen_review_export_keeps_original_definitions_and_upgrade_never_splits_scores(self):
        old_seed = ROOT / "reviewdesk/rights.synthetic.json"
        original_bytes = old_seed.read_bytes()
        original_fixture = json.loads(original_bytes)
        old = ReviewStore(old_seed, self.root / "old-state")
        payload = self.payload("rights_demo_2", rubric_version=RUBRIC_V1["version"], dimensions=deepcopy(old.rights.prepared["rights_demo_2"]))
        first = old.rights.save("rights_demo_2", payload)
        old_review = old.rights.review("rights_demo_2", self.review_payload(dimension_ids=["counsel_preparation"], claim_ids=["b_counsel"]))
        reopened = ReviewStore(old_seed, self.root / "old-state")
        doc = reopened.rights.export("rights_demo_2")
        self.assertEqual(doc["schema_version"], "rights-assessment/1")
        self.assertEqual(doc["rubric"], RUBRIC_V1)
        self.assertEqual(doc["case_profile"]["coverage"]["total_dimensions"], 9)
        self.assertEqual(doc["case_profile"]["assessment"], first)
        self.assertEqual(doc["rights_review_history"], [old_review])
        self.assertEqual(dimension(first, "counsel_preparation")["score"], 0)
        upgrade = doc["case_profile"]["upgrade_dimensions"]
        for did in ("preparation_facilities", "legal_assistance", "tribunal_law", "equality_arms", "publicity", "participation", "interpretation", "self_incrimination", "undue_delay", "appeal_review", "juvenile_safeguards", "double_jeopardy", "miscarriage_compensation"):
            entry = next(item for item in upgrade if item["dimension_id"] == did)
            self.assertEqual(entry["status"], "not_assessed")
            self.assertIsNone(entry["concern_level"])
            self.assertEqual(entry["support_claim_ids"], [])
        second = reopened.rights.save("rights_demo_2", self.payload(expected_revision=1, dimensions=upgrade))
        self.assertEqual(second["schema_version"], "rights-assessment/2")
        state = reopened.rights.state()
        self.assertEqual(state["history"]["rights_demo_2"][0], first)
        self.assertEqual(state["case_profiles"]["rights_demo_2"]["dimension_reviews"], {})
        self.assertEqual(state["case_profiles"]["rights_demo_2"]["coverage"]["total_dimensions"], 20)
        self.assertEqual(state["original_prepared_mappings"], original_fixture["rights_prepared_mappings"])
        self.assertEqual(state["prepared_rubric_versions"]["rights_demo_2"], RUBRIC_V1["version"])
        self.assertEqual(old_seed.read_bytes(), original_bytes)
        self.assertIn("counsel_preparation", {item["id"] for item in reopened.rights.export("rights_demo_2")["rubric_registry"][RUBRIC_V1["version"]]["dimensions"]})

    def test_v2_does_not_accept_v1_dimension_contract_as_a_silent_migration(self):
        old = json.loads((ROOT / "reviewdesk/rights.synthetic.json").read_text(encoding="utf-8"))
        with self.assertRaises(APIError):
            self.store.rights.save("rights_demo_1", self.payload(dimensions=old["rights_prepared_mappings"]["rights_demo_1"]))
        self.assertEqual(self.store.rights.state()["history"], {})

    def test_untrusted_text_is_escaped_in_markdown_export(self):
        payload = self.payload()
        dimension(payload)["explanation"] = '<script>alert(1)</script> ![track](https://bad.invalid/pixel)'
        self.store.rights.save("rights_demo_1", payload)
        rendered = render_rights_markdown(self.store.rights.export("rights_demo_1"))
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("![track]", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        intake = json.loads((ROOT / "examples/rights-intake.synthetic.v2.json").read_text(encoding="utf-8"))
        intake["candidate"]["sources"][0]["url"] = "https://example.invalid/a)![pixel](https://evil.invalid/pixel"
        candidate = self.store.rights.intake(intake)
        self.store.rights.save(candidate["id"], self.payload(dimensions=intake["prepared_mappings"]))
        safe_export = render_rights_markdown(self.store.rights.export(candidate["id"]))
        self.assertNotIn(")![pixel](", safe_export)
        self.assertIn("%29", safe_export)


class RightsHTTPTests(unittest.TestCase):
    payload = RightsStoreTests.payload
    review_payload = RightsStoreTests.review_payload

    def setUp(self):
        RightsStoreTests.setUp(self)
        self.server = ReviewServer(self.store, port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, value=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(method, path, body=json.dumps(value) if value is not None else None, headers={"Content-Type": "application/json", **(headers or {})})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_http_complete_walkthrough_draft_save_review_index_export_and_security(self):
        state = json.loads(self.request("GET", "/api/rights/state")[2])
        self.assertEqual(len(state["candidates"]), 3)
        self.assertEqual(len(json.loads(self.request("GET", "/api/rights/rubric")[2])["dimensions"]), len(DIMENSIONS))
        self.assertEqual(self.request("POST", "/api/rights/draft/rights_demo_1", self.payload())[0], 200)
        self.assertEqual(self.store.rights.state()["history"], {})
        self.assertEqual(self.request("POST", "/api/rights/assessments/rights_demo_1", self.payload(), {"Origin": "https://attacker.invalid"})[0], 403)
        self.assertEqual(self.request("POST", "/api/rights/assessments/rights_demo_1", self.payload())[0], 201)
        self.assertEqual(self.request("POST", "/api/rights/reviews/rights_demo_1", self.review_payload())[0], 201)
        current = json.loads(self.request("GET", "/api/rights/state")[2])
        self.assertEqual(current["rights"]["case_profiles"]["rights_demo_1"]["review_status"], "partially_approved")
        for format_name in ("json", "md"):
            status, headers, body = self.request("GET", "/api/rights/export/rights_demo_1?format=" + format_name)
            self.assertEqual(status, 200)
            self.assertIn("attachment", headers["Content-Disposition"])
            self.assertIn(b"a_reply", body)
        self.assertEqual(self.request("GET", "/api/rights/export/rights_demo_1?format=html")[0], 400)
        self.assertEqual(self.request("POST", "/api/rights/assessments/rights_demo_1", [])[0], 400)

    def test_malformed_structured_intake_returns_json400_without_any_saved_state(self):
        template = json.loads((ROOT / "examples/rights-intake.synthetic.v2.json").read_text(encoding="utf-8"))
        invalid = []
        for field in ("material_type", "suggested_decision", "source_id"):
            for value in ([], {}, None, 7):
                payload = deepcopy(template)
                target = payload["candidate"]["claims"][0] if field == "source_id" else payload["candidate"]
                target[field] = value
                invalid.append(payload)
        for field in ("candidate", "source_texts", "prepared_mappings"):
            payload = deepcopy(template)
            payload[field] = []
            invalid.append(payload)
        invalid.extend([[], {}, ["wrong top-level type"]])
        for payload in invalid:
            with self.subTest(payload=payload):
                status, headers, body = self.request("POST", "/api/rights/intake", payload)
                self.assertEqual(status, 400)
                self.assertIn("application/json", headers["Content-Type"])
                self.assertEqual(json.loads(body)["code"], "invalid_request")
        self.assertEqual(len(self.store.state()["candidates"]), 3)
        self.assertEqual(self.store.state()["history"], {})
        self.assertEqual(self.store.rights.state()["history"], {})
        with self.store.connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM intakes").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM rights_source_texts").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM rights_preparations").fetchone()[0], 0)
        self.assertEqual(self.request("GET", "/api/health")[0], 200)


if __name__ == "__main__":
    unittest.main()
