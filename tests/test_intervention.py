"""Connected worksheet mechanics; tests do not measure legal accuracy or impact."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from reviewdesk.server import APIError, ReviewStore, markdown_text
from reviewdesk.rights import RUBRIC_VERSION, blank_dimensions
from reviewdesk.intervention import InterventionService, render_intervention_markdown

ROOT = Path(__file__).resolve().parents[1]
CID = "rights_demo_1"


class InterventionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.seed = ROOT / "reviewdesk/rights.synthetic.v2.json"
        self.store = ReviewStore(self.seed, Path(self.tmp.name) / "state")
        self.service = getattr(self.store, "interventions", None) or InterventionService(self.store)
        self.example = json.loads((ROOT / "examples/intervention.synthetic.json").read_text(encoding="utf-8"))
        self.store.rights.save(CID, self.assessment())
        self.service.context(CID, deepcopy(self.example["context"]))

    def assessment(self, **changes):
        payload = {"expected_revision": 0, "expected_evidence_revision": 0, "rubric_version": RUBRIC_VERSION, "analyst": "Fictional analyst", "preparation": "synthetic_prepared", "dimensions": deepcopy(self.store.rights.prepared[CID])}
        payload.update(changes)
        return payload

    def proposal(self, **changes):
        p = deepcopy(self.example["proposal"])
        p.update(changes)
        return p

    def review(self, record, **changes):
        p = {"expected_review_revision": 0, "reviewer": "Synthetic demonstration reviewer", "decision": "accept", "reason": "Inspect only this provisional worksheet, exact notice dimension and cited context/alternatives; no real human legal validation.", "dimension_ids": record["review_scope"]["dimension_ids"], "context_claim_ids": record["review_scope"]["context_claim_ids"], "revised_disposition": None, "revision_note": ""}
        p.update(changes)
        return p

    def test_complete_scoped_review_reopen_and_cited_export(self):
        r = self.service.propose(CID, self.proposal())
        self.assertEqual(r["disposition"], "prepare_verify")
        self.assertEqual(r["rights_scope_status"], "pending_human_review")
        review = self.service.review(r["id"], self.review(r))
        self.service.followup(r["id"], deepcopy(self.example["followup"]))
        reopened = ReviewStore(self.seed, Path(self.tmp.name) / "state")
        service = getattr(reopened, "interventions", None) or InterventionService(reopened)
        exported = service.export(r["id"])
        self.assertEqual(exported["recommendation"]["review_status"], "accept")
        self.assertEqual(exported["recommendation"]["reviews"], [review])
        self.assertEqual(exported["recommendation"]["dependencies"], r["dependencies"])
        text = render_intervention_markdown(exported)
        for value in ("Full saved legal profiles", "ICCPR", "Exact excerpt", "Conditional scenario", "prior_outcome", "contrary", "deferral", "Synthetic demonstration reviewer", "no causal"):
            self.assertTrue(value.lower() in text.lower() or markdown_text(value).lower() in text.lower(), value)
        self.assertNotIn("source_texts", json.dumps(exported))
        for claim_id in r["review_scope"]["context_claim_ids"]:
            self.assertIn('<a id="context-' + claim_id + '"></a>', text)

    def test_six_dispositions_and_human_four_decisions_are_distinct(self):
        # Prepared worksheet supports explicit verification, deferral and against;
        # immediate/referral gates are additionally exercised below.
        for request, selected in (("prepare_verify", "verify_records"), ("defer", "defer_public"), ("against", "verify_records"), ("insufficient_basis", "verify_records")):
            current = len(self.service.state(CID)["recommendations"])
            r = self.service.propose(CID, self.proposal(expected_revision=current, requested_disposition=request, selected_option_id=selected))
            self.assertEqual(r["disposition"], request)
        r = self.service.state(CID)["latest"]
        for index, decision in enumerate(("accept", "revise", "reject", "defer")):
            change = {"expected_review_revision": index, "decision": decision}
            if decision == "revise":
                change.update(revised_disposition="prepare_verify", revision_note="Human-limited verification supersedes the abstention proposal; original remains.")
            review = self.service.review(r["id"], self.review(r, **change))
            self.assertEqual(review["decision"], decision)
        self.assertEqual(len(self.service.export(r["id"])["recommendation"]["reviews"]), 4)

    def test_immediate_and_referral_require_separate_evidenced_prerequisites(self):
        p = self.proposal(requested_disposition="intervene_now")
        r = self.service.propose(CID, p)
        self.assertEqual(r["disposition"], "prepare_verify")
        self.assertTrue(any("preferences" in x.lower() for x in r["rule_reasons"]))
        context = deepcopy(self.example["context"])
        context["expected_revision"] = 1
        changed = {"harm": "The fictional note records an agreed confidentiality plan addressing the identified exposure risk.", "preferences": "The fictional defendant requests limited legal research support through authorized counsel."}
        for c in context["claims"]:
            if c["id"] in changed:
                c["text"] = c["excerpt"] = changed[c["id"]]
        context["source_texts"]["context_record"] = "\n\n".join(c["excerpt"] for c in context["claims"])
        self.service.context(CID, context)
        p = self.proposal(expected_revision=1, expected_context_revision=2, requested_disposition="intervene_now")
        o = p["options"][0]
        o["route"] = "legal_support"
        o["blocking_unknowns"] = []
        o["factors"].update(feasibility="feasible", harm="mitigated", preferences="requested")
        r = self.service.propose(CID, p)
        self.assertEqual(r["disposition"], "intervene_now")
        p.update(expected_revision=2, requested_disposition="refer_coordinate")
        o["route"] = "partner_coordination"
        r = self.service.propose(CID, p)
        self.assertEqual(r["disposition"], "refer_coordinate")
        self.assertEqual(r["legal_concern"][0]["score"], 2)

    def test_party_deadline_duplicate_reporting_cannot_create_opportunity(self):
        context = deepcopy(self.example["context"])
        context["expected_revision"] = 1
        context["claims"][0]["topic"] = "party_label"
        context["claims"].append({**deepcopy(context["claims"][0]), "id": "repeated_party"})
        self.service.context(CID, context)
        p = self.proposal(expected_context_revision=2, requested_disposition="intervene_now")
        o = p["options"][0]
        o["support_context_ids"] = ["route", "repeated_party", "window"]
        o["authority_context_ids"] = ["route"]
        o["route"] = "legal_support"
        o["blocking_unknowns"] = []
        o["factors"].update(feasibility="feasible", harm="mitigated", preferences="requested")
        r = self.service.propose(CID, p)
        self.assertNotEqual(r["disposition"], "intervene_now")
        self.assertTrue(any("party labels" in x for x in r["rule_reasons"]))
        self.assertIn("reply", r["options"][0]["contrary_context_ids"])

    def test_missingness_is_abstention_not_confident_negative_or_action(self):
        self.store.rights.save(CID, self.assessment(expected_revision=1, dimensions=blank_dimensions()))
        context = deepcopy(self.example["context"])
        context.update(expected_revision=1, sources=[], source_texts={}, claims=[], comparables=[])
        self.service.context(CID, context)
        p = self.proposal(expected_context_revision=2, expected_assessment_revision=2, requested_disposition="intervene_now")
        for option in p["options"]:
            for key in tuple(option):
                if key.endswith("_context_ids"):
                    option[key] = []
            option["factors"].update(urgency="unknown", opportunity="unknown", feasibility="unknown", harm="unknown", preferences="unknown")
        r = self.service.propose(CID, p)
        self.assertEqual(r["disposition"], "insufficient_basis")
        p.update(expected_revision=1, requested_disposition="against")
        self.assertEqual(self.service.propose(CID, p)["disposition"], "insufficient_basis")
        p.update(expected_revision=2, requested_disposition="prepare_verify")
        self.assertEqual(self.service.propose(CID, p)["disposition"], "insufficient_basis")

    def test_context_citations_fail_closed_and_scoped_review_retains_contrary(self):
        bad = deepcopy(self.example["context"])
        bad["expected_revision"] = 1
        bad["source_texts"]["context_record"] = "different supplied source"
        with self.assertRaises(APIError):
            self.service.context(CID, bad)
        bad = deepcopy(self.example["context"])
        bad["expected_revision"] = 1
        bad["sources"][0]["publication_date"] = "2026-10-10"
        with self.assertRaises(APIError):
            self.service.context(CID, bad)
        p = self.proposal()
        p["options"][0]["support_context_ids"] = ["missing"]
        with self.assertRaises(APIError):
            self.service.propose(CID, p)
        r = self.service.propose(CID, self.proposal())
        scope = [x for x in r["review_scope"]["context_claim_ids"] if x != "reply"]
        with self.assertRaises(APIError):
            self.service.review(r["id"], self.review(r, context_claim_ids=scope))
        self.assertIn("reply", r["review_scope"]["context_claim_ids"])

    def test_context_evidence_and_reassessment_stale_old_decisions(self):
        r = self.service.propose(CID, self.proposal())
        self.service.review(r["id"], self.review(r))
        context = deepcopy(self.example["context"])
        context.update(expected_revision=1, unknowns=["Material context revision: confirm capacity again."])
        self.service.context(CID, context)
        self.assertTrue(self.service.export(r["id"])["recommendation"]["stale"])
        with self.assertRaises(APIError):
            self.service.review(r["id"], self.review(r, expected_review_revision=1))
        r2 = self.service.propose(CID, self.proposal(expected_revision=1, expected_context_revision=2))
        original = self.store.originals[CID]["claims"][0]
        correction = {"claim_id": original["id"], "source_id": original["source_id"], "text": "Fictional corrected wording; support still unresolved.", "excerpt": original["excerpt"], "locator": original["locator"], "event_date": None}
        self.store.review(CID, {"expected_revision": 0, "reviewer": "Synthetic correction reviewer", "decision": "defer", "reason": "Fictional correction makes dependent recommendation stale.", "duplicate_of": None, "corrections": [correction], "included_claim_ids": []})
        self.assertTrue(self.service.export(r2["id"])["recommendation"]["stale"])
        self.store.rights.save(CID, self.assessment(expected_revision=1, expected_evidence_revision=1))
        r3 = self.service.propose(CID, self.proposal(expected_revision=2, expected_context_revision=2, expected_assessment_revision=2))
        self.assertEqual(r3["review_status"], "pending_human_review")
        self.assertEqual(r3["reviews"], [])
        self.store.rights.save(CID, self.assessment(expected_revision=2, expected_evidence_revision=1))
        self.assertTrue(self.service.export(r3["id"])["recommendation"]["stale"])
        self.assertEqual(self.service.export(r["id"])["recommendation"]["context_snapshot"]["revision"], 1)

    def test_cluster_membership_exact_scope_and_linked_case_dependencies(self):
        context = deepcopy(self.example["context"])
        context["expected_revision"] = 1
        context["cluster"] = {"candidate_ids": [CID, "rights_demo_2"], "memberships": [{"candidate_id": cid, "basis": "Fictional notice-document issue only.", "material_differences": "Different fictional defendant, tribunal and records.", "identity_uncertainty": "Distinct fixture IDs; no merged identity or arrest event."} for cid in (CID, "rights_demo_2")], "reviewer": "Synthetic cluster reviewer", "reason": "Review links only; no movement or factual authentication.", "reviewed_context_ids": ["route"]}
        self.service.context(CID, context)
        r = self.service.propose(CID, self.proposal(expected_context_revision=2))
        self.assertIsNone(r["rights_snapshots"]["rights_demo_2"]["case_profile"]["assessment"])
        self.store.rights.save("rights_demo_2", {**self.assessment(), "dimensions": deepcopy(self.store.rights.prepared["rights_demo_2"])})
        self.assertTrue(self.service.export(r["id"])["recommendation"]["stale"])

    def test_observed_outcome_requires_source_scenarios_remain_distinct(self):
        r = self.service.propose(CID, self.proposal())
        f = deepcopy(self.example["followup"])
        f["kind"] = "observed_outcome"
        with self.assertRaises(APIError):
            self.service.followup(r["id"], f)
        f.update(source=deepcopy(self.example["context"]["sources"][0]), source_text="A fictional court granted preparation time.", excerpt="A fictional court granted preparation time.", locator="Fictional followup paragraph", text="The fictional source reports more preparation time.", contribution="Chronology only; no causal contribution established.")
        observed = self.service.followup(r["id"], f)
        scenario = self.service.followup(r["id"], {**deepcopy(self.example["followup"]), "expected_sequence": 1})
        self.assertEqual(observed["kind"], "observed_outcome")
        self.assertEqual(scenario["kind"], "conditional_scenario")
        self.assertIn("not an observed outcome", scenario["interpretation"])


if __name__ == "__main__":
    unittest.main()
