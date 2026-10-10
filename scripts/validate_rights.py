"""Validate rights seed/structured-intake contracts without dependencies or live calls.

The runtime validator checks supported fields, excerpts, mappings and references;
this command does not claim full JSON Schema implementation or legal accuracy.
"""
import argparse
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewdesk.server import APIError, ReviewStore, decode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    failed = False
    for path in args.files:
        try:
            document = decode(path.read_bytes())
            with tempfile.TemporaryDirectory(prefix="trialwatch-rights-validation-") as state:
                if isinstance(document, dict) and isinstance(document.get("schema_version"), str) and document["schema_version"] in {"rights-intake/1", "rights-intake/2"}:
                    store = ReviewStore(ROOT / "reviewdesk/rights.synthetic.json", state)
                    store.rights.intake(document)
                else:
                    ReviewStore(path, state)
            print(str(path) + ": valid local contract (support semantics/legal correctness remain human checks)")
        except (APIError, OSError) as error:
            print(str(path) + ": " + str(error), file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
