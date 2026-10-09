"""Convert team observation records into a local, unreviewed campaign seed.

No retrieval, extraction, source verification, app reviews or saved analyses run.
One CSV row is one attributed observation. Dossier IDs are supplied by the team;
the importer never infers identity or joins records by a person's name or URL.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewdesk.server import (APIError, CAMPAIGN_CATEGORIES, identifier, iso_date,
                               public_url, string, validate_candidate)

FIELDS = (
    "dossier_id", "dossier_title", "person", "proceeding", "country", "dossier_unknowns",
    "source_id", "source_title", "publisher", "url", "publication_date", "retrieved_at",
    "language", "translation_status", "access_note", "lineage_note", "observation_id", "event_id",
    "summary", "excerpt", "locator", "event_date", "date_note", "attribution",
    "attribution_type", "observation_category", "review_status", "checked_by", "checked_at", "notes",
)
ATTRIBUTION_TYPES = {
    "source_allegation": "Source allegation",
    "reported_court_finding": "Reported court finding",
    "reported_activity": "Source-reported activity",
    "analyst_judgment": "Analyst judgment",
    "proposed_advocacy": "Proposed advocacy; not a completed action",
}
REVIEW_STATUSES = {
    "unreviewed": "Unreviewed",
    "ai_feasibility_only": "AI feasibility check only; not human review",
    "human_checked": "Human checked this observation; not whole-dossier approval",
}
NOTICE = (
    "Imported manual records remain pending app review. Text presence and substantive "
    "source support were not independently verified by the importer. Check labels are "
    "supplied by the record author, not established by this software. Suggested categories "
    "are guidance only; no app review or analysis has been saved."
)
GENERAL_UNKNOWNS = (
    "Current case status and completeness of campaign coverage remain unverified. "
    "Missing evidence means unknown; chronology does not establish causation."
)


def unknown(value):
    return not value or value.casefold() == "unknown"


def date_value(value, field):
    return iso_date(None if unknown(value) else value, field)


def timestamp(value, field):
    if unknown(value):
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
        raise APIError(f"{field} must be an ISO timestamp with seconds and timezone, or unknown.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError()
    except ValueError as exc:
        raise APIError(f"Invalid {field}.") from exc
    return value


def choice(value, choices, field, default=None):
    value = default if unknown(value) else value
    if value not in choices:
        raise APIError(f"{field} must be one of: {', '.join(choices)}.")
    return value


def read_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames or []
        if len(header) != len(set(header)) or set(header) != set(FIELDS):
            raise APIError("CSV columns must match the template exactly (order may differ); no duplicate headers.")
        rows = []
        for row in reader:
            line = reader.line_num
            if None in row or any(value is None for value in row.values()):
                raise APIError(f"CSV line {line}: wrong number of fields.")
            if not any(value.strip() for value in row.values()):
                continue
            rows.append((line, {key: string(value, key, blank=True) for key, value in row.items()}))
    return rows


def build_seed(path):
    dossiers, dossier_metadata, source_metadata, observation_ids = {}, {}, {}, set()
    for line, row in read_rows(path):
        try:
            did = identifier(row["dossier_id"], "dossier_id")
            sid = identifier(row["source_id"], "source_id")
            oid = identifier(row["observation_id"], "observation_id")
            event_id = None if unknown(row["event_id"]) else identifier(row["event_id"], "event_id")
            if oid in observation_ids:
                raise APIError("Duplicate observation_id: " + oid)
            observation_ids.add(oid)
            metadata = {key: string(row[key], key) for key in ("dossier_title", "person", "proceeding", "country")}
            metadata["dossier_unknowns"] = row["dossier_unknowns"]
            if did in dossier_metadata and dossier_metadata[did] != metadata:
                raise APIError("Conflicting dossier metadata for " + did)
            dossier_metadata[did] = metadata
            source = {
                "id": sid, "title": string(row["source_title"], "source_title"),
                "publisher": string(row["publisher"], "publisher"), "url": public_url(row["url"]),
                "publication_date": date_value(row["publication_date"], "publication_date"),
                "retrieved_at": timestamp(row["retrieved_at"], "retrieved_at"),
                "language": "und" if unknown(row["language"]) else row["language"],
                "translation_status": "Unknown; not recorded" if unknown(row["translation_status"]) else row["translation_status"],
                "access_note": "Unknown access conditions; importer did not fetch source" if unknown(row["access_note"]) else row["access_note"],
                "lineage_note": "Unknown; independent corroboration not established" if unknown(row["lineage_note"]) else row["lineage_note"],
            }
            source_key = (did, sid)
            if source_key in source_metadata and source_metadata[source_key] != source:
                raise APIError("Conflicting source metadata for " + did + "/" + sid)
            source_metadata[source_key] = source
            attribution_type = choice(row["attribution_type"], ATTRIBUTION_TYPES, "attribution_type")
            category = None if unknown(row["observation_category"]) else choice(row["observation_category"], CAMPAIGN_CATEGORIES, "observation_category")
            status = choice(row["review_status"], REVIEW_STATUSES, "review_status", "unreviewed")
            checked_by = None if unknown(row["checked_by"]) else row["checked_by"]
            checked_at = timestamp(row["checked_at"], "checked_at")
            if status == "unreviewed" and (checked_by or checked_at):
                raise APIError("Unreviewed records must leave checked_by and checked_at unknown.")
            if status != "unreviewed" and not (checked_by and checked_at):
                raise APIError("A record check requires checked_by and checked_at; AI checking is not human review.")
            attribution = string(row["attribution"], "attribution")
            check_note = REVIEW_STATUSES[status] + (f"; {checked_by}, {checked_at}" if checked_by else "")
            event_date = date_value(row["event_date"], "event_date")
            claim = {
                "id": oid, "text": string(row["summary"], "summary"), "source_id": sid,
                "excerpt": string(row["excerpt"], "excerpt", 2000), "locator": string(row["locator"], "locator", 2000),
                "event_date": event_date,
                "date_note": row["date_note"] or ("Event date unknown; publication date is not substituted." if event_date is None else "Event date supplied by record author; source support requires review."),
                "attribution": f"{ATTRIBUTION_TYPES[attribution_type]}: {attribution} Record check: {check_note}. Importer did not verify source support." + (f" Team event grouping: {event_id}; repeated reports do not establish additional activity." if event_id else " Event grouping unknown.") + (f" Record note: {row['notes']}" if row["notes"] else ""),
                "attribution_type": attribution_type, "original_attribution": attribution,
                "event_id": event_id,
                "suggested_category": category,
                "record_review": {"status": status, "checked_by": checked_by, "checked_at": checked_at},
                "record_notes": row["notes"],
            }
            if did not in dossiers:
                dossiers[did] = {
                    "id": did, "title": metadata["dossier_title"], "person": metadata["person"],
                    "proceeding": metadata["proceeding"], "country": metadata["country"],
                    "material_type": "manual_intake", "as_of": None, "summary": "Imported manual observations; review pending.",
                    "suggested_decision": "uncertain", "review_reasons": [NOTICE],
                    "unknowns": [GENERAL_UNKNOWNS] + ([metadata["dossier_unknowns"]] if not unknown(metadata["dossier_unknowns"]) else []),
                    "sources": [], "claims": [], "related_candidate_ids": [],
                    "notes": [NOTICE, "Dossier identity is an explicit team grouping, not an inferred identity match."],
                }
            candidate = dossiers[did]
            if not any(existing["id"] == sid for existing in candidate["sources"]):
                candidate["sources"].append(source)
            candidate["claims"].append(claim)
            validate_candidate(candidate)
        except APIError as exc:
            raise APIError(f"CSV line {line}: {exc}") from exc
    return {
        "schema_version": 1,
        "dataset": {"id": "manual_campaign_research", "label": "Manual campaign research records",
                    "kind": "manual_intake", "description": NOTICE},
        "candidates": list(dossiers.values()),
    }


def write_seed(document, output):
    output = Path(output).resolve()
    if output.suffix.lower() != ".json":
        raise APIError("Output must be a .json file. Use an ignored local location such as data/processed/research/.")
    if any(output.is_relative_to(ROOT / name) for name in ("reviewdesk", "examples", "docs", "scripts", "tests", "schemas")):
        raise APIError("Research output must stay outside public code/docs/example directories; use data/processed/research/.")
    # Validate and serialize fully before opening the destination; x refuses overwrites.
    content = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, help="CSV using examples/research_records.template.csv headers")
    parser.add_argument("--output", required=True, type=Path, help="New local JSON path; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        document = build_seed(args.records)
        output = write_seed(document, args.output)
    except (APIError, OSError, csv.Error, UnicodeError) as exc:
        parser.error(str(exc))
    print(f"Wrote {len(document['candidates'])} explicit dossiers / {sum(len(c['claims']) for c in document['candidates'])} observations to {output}")
    print("Pending review; no source verification, saved analysis, retrieval or publication. Use a fresh --state-dir.")


if __name__ == "__main__":
    main()
