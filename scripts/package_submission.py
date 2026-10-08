"""Build a local, allowlisted code package with synthetic examples only.

No upload, Git operation, source collection or notebook execution occurs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "pyproject.toml", ".gitignore",
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
]


def main() -> None:
    sources = [ROOT / name for name in FILES]
    missing = [str(p.relative_to(ROOT)) for p in sources if not p.is_file()]
    if missing:
        raise SystemExit("Package incomplete; missing: " + ", ".join(missing))
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
