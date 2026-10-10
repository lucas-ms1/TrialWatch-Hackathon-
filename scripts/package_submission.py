"""Build a local, allowlisted code package with synthetic examples only.

No upload, Git operation, source collection or notebook execution occurs.
"""
from __future__ import annotations

import csv
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_research_seed import FIELDS

FILES = [
    "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "pyproject.toml", ".gitignore", "AGENTS.md",
    "reviewdesk/__init__.py", "reviewdesk/__main__.py", "reviewdesk/server.py",
    "reviewdesk/demo.synthetic.json", "reviewdesk/static/index.html",
    "reviewdesk/static/app.js", "reviewdesk/static/style.css",
    "tests/test_reviewdesk.py", "tests/test_validate_data.py", "tests/test_experiment_01.py",
    "tests/test_advocacy.py", "tests/test_campaigns.py",
    "scripts/validate_data.py", "scripts/package_submission.py",
    "scripts/experiment_01/__init__.py", "scripts/experiment_01/__main__.py",
    "scripts/experiment_01/pipeline.py", "scripts/build_demo_fallback.py",
    "schemas/cases.schema.json", "schemas/README.md", "examples/cases.synthetic.json",
    "docs/TOOL_DESCRIPTION.md", "docs/DEMO_SCRIPT.md", "docs/SUBMISSION_CHECKLIST.md",
    "docs/EVENT_BRIEF.md", "docs/DECISIONS.md", "docs/SPRINT_PLAN.md",
    "docs/PROJECT_BRIEF.md", "docs/ANALYSIS_METHOD.md", "docs/VERIFICATION.md",
    "docs/demo/fallback.html", "docs/demo/comparison.synthetic.md", "docs/demo/comparison.synthetic.json",
    "experiments/philippines_pilot/config.json",  # static parameters used by legacy synthetic regression tests; no research records
    "scripts/build_research_seed.py", "tests/test_research_seed.py",
    "examples/research_records.template.csv", "docs/RESEARCH_HANDOFF.md",  # empty template and generic protocol only
    "docs/MATERIALS_AND_DEMO_OPTIONS.md", "docs/TECHNICAL_PLAN.md", "docs/TEAM_MESSAGE.md",
    "docs/PATTERN_REVIEW_WORKSHEET.md", "docs/PATTERN_PROPOSAL_PROMPT.md",  # blank preparation only, no results
    "docs/history/SPRINT_PLAN.2026-10-08.md", "docs/history/PROJECT_BRIEF.2026-10-08.md",
    "docs/history/PROJECT_BRIEF.before-interface-2026-10-09.md",
    "docs/history/PROJECT_BRIEF.before-strategy-2026-10-09.md",
    "docs/history/SPRINT_PLAN.before-progress-review-2026-10-09.md",
    "docs/history/TECHNICAL_PLAN.before-interface-2026-10-09.md",
    "docs/history/TECHNICAL_PLAN.before-strategy-2026-10-09.md",
    "docs/history/TOOL_DESCRIPTION.before-interface-2026-10-09.md",
    "docs/history/TOOL_DESCRIPTION.before-strategy-2026-10-09.md",
    "docs/TEAM_START_HERE.md", "docs/demo/signals-and-strategy.html", "docs/demo/README.md",
    "reviewdesk/rights.py",
    "reviewdesk/rights.synthetic.json",
    "reviewdesk/static/rights.html",
    "reviewdesk/static/rights.js",
    "reviewdesk/static/ai-wizard.js",
    "reviewdesk/static/advocacy-reader.js",
    "reviewdesk/static/synthetic-strategy.css",
    "reviewdesk/static/synthetic-strategy-data.js",
    "reviewdesk/static/synthetic-strategy-core.js",
    "reviewdesk/static/synthetic-strategy.js",
    "examples/synthetic-strategy.fixture.json",
    "scripts/load_synthetic_strategy_case.py",
    "scripts/check_synthetic_strategy.cjs",
    "tests/test_synthetic_strategy_fixture.py",
    "reviewdesk/static/judgment-import.js",
    "reviewdesk/static/judgment-import.css",
    "reviewdesk/judgment_import.py",
    "tests/test_judgment_import.py",
    "tests/test_judgment_import_http.py",
    "tests/test_evidence_additions.py",
    "tests/test_retained_sources.py",
    "examples/judgment-import.synthetic.json",
    "examples/judgment-import.template.json",
    "docs/JUDGMENT_IMPORT.md",
    "reviewdesk/static/rights.css",
    "examples/rights-intake.synthetic.json",
    "schemas/rights-assessment.schema.json",
    "scripts/build_rights_seed.py",
    "scripts/validate_rights.py",
    "tests/test_rights.py",
    "docs/RIGHTS_RUBRIC.md",
    "docs/DATA_SOURCE_INVENTORY.md",
    "docs/history/AGENTS.before-rights-pivot-2026-10-09.md",
    "docs/history/ANALYSIS_METHOD.before-rights-pivot-2026-10-09.md",
    "docs/history/DEMO_SCRIPT.before-rights-pivot-2026-10-09.md",
    "docs/history/EVENT_BRIEF.before-rights-pivot-2026-10-09.md",
    "docs/history/MATERIALS_AND_DEMO_OPTIONS.before-rights-pivot-2026-10-09.md",
    "docs/history/PROJECT_BRIEF.before-rights-pivot-2026-10-09.md",
    "docs/history/README.before-rights-pivot-2026-10-09.md",
    "docs/history/RESEARCH_HANDOFF.before-rights-pivot-2026-10-09.md",
    "docs/history/SPRINT_PLAN.before-rights-pivot-2026-10-09.md",
    "docs/history/SUBMISSION_CHECKLIST.before-rights-pivot-2026-10-09.md",
    "docs/history/TEAM_START_HERE.before-rights-pivot-2026-10-09.md",
    "docs/history/TECHNICAL_PLAN.before-rights-pivot-2026-10-09.md",
    "docs/history/TOOL_DESCRIPTION.before-rights-pivot-2026-10-09.md",
    "docs/history/VERIFICATION.before-rights-pivot-2026-10-09.md",
    "reviewdesk/rights-rubric.v1.json",
    "reviewdesk/rights.synthetic.v2.json",
    "examples/rights-intake.synthetic.v2.json",
    "schemas/rights-assessment.v2.schema.json",
    "reviewdesk/intervention.py",
    "schemas/intervention.schema.json",
    "examples/intervention.synthetic.json",
    "tests/test_intervention.py",
    "scripts/rehearse_intervention.py",
    "docs/INTERVENTION_API.md",
    "docs/INTERVENTION_METHOD.md",
    "docs/history/AGENTS.before-connected-intervention-2026-10-09.md",
    "docs/history/ANALYSIS_METHOD.before-connected-intervention-2026-10-09.md",
    "docs/history/DEMO_SCRIPT.before-connected-intervention-2026-10-09.md",
    "docs/history/PROJECT_BRIEF.before-connected-intervention-2026-10-09.md",
    "docs/history/README.before-connected-intervention-2026-10-09.md",
    "docs/history/RIGHTS_RUBRIC.before-connected-intervention-2026-10-09.md",
    "docs/history/TEAM_START_HERE.before-connected-intervention-2026-10-09.md",
    "docs/history/TEAM_MESSAGE.before-connected-intervention-2026-10-09.md",
    "docs/history/VERIFICATION.before-connected-intervention-2026-10-09.md",
    "docs/history/TOOL_DESCRIPTION.before-connected-intervention-2026-10-09.md",
    "docs/history/TECHNICAL_PLAN.before-connected-intervention-2026-10-09.md",
    "docs/history/SPRINT_PLAN.before-connected-intervention-2026-10-09.md",
    "docs/history/schemas-README.before-connected-intervention-2026-10-09.md",
    "docs/history/SUBMISSION_CHECKLIST.before-connected-intervention-2026-10-09.md",
    "reviewdesk/ai_drafts.py", "reviewdesk/draft_contract.py",
    "schemas/ai-draft.schema.json", "examples/ai-draft.synthetic.json",
    "tests/test_ai_drafts.py", "docs/AI_DRAFTING.md",
    "scripts/build_ai_fixture.py",
    "docs/AI_DRAFT_API.md",
]


