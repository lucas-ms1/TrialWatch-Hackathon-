"""Campaign comparisons tested with isolated synthetic fixtures, never impact claims."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from reviewdesk.server import APIError, CAMPAIGN_CATEGORIES, ReviewServer, ReviewStore, render_campaign_markdown
from test_advocacy import fixture, review


def analysis(**changes):
    payload = {"expected_revision": 0, "expected_review_revision": 1, "analyst": "Fictional campaign analyst",
               "campaign_label": "Fictional campaign A", "objective": "Compare reported attention and proceedings",
               "interpretation": "The selected reports document attention and a later legal change; association is not causation.",
               "alternative_explanations": "Legal merits and other interventions may explain the reported change.",
               "limitations": "Convenience sample with incomplete campaign and outcome reporting.",
               "codings": [{"claim_id": "later", "category": "legal_outcome"},
                           {"claim_id": "earlier", "category": "social_media"},
                           {"claim_id": "undated", "category": "context"}]}
    payload.update(changes)
    return payload


class CampaignStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.seed = self.root / "seed.json"
        seed = fixture()
        second = deepcopy(seed["candidates"][0])
        second["id"] = "candidate_2"
        second["title"] = "Second fictional dossier; same underlying sources"
        seed["candidates"].append(second)
        self.seed.write_text(json.dumps(seed), encoding="utf-8")
        self.original_hash = hashlib.sha256(self.seed.read_bytes()).hexdigest()
        self.store = ReviewStore(self.seed, self.root / "state")

    def save_analysis(self, cid="candidate_1", **changes):
        self.store.review(cid, review())
        return self.store.campaign(cid, analysis(**changes))

    def test_empty_comparison_and_missing_included_review_rejected(self):
        with self.assertRaises(APIError) as caught:
            self.store.campaign_export()
        self.assertEqual(caught.exception.code, "campaign_required")
        with self.assertRaises(APIError) as caught:
            self.store.campaign("candidate_1", analysis(expected_review_revision=0))
        self.assertEqual(caught.exception.code, "review_required")
        self.store.review("candidate_1", review(decision="defer"))
        with self.assertRaises(APIError) as caught:
            self.store.campaign("candidate_1", analysis())
        self.assertEqual(caught.exception.code, "review_required")
        with self.assertRaises(APIError) as caught:
            self.store.campaign("missing", analysis())
        self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.store.state()["campaigns"], {})

    def test_every_selected_claim_coded_exactly_once_and_categories_are_bounded(self):
        self.store.review("candidate_1", review())
        good = analysis()["codings"]
        invalid = [[], good[:2], good + [good[0]], good + [{"claim_id": "omitted", "category": "context"}],
                   good + [{"claim_id": "missing", "category": "context"}],
                   [{**entry, "category": "causal_impact"} for entry in good],
                   [{**entry, "category": []} for entry in good],
                   [{**entry, "source_id": "source_1"} for entry in good],
                   [{"claim_id": [], "category": "context"}], {"claim_id": "later"}]
        for codings in invalid:
            with self.subTest(codings=codings), self.assertRaises(APIError):
                self.store.campaign("candidate_1", analysis(codings=codings))
        self.assertEqual(self.store.state()["campaign_history"], {})
        saved = self.store.campaign("candidate_1", analysis())
        self.assertEqual(saved["codings"], good)
        self.assertIn("Analyst-coded", saved["coding_method"])

    def test_required_text_and_revision_types_validated_without_save(self):
        self.store.review("candidate_1", review())
        invalid = [analysis(analyst=" "), analysis(campaign_label=""), analysis(interpretation=[]),
                   analysis(alternative_explanations=""), analysis(limitations="x" * 8001),
                   analysis(expected_revision=True), analysis(expected_review_revision=-1),
                   analysis(extra="not allowed"), []]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(APIError):
                self.store.campaign("candidate_1", payload)
        self.assertEqual(self.store.state()["campaigns"], {})

    def test_saved_snapshot_corrections_and_originals_survive_review_change_restart(self):
        correction = {"claim_id": "later", "text": "Corrected fictional outcome with limited support.",
                      "event_date": None, "source_id": "source_2", "excerpt": "A second fictional source reports a change.", "locator": "Paragraph 2"}
        self.store.review("candidate_1", review(corrections=[correction]))
        saved = self.store.campaign("candidate_1", analysis())
        self.store.review("candidate_1", review(expected_revision=1, decision="exclude", included_claim_ids=[]))
        restarted = ReviewStore(self.seed, self.root / "state")
        exported = restarted.campaign_export()["campaigns"][0]
        self.assertTrue(exported["stale_review"])
        self.assertTrue(exported["review_no_longer_included"])
        self.assertEqual(exported["current_review_decision"], "exclude")
        self.assertEqual(exported["analysis"], saved)
        outcome = exported["timelines"]["legal_outcome"]["undated"][0]
        self.assertEqual(outcome["text"], correction["text"])
        self.assertEqual(outcome["original"]["event_date"], "2026-09-06")
        self.assertEqual(outcome["source"]["language"], "fil")
        self.assertEqual(exported["unique_source_count"], 2)
        rendered = render_campaign_markdown(restarted.campaign_export())
        self.assertIn("REVIEW CHANGED", rendered)
        self.assertIn("| Fictional campaign A **[REVIEW CHANGED]** |", rendered)
        self.assertLess(rendered.index("REVIEW CHANGED"), rendered.index("## Comparison of documented evidence"))
        self.assertIn("Original statement preserved", rendered)
        self.assertIn("Original language/translation", rendered)
        self.assertEqual(hashlib.sha256(self.seed.read_bytes()).hexdigest(), self.original_hash)

    def test_revision_guards_and_resave_preserve_history_while_export_uses_latest(self):
        first = self.save_analysis()
        with self.assertRaises(APIError) as caught:
            self.store.campaign("candidate_1", analysis())
        self.assertEqual(caught.exception.code, "revision_conflict")
        self.store.review("candidate_1", review(expected_revision=1, included_claim_ids=["undated"]))
        with self.assertRaises(APIError) as caught:
            self.store.campaign("candidate_1", analysis(expected_revision=1))
        self.assertEqual(caught.exception.code, "review_revision_conflict")
        second = self.store.campaign("candidate_1", analysis(expected_revision=1, expected_review_revision=2,
                     campaign_label="Revised campaign", codings=[{"claim_id": "undated", "category": "context"}]))
        self.assertEqual(self.store.state()["campaign_history"]["candidate_1"], [first, second])
        comparison = self.store.campaign_export()
        self.assertEqual(comparison["summary"]["campaign_dossiers"], 1)
        self.assertEqual(comparison["campaigns"][0]["analysis"], second)
        self.assertFalse(comparison["campaigns"][0]["stale_review"])
        self.assertIsNone(comparison["campaigns"][0]["known_event_range"])

    def test_concurrent_writers_protect_campaign_revision(self):
        self.store.review("candidate_1", review())
        second_store = ReviewStore(self.seed, self.root / "state")
        barrier = threading.Barrier(2)

        def write(store, name):
            barrier.wait(timeout=3)
            try:
                return store.campaign("candidate_1", analysis(analyst=name))["revision"]
            except APIError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(write, store, name) for store, name in ((self.store, "Analyst A"), (second_store, "Analyst B"))]
            result = [job.result(timeout=10) for job in jobs]
        self.assertCountEqual(result, [1, "revision_conflict"])
        self.assertEqual(len(self.store.state()["campaign_history"]["candidate_1"]), 1)

    def test_comparison_counts_observations_and_distinct_urls_not_cases_or_reach(self):
        self.save_analysis()
        self.save_analysis("candidate_2", campaign_label="Fictional campaign B")
        comparison = self.store.campaign_export()
        self.assertEqual(comparison["summary"], {"campaign_dossiers": 2, "coded_observations": 6, "unique_cited_sources": 1})
        self.assertEqual([item["unique_source_count"] for item in comparison["campaigns"]], [1, 1])
        self.assertIn("not automatically distinct cases", comparison["comparison_scope"])
        self.assertIn("neither is a reach or impact measure", comparison["counting_method"])
        for item in comparison["campaigns"]:
            self.assertEqual(item["category_summary"]["legal_outcome"]["status"], "documented_in_selected_evidence")
            self.assertEqual(item["category_summary"]["policy_outcome"]["status"], "not_documented_in_selected_evidence")
            self.assertIn("Unknown", item["outcomes"]["policy_outcome"]["meaning"])
            self.assertIn("not proof of campaign effect", item["outcomes"]["legal_outcome"]["meaning"])
            self.assertEqual(set(item["timelines"]), set(CAMPAIGN_CATEGORIES))
        self.assertNotIn("impact_score", json.dumps(comparison))

    def test_category_timelines_preserve_unknowns_and_publication_dates(self):
        codings = [{"claim_id": cid, "category": "campaign_action"} for cid in ("later", "undated", "earlier")]
        self.save_analysis(codings=codings)
        item = self.store.campaign_export()["campaigns"][0]
        timeline = item["timelines"]["campaign_action"]
        self.assertEqual([claim["id"] for claim in timeline["dated"]], ["earlier", "later"])
        self.assertEqual([claim["id"] for claim in timeline["undated"]], ["undated"])
        self.assertEqual(item["known_event_range"], {"start": "2026-09-01", "end": "2026-09-06"})
        self.assertEqual(item["unknown_event_dates"], 1)
        self.assertEqual(timeline["undated"][0]["source"]["publication_date"], "2026-09-07")
        self.assertIsNone(timeline["undated"][0]["event_date"])

    def test_memo_keeps_interpretation_separate_and_escapes_untrusted_text(self):
        self.save_analysis(interpretation='<script>alert(1)</script> ![tracking](https://bad.invalid/pixel)')
        rendered = render_campaign_markdown(self.store.campaign_export())
        for expected in ("## Comparison of documented evidence", "Analyst judgments", "not source-attributed facts",
                         "Alternative explanations", "Convenience sample", "Confounding", "not an effectiveness ranking",
                         "Exact excerpt:", "Source limits:", "Published:", "Current case status remains unverified",
                         "https://example.invalid/fixture", "Material: synthetic", "Unknown", "Policy development evidence",
                         "does not establish adopted policy by default"):
            self.assertIn(expected, rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("![tracking]", rendered)
        self.assertIn("&lt;script&gt;", rendered)


class CampaignHTTPTests(unittest.TestCase):
    def setUp(self):
        CampaignStoreTests.setUp(self)
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

    def test_http_campaign_save_and_export_keep_local_security(self):
        self.assertEqual(self.request("GET", "/api/campaign-export?format=json")[0], 409)
        self.assertEqual(self.request("POST", "/api/reviews/candidate_1", review())[0], 201)
        self.assertEqual(self.request("POST", "/api/campaigns/candidate_1", analysis(), {"Origin": "https://attacker.invalid"})[0], 403)
        self.assertEqual(self.request("POST", "/api/campaigns/candidate_1", analysis())[0], 201)
        self.assertEqual(self.request("POST", "/api/campaigns/candidate_1", analysis())[0], 409)
        state = json.loads(self.request("GET", "/api/state")[2])
        self.assertEqual(state["campaigns"]["candidate_1"]["revision"], 1)
        self.assertEqual(len(state["campaign_history"]["candidate_1"]), 1)
        status, headers, body = self.request("GET", "/api/campaign-export?format=json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["summary"]["campaign_dossiers"], 1)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("attachment", headers["Content-Disposition"])
        status, headers, body = self.request("GET", "/api/campaign-export?format=md")
        self.assertEqual(status, 200)
        self.assertIn(b"Campaign evidence comparison", body)
        self.assertIn("text/markdown", headers["Content-Type"])
        self.assertEqual(self.request("GET", "/api/campaign-export?format=html")[0], 400)
        self.assertEqual(self.request("POST", "/api/campaigns/candidate_1", [])[0], 400)


if __name__ == "__main__":
    unittest.main()
