"""Validate the preparation contract with Python's standard library.

This implements only the JSON Schema keywords used by cases.schema.json,
plus record-level semantics. It is not a general JSON Schema implementation.
It does not fetch sources or establish the truth or legal significance of claims.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlsplit


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "cases.schema.json"
SUPPORTED_KEYWORDS = {
    "$schema", "$id", "$defs", "$ref", "title", "description", "type", "const",
    "enum", "required", "properties", "additionalProperties", "items", "minItems",
    "minLength", "pattern", "format",
}


def load_json(path: Path) -> Any:
    """Reject duplicate JSON keys and nonstandard NaN/Infinity values."""
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key!r}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ValueError(f"nonstandard JSON constant: {value}")

    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=unique_object,
        parse_constant=invalid_constant,
    )


def _check_schema(schema: dict[str, Any]) -> None:
    """Fail visibly if contract edits outgrow this intentionally small validator."""
    unknown = set(schema) - SUPPORTED_KEYWORDS
    if unknown:
        raise ValueError(f"unsupported schema keywords: {sorted(unknown)}")
    for group in ("$defs", "properties"):
        for child in schema.get(group, {}).values():
            _check_schema(child)
    if "items" in schema:
        _check_schema(schema["items"])
    if schema.get("format") not in (None, "date", "date-time", "uri"):
        raise ValueError(f"unsupported schema format: {schema['format']}")


def _matches_type(value: Any, kind: str) -> bool:
    return {
        "null": value is None,
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
    }.get(kind, False)


def _valid_format(value: str, kind: str) -> bool:
    try:
        if kind == "date":
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) and bool(date.fromisoformat(value))
        if kind == "date-time":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)", value):
                return False
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.utcoffset() is not None
        if kind == "uri":
            parsed_url = urlsplit(value)
            return bool(parsed_url.scheme and parsed_url.hostname) and not any(c.isspace() for c in value)
    except ValueError:
        return False
    return False


def _validate_shape(value: Any, rule: dict[str, Any], root: dict[str, Any], path: str, errors: list[str]) -> None:
    if "$ref" in rule:
        reference = rule["$ref"]
        if not reference.startswith("#/$defs/"):
            raise ValueError(f"unsupported schema reference: {reference}")
        _validate_shape(value, root["$defs"][reference.removeprefix("#/$defs/")], root, path, errors)
        return
    if "type" in rule:
        kinds = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
        if not any(_matches_type(value, kind) for kind in kinds):
            errors.append(f"{path}: expected {' or '.join(kinds)}")
            return
    if "const" in rule and value != rule["const"]:
        errors.append(f"{path}: expected {rule['const']!r}")
    if "enum" in rule and value not in rule["enum"]:
        errors.append(f"{path}: expected one of {rule['enum']}")
    if isinstance(value, dict):
        properties = rule.get("properties", {})
        for key in rule.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required field missing")
        for key, child in value.items():
            if key in properties:
                _validate_shape(child, properties[key], root, f"{path}.{key}", errors)
            elif rule.get("additionalProperties") is False:
                errors.append(f"{path}.{key}: unexpected field")
    elif isinstance(value, list):
        if len(value) < rule.get("minItems", 0):
            errors.append(f"{path}: requires at least {rule['minItems']} item(s)")
        for index, child in enumerate(value):
            if "items" in rule:
                _validate_shape(child, rule["items"], root, f"{path}[{index}]", errors)
    elif isinstance(value, str):
        if len(value.strip()) < rule.get("minLength", 0):
            errors.append(f"{path}: must contain nonblank text")
        if "pattern" in rule and re.search(rule["pattern"], value) is None:
            errors.append(f"{path}: does not match {rule['pattern']!r}")
        if "format" in rule and not _valid_format(value, rule["format"]):
            errors.append(f"{path}: invalid {rule['format']}")


def validate_document(document: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return structural and semantic errors; no network calls or model calls."""
    schema = schema if schema is not None else load_json(SCHEMA_PATH)
    _check_schema(schema)
    errors: list[str] = []
    _validate_shape(document, schema, schema, "$", errors)
    if errors:
        return errors  # Semantic checks below require a valid structural shape.

    case_ids: set[str] = set()
    for case_index, case in enumerate(document["cases"]):
        path = f"$.cases[{case_index}]"
        if case["case_id"] in case_ids:
            errors.append(f"{path}.case_id: duplicate case ID {case['case_id']!r}")
        case_ids.add(case["case_id"])
        source_ids: set[str] = set()
        for source_index, source in enumerate(case["sources"]):
            if source["source_id"] in source_ids:
                errors.append(f"{path}.sources[{source_index}].source_id: duplicate source ID {source['source_id']!r}")
            source_ids.add(source["source_id"])
        claim_ids: set[str] = set()
        for claim_index, claim in enumerate(case["claims"]):
            claim_path = f"{path}.claims[{claim_index}]"
            if claim["claim_id"] in claim_ids:
                errors.append(f"{claim_path}.claim_id: duplicate claim ID {claim['claim_id']!r}")
            claim_ids.add(claim["claim_id"])
            for evidence_index, evidence in enumerate(claim["evidence"]):
                if evidence["source_id"] not in source_ids:
                    errors.append(f"{claim_path}.evidence[{evidence_index}].source_id: unknown source {evidence['source_id']!r}")
        review = case["review"]
        if not case["claims"] and review["status"] != "needs_sources":
            errors.append(f"{path}.review.status: cases without claims must be needs_sources")
        if review["reviewed_at"] is not None and review["reviewer"] is None:
            errors.append(f"{path}.review.reviewer: reviewer required when reviewed_at is set")
        if review["status"] == "ready_for_expert_review" and (review["reviewer"] is None or review["reviewed_at"] is None):
            errors.append(f"{path}.review: ready_for_expert_review requires reviewer and reviewed_at")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="case JSON files to validate")
    args = parser.parse_args(argv)
    failed = False
    try:
        schema = load_json(SCHEMA_PATH)
        _check_schema(schema)
    except (OSError, ValueError) as exc:
        print(f"Schema error: {exc}", file=sys.stderr)
        return 2
    for path in args.files:
        try:
            document = load_json(path)
            errors = validate_document(document, schema)
        except (OSError, ValueError) as exc:
            errors = [str(exc)]
        if errors:
            failed = True
            print(f"FAIL {path}", file=sys.stderr)
            for error in errors:
                print(f"  {error}", file=sys.stderr)
        else:
            cases = document["cases"]
            synthetic_count = sum(case["synthetic"] for case in cases)
            print(f"PASS {path}: {len(cases)} case(s), {synthetic_count} synthetic. Structure only; source accuracy requires human review.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
