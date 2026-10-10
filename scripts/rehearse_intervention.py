"""Local synthetic connected walkthrough; creates no real human review or advocacy."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewdesk.server import ReviewStore
from reviewdesk.rights import RUBRIC_VERSION
from reviewdesk.intervention import render_intervention_markdown


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    destination = args.output_dir or ROOT / "outputs/intervention_rehearsal" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if destination.exists():
        parser.error("Use a fresh output directory; existing state is never overwritten.")
    destination.mkdir(parents=True)
    seed = ROOT / "reviewdesk/rights.synthetic.v2.json"
    store = ReviewStore(seed, destination / "state")
    example = json.loads((ROOT / "examples/intervention.synthetic.json").read_text(encoding="utf-8"))
    cid = "rights_demo_1"
    assert store.originals[cid]["material_type"] == "synthetic"
    assessment = store.rights.save(cid, {"expected_revision": 0, "expected_evidence_revision": 0, "rubric_version": RUBRIC_VERSION, "analyst": "Synthetic rehearsal preparer", "preparation": "synthetic_prepared", "dimensions": deepcopy(store.rights.prepared[cid])})
    notice = next(d for d in assessment["dimensions"] if d["dimension_id"] == "notice_charges")
    store.rights.review(cid, {"expected_assessment_revision": 1, "expected_review_revision": 0, "expected_evidence_revision": 0, "reviewer": "Synthetic demonstration reviewer; software simulation", "reason": "Only notice and its exact support/contrary passages; no actual human legal validation.", "decision": "approve", "dimension_ids": ["notice_charges"], "claim_ids": list(set(notice["support_claim_ids"] + notice["contrary_claim_ids"]))})
    context = store.interventions.context(cid, deepcopy(example["context"]))
    recommendation = store.interventions.propose(cid, deepcopy(example["proposal"]))
    assert recommendation["disposition"] == "prepare_verify"
    scope = recommendation["review_scope"]
    decision = store.interventions.review(recommendation["id"], {"expected_review_revision": 0, "reviewer": "Synthetic demonstration reviewer; software simulation", "decision": "accept", "reason": "Accept targeted local verification preparation only; uncertainty, public-advocacy deferral and contrary account retained.", "dimension_ids": scope["dimension_ids"], "context_claim_ids": scope["context_claim_ids"], "revised_disposition": None, "revision_note": ""})
    store.interventions.followup(recommendation["id"], deepcopy(example["followup"]))
    exported = store.interventions.export(recommendation["id"])
    (destination / "decision.json").write_text(json.dumps(exported, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "decision.md").write_text(render_intervention_markdown(exported), encoding="utf-8")
    insufficient = store.interventions.propose(cid, {**deepcopy(example["proposal"]), "expected_revision": 1, "requested_disposition": "insufficient_basis"})
    deferred = store.interventions.propose(cid, {**deepcopy(example["proposal"]), "expected_revision": 2, "selected_option_id": "defer_public", "requested_disposition": "defer"})
    assert insufficient["disposition"] == "insufficient_basis" and deferred["disposition"] == "defer"
    original = store.originals[cid]["claims"][0]
    store.review(cid, {"expected_revision": 0, "reviewer": "Synthetic correction simulation", "decision": "defer", "reason": "Fictional evidence correction tests dependent recommendation staleness.", "duplicate_of": None, "corrections": [{"claim_id": original["id"], "text": "Fictional corrected proposition; original passage remains and support is unresolved.", "event_date": None, "source_id": original["source_id"], "excerpt": original["excerpt"], "locator": original["locator"]}], "included_claim_ids": []})
    reopened = ReviewStore(seed, destination / "state")
    stale = reopened.interventions.export(recommendation["id"])
    assert stale["recommendation"]["stale"] and stale["recommendation"]["reviews"] == [decision]
    assert stale["recommendation"]["context_snapshot"] == context
    (destination / "decision.stale.json").write_text(json.dumps(stale, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "decision.stale.md").write_text(render_intervention_markdown(stale), encoding="utf-8")
    receipt = {"synthetic": True, "checked_at": datetime.now(timezone.utc).isoformat(), "candidate_id": cid, "recommendation_id": recommendation["id"], "observed_software_behaviors": ["Saved sourced synthetic rights assessment", "Simulated only notice-dimension approval", "Saved dated context and two options", "Generated preparation recommendation", "Simulated exact recommendation-scope acceptance", "Conditional scenario retained separately from observed outcome", "Insufficient basis and specified deferral stayed distinct", "Evidence correction flagged prior recommendation stale", "Reopened state preserved snapshots, scope and review"], "limitations": "Software rehearsal only, with fictional sources and simulated reviewers. No legal accuracy, human validation, useful advocacy effect, calibrated probability or actual intervention is demonstrated."}
    (destination / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(destination.resolve())
    print("Synthetic connected rehearsal passed; exports/state retained locally, no advocacy executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