def validate_blank_research_template(path):
    """Fail closed if the public template acquired any research observations."""
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        rows = csv.reader(stream, strict=True)
        if tuple(next(rows, ())) != FIELDS:
            raise ValueError("Research template must retain the exact documented header.")
        if any(any(value.strip() for value in row) for row in rows):
            raise ValueError("Research template contains data rows. Keep filled records in ignored local storage.")


def main() -> None:
    sources = [ROOT / name for name in FILES]
    missing = [str(p.relative_to(ROOT)) for p in sources if not p.is_file()]
    if missing:
        raise SystemExit("Package incomplete; missing: " + ", ".join(missing))
    try:
        validate_blank_research_template(ROOT / "examples/research_records.template.csv")
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        raise SystemExit("Public research template must remain header-only: " + str(exc)) from exc
    seed = json.loads((ROOT / "reviewdesk/demo.synthetic.json").read_text(encoding="utf-8"))
    if seed["dataset"]["kind"] != "synthetic" or any(c["material_type"] != "synthetic" for c in seed["candidates"]):
        raise SystemExit("The public starter package must contain synthetic examples only.")
    comparison = json.loads((ROOT / "docs/demo/comparison.synthetic.json").read_text(encoding="utf-8"))
    if comparison["dataset"]["kind"] != "synthetic" or any(c["material_type"] != "synthetic" for c in comparison["campaigns"]):
        raise SystemExit("The offline comparison must contain synthetic examples only.")
    from reviewdesk.server import ReviewStore
    from reviewdesk.judgment_import import inspect_judgment, preview_judgment
    judgment_example = json.loads((ROOT / "examples/judgment-import.synthetic.json").read_text(encoding="utf-8"))
    if judgment_example.get("provider") != "synthetic_fixture":
        raise SystemExit("The public judgment example must remain explicitly fictional.")
    inspected = inspect_judgment(judgment_example)
    judgment_preview = preview_judgment({**judgment_example, "selected_passage_ids": [inspected["passages"][0]["id"]]})
    if (judgment_preview["intake"]["candidate"]["material_type"] != "synthetic"
            or judgment_preview["intake"]["prepared_mappings"] is not None):
        raise SystemExit("The public judgment preview must be synthetic and unassessed.")
    with tempfile.TemporaryDirectory(prefix="trialwatch-public-judgment-check-") as temporary:
        judgment_store = ReviewStore(ROOT / "reviewdesk/rights.synthetic.v2.json", temporary)
        judgment_store.rights.intake(judgment_preview["intake"])
    from scripts.load_synthetic_strategy_case import load_case
    with tempfile.TemporaryDirectory(prefix="trialwatch-public-strategy-check-") as temporary:
        strategy_store = ReviewStore(ROOT / "reviewdesk/rights.synthetic.v2.json", temporary)
        load_case(strategy_store)
    from reviewdesk.draft_contract import parse_json
    ai_example = json.loads((ROOT / "examples/ai-draft.synthetic.json").read_text(encoding="utf-8"))
    ai_payload = ai_example.get("import_payload", {})
    if (ai_example.get("material_type") != "synthetic" or ai_payload.get("origin") != "synthetic_fixture"
            or ai_payload.get("receipt_json") is not None):
        raise SystemExit("The pending AI starter must be a synthetic fixture with no provider receipt.")
    clean_ai_input = parse_json(ai_payload.get("model_input_json"), "model_input_json")
    if any("example.invalid" not in source.get("url", "") for source in clean_ai_input["source_metadata"]):
        raise SystemExit("Synthetic draft factual URLs must remain nonresolving fictional fixture URLs.")
    with tempfile.TemporaryDirectory(prefix="trialwatch-public-ai-draft-check-") as temporary:
        ai_store = ReviewStore(ROOT / "reviewdesk/rights.synthetic.v2.json", temporary)
        ai_record = ai_store.ai_drafts.import_draft(ai_example["candidate_id"], ai_payload)
        ai_store.ai_drafts.worksheet(ai_example["candidate_id"], {
            "expected_draft_revision": ai_record["revision"],
            "author": "Synthetic package verification label",
            "selected_option_id": "verify_records",
        })
    from reviewdesk.rights import RUBRIC_VERSION
    for seed_name, intake_name, version in (
        ("reviewdesk/rights.synthetic.json", "examples/rights-intake.synthetic.json", "rights-intake/1"),
        ("reviewdesk/rights.synthetic.v2.json", "examples/rights-intake.synthetic.v2.json", "rights-intake/2"),
    ):
        rights_seed = json.loads((ROOT / seed_name).read_text(encoding="utf-8"))
        if rights_seed["dataset"]["kind"] != "synthetic" or any(c["material_type"] != "synthetic" for c in rights_seed["candidates"]):
            raise SystemExit("The rights starter package must contain synthetic examples only: " + seed_name)
        rights_intake = json.loads((ROOT / intake_name).read_text(encoding="utf-8"))
        if rights_intake["schema_version"] != version or rights_intake["candidate"]["material_type"] != "synthetic":
            raise SystemExit("The shareable rights intake must remain synthetic: " + intake_name)
        with tempfile.TemporaryDirectory(prefix="trialwatch-public-rights-check-") as temporary:
            store = ReviewStore(ROOT / seed_name, temporary)
            store.rights.intake(rights_intake)
    example = json.loads((ROOT / "examples/intervention.synthetic.json").read_text(encoding="utf-8"))
    if (example.get("schema_version") != "intervention-example/1" or example.get("synthetic") is not True
            or example.get("context", {}).get("origin") != "synthetic_prepared"
            or example.get("proposal", {}).get("origin") != "synthetic_prepared"):
        raise SystemExit("The intervention worksheet example must remain explicitly synthetic.")
    with tempfile.TemporaryDirectory(prefix="trialwatch-public-intervention-check-") as temporary:
        store = ReviewStore(ROOT / "reviewdesk/rights.synthetic.v2.json", temporary)
        cid = "rights_demo_1"
        store.rights.save(cid, {"expected_revision": 0, "expected_evidence_revision": 0,
                              "rubric_version": RUBRIC_VERSION, "analyst": "Synthetic package validator; no human legal review",
                              "preparation": "synthetic_prepared", "dimensions": deepcopy(store.rights.prepared[cid])})
        store.interventions.context(cid, deepcopy(example["context"]))
        recommendation = store.interventions.propose(cid, deepcopy(example["proposal"]))
        store.interventions.followup(recommendation["id"], deepcopy(example["followup"]))
        exported = store.interventions.export(recommendation["id"])
        if exported["recommendation"]["rights_snapshots"][cid]["case_profile"]["assessment"]["evidence_snapshot"]["material_type"] != "synthetic":
            raise SystemExit("The intervention fixture unexpectedly depends on non-synthetic case evidence.")
    manifest = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
    manifest_text = json.dumps({"scope": "Local submission candidate; not published or submitted. Original code/docs and synthetic data only. Historical local evidence, all runtime databases, full articles, notebook bundles and organizer PDFs excluded.", "files": manifest}, indent=2) + "\n"
    digest = hashlib.sha256(manifest_text.encode()).hexdigest()[:12]
    destination = ROOT / "outputs/submission" / f"trialwatch-connected-desk-{digest}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, name)
        archive.writestr("PACKAGE_MANIFEST.json", manifest_text)
    with ZipFile(destination) as archive:
        if set(archive.namelist()) != set(FILES) | {"PACKAGE_MANIFEST.json"}:
            raise SystemExit("Unexpected files in submission archive")
        if archive.testzip():
            raise SystemExit("ZIP integrity check failed")
        for name, expected in manifest.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise SystemExit("Packaged hash mismatch: " + name)
    (destination.with_suffix(".manifest.json")).write_text(manifest_text, encoding="utf-8")
    print(destination)
    print(f"Verified {len(FILES)} allowlisted files; no publication or submission performed.")


if __name__ == "__main__":
    main()
