"""Build a local, allowlisted code package with synthetic examples only.

No upload, Git operation, source collection or notebook execution occurs.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
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
    manifest = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
    manifest_text = json.dumps({"scope": "Local submission candidate; not published or submitted. Original code/docs and synthetic data only. Historical local evidence, all runtime databases, full articles, notebook bundles and organizer PDFs excluded.", "files": manifest}, indent=2) + "\n"
    digest = hashlib.sha256(manifest_text.encode()).hexdigest()[:12]
    destination = ROOT / "outputs/submission" / f"trialwatch-campaign-comparison-{digest}.zip"
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
