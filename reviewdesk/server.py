"""Small loopback-only review service with immutable inputs and durable decisions.

This serves saved evidence, human-entered material and pending source-assisted
drafts. An explicit startup flag enables one bounded local Codex request. It does
not fetch sources, verify allegations or modify the experiment that supplied a seed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, quote, unquote, urlsplit
from uuid import uuid4


MAX_BODY = 1_048_576
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\Z")
DISCLAIMER = (
    "This is a candidate-review brief, not a legal finding or factual certification. "
    "Historical reporting does not establish current case status. Current status has not "
    "been verified. A human triage decision is not whole-card factual approval. "
    "Source allegations, reported court decisions, and reviewer interpretations remain distinct."
)
ADVOCACY_DISCLAIMER = (
    "This is an analyst-authored advocacy proposal grounded in selected source-attributed statements, "
    "not a legal finding, factual certification, or instruction to contact anyone. "
    "Source allegations and reported court findings retain their attribution; analyst judgments and proposed actions "
    "are not sourced facts. Current case status remains unknown unless separately verified. "
    "Follow-up entries record actions or observed changes, not measured advocacy effectiveness. "
    "Chronology does not establish causation. No intervention is shown to have caused an outcome."
)
CAMPAIGN_CATEGORIES = {
    "social_media": "Social media activity",
    "international_attention": "International attention",
    "campaign_action": "Human rights campaign action",
    "legal_outcome": "Reported legal outcome",
    "policy_outcome": "Reported policy development",
    "context": "Context",
}
CAMPAIGN_DISCLAIMER = (
    "This comparison organizes selected source-attributed observations and analyst interpretations. "
    "Coding is an analyst judgment, not AI extraction or independent verification. Source allegations, "
    "reported court findings, and analyst interpretations remain distinct. Chronology and co-occurrence "
    "do not establish causation. This is not an effectiveness ranking or a measurement of national impact. "
    "Missing evidence means unknown, not that an activity or outcome did not occur. Current case status remains unverified."
)
CAMPAIGN_LIMITATIONS = [
    "Convenience sample: these saved dossiers do not represent all campaigns, cases, or countries.",
    "Reporting and selection bias: coverage and analyst selection affect what is documented; unreported activity is unknown.",
    "Confounding: legal merits, institutions, timing, other actors, and other interventions can explain observed changes.",
    "Source dependence: distinct URLs are not proof of independent corroboration; reports may repeat the same source.",
    "Coded observations and unique cited URLs measure this evidence collection, not audience reach, campaign intensity, or effectiveness.",
    "Dossiers are not automatically distinct cases; repeated coverage and uncertain identity matches require human review.",
]


class APIError(Exception):
    def __init__(self, message, status=400, code="invalid_request"):
        super().__init__(message)
        self.status, self.code = status, code


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Repeated JSON field: " + key)
        result[key] = value
    return result


def decode(raw):
    def invalid_constant(value):
        raise ValueError("Non-finite JSON value")
    try:
        return json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise APIError("Malformed JSON.") from exc


def string(value, field, limit=12000, blank=False):
    if not isinstance(value, str) or len(value) > limit or (not blank and not value.strip()):
        raise APIError(f"{field} must be {'a' if blank else 'a nonblank'} string of at most {limit} characters.")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise APIError(f"{field} contains control characters.")
    return value.strip()


def identifier(value, field="id"):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise APIError(f"Invalid {field}.")
    return value


def iso_date(value, field):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise APIError(f"{field} must be YYYY-MM-DD or null.")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise APIError(f"Invalid {field}.") from exc
    return value


def public_url(value):
    value = string(value, "url", 4096)
    try:
        parts = urlsplit(value)
        if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password
                or any(c.isspace() or ord(c) < 32 for c in value)
                or any(c in value for c in '<>"\'`\\')):
            raise ValueError()
        parts.port
    except ValueError as exc:
        raise APIError("Source URL must be a valid HTTP(S) URL without credentials or unsafe characters.") from exc
    return value


def require_fields(payload, fields):
    if not isinstance(payload, dict):
        raise APIError("Expected a JSON object.")
    missing = fields - payload.keys()
    extra = payload.keys() - fields
    if missing or extra:
        raise APIError(f"Payload fields differ: missing={sorted(missing)}, unexpected={sorted(extra)}.")


def validate_candidate(candidate):
    if not isinstance(candidate, dict):
        raise APIError("Each candidate must be an object.")
    identifier(candidate.get("id"))
    for key in ("title", "person", "proceeding", "country", "summary"):
        string(candidate.get(key), key)
    if not isinstance(candidate.get("material_type"), str) or candidate["material_type"] not in {"historical", "synthetic", "manual_intake"}:
        raise APIError("Invalid material_type.")
    iso_date(candidate.get("as_of"), "as_of")
    if not isinstance(candidate.get("suggested_decision"), str) or candidate["suggested_decision"] not in {"include", "exclude", "uncertain"}:
        raise APIError("Invalid suggested_decision.")
    for key in ("review_reasons", "unknowns", "related_candidate_ids", "notes"):
        if not isinstance(candidate.get(key), list):
            raise APIError(f"{key} must be an array.")
        for value in candidate[key]:
            string(value, key)
    sources, claims = candidate.get("sources"), candidate.get("claims")
    if not isinstance(sources, list) or not sources or len(sources) > 100:
        raise APIError("Candidate needs 1–100 sources.")
    if not isinstance(claims, list) or len(claims) > 500:
        raise APIError("Candidate claims must be an array of at most 500 items.")
    source_ids, claim_ids = set(), set()
    for source in sources:
        if not isinstance(source, dict):
            raise APIError("Invalid source.")
        sid = identifier(source.get("id"), "source id")
        if sid in source_ids:
            raise APIError("Duplicate source ID.")
        source_ids.add(sid)
        public_url(source.get("url"))
        iso_date(source.get("publication_date"), "publication_date")
        for field in ("title", "publisher", "language", "translation_status", "access_note", "lineage_note"):
            string(source.get(field), field)
        if source.get("retrieved_at") is not None:
            string(source["retrieved_at"], "retrieved_at")
    for claim in claims:
        if not isinstance(claim, dict):
            raise APIError("Invalid claim.")
        cid = identifier(claim.get("id"), "claim id")
        if cid in claim_ids:
            raise APIError("Duplicate claim ID.")
        claim_ids.add(cid)
        if not isinstance(claim.get("source_id"), str) or claim["source_id"] not in source_ids:
            raise APIError("Claim references an unknown source.")
        for field in ("text", "excerpt", "locator", "attribution"):
            string(claim.get(field), field)
        string(claim.get("date_note"), "date_note", blank=True)
        iso_date(claim.get("event_date"), "event_date")


class ReviewStore:
    """SQLite transactions serialize revisions across threads/processes.

    Rows are inserted, never updated or deleted. The database is bound to the
    exact seed bytes; a different dataset requires a separate state directory.
    """

    def __init__(self, seed, state_dir):
        self.seed_path = Path(seed).resolve()
        raw = self.seed_path.read_bytes()
        document = decode(raw)
        if (not isinstance(document, dict) or document.get("schema_version") != 1
                or not isinstance(document.get("dataset"), dict)
                or not isinstance(document.get("candidates"), list)):
            raise APIError("Unsupported seed format.")
        self.dataset = document["dataset"]
        self.has_rights_seed = "rights_prepared_mappings" in document
        for key in ("id", "label", "kind", "description"):
            string(self.dataset.get(key), "dataset." + key)
        self.originals = {}
        for candidate in document["candidates"]:
            validate_candidate(candidate)
            if candidate["id"] in self.originals:
                raise APIError("Duplicate candidate ID in seed.")
            self.originals[candidate["id"]] = candidate
        for candidate in self.originals.values():
            if not set(candidate["related_candidate_ids"]) <= self.originals.keys():
                raise APIError("Unresolved related candidate ID.")
        state_dir = Path(state_dir).resolve()
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "reviewdesk.sqlite3"
        with self.connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS intakes (id TEXT PRIMARY KEY, candidate TEXT NOT NULL, source_text TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reviews (
                    candidate_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(candidate_id, revision));
                CREATE TABLE IF NOT EXISTS evidence_additions (
                    candidate_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(candidate_id, revision));
                CREATE TABLE IF NOT EXISTS advocacy_plans (
                    candidate_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(candidate_id, revision));
                CREATE TABLE IF NOT EXISTS followups (
                    candidate_id TEXT NOT NULL, sequence INTEGER NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(candidate_id, sequence));
                CREATE TABLE IF NOT EXISTS campaign_analyses (
                    candidate_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(candidate_id, revision));
            """)
            connection.execute("BEGIN IMMEDIATE")
            digest = hashlib.sha256(raw).hexdigest()
            existing = connection.execute("SELECT value FROM metadata WHERE key='seed_sha256'").fetchone()
            if existing and existing[0] != digest:
                raise APIError("This state directory belongs to a different seed. Use a new state directory.", 409, "seed_changed")
            if not existing:
                connection.execute("INSERT INTO metadata VALUES ('seed_sha256', ?)", (digest,))
        # Explicit new contract; legacy candidate/review/analysis fields retain
        # their original meanings and all historical state remains untouched.
        from .rights import RightsService
        self.rights = RightsService(self, document)
        from .intervention import InterventionService
        self.interventions = InterventionService(self)
        from .ai_drafts import DraftService
        self.ai_drafts = DraftService(self)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def candidates(self, connection):
        candidates = dict(self.originals)
        candidates.update({row[0]: json.loads(row[1]) for row in connection.execute("SELECT id,candidate FROM intakes ORDER BY rowid")})
        for cid, record in connection.execute("SELECT candidate_id,record FROM evidence_additions ORDER BY candidate_id,revision"):
            addition = json.loads(record)
            original = candidates[cid]
            candidates[cid] = {**original, "claims": original["claims"] + addition["claims"]}
        return candidates

    @staticmethod
    def evidence_revision(connection, cid):
        """Dependency revision includes additions; human review revisions stay separate."""
        review = connection.execute("SELECT MAX(revision) FROM reviews WHERE candidate_id=?", (cid,)).fetchone()[0] or 0
        addition = connection.execute("SELECT MAX(revision) FROM evidence_additions WHERE candidate_id=?", (cid,)).fetchone()[0] or 0
        return review + addition

    @staticmethod
    def histories(connection):
        result = {}
        for cid, record in connection.execute("SELECT candidate_id,record FROM reviews ORDER BY candidate_id,revision"):
            result.setdefault(cid, []).append(json.loads(record))
        return result

    @staticmethod
    def advocacy_histories(connection):
        result = {}
        for cid, record in connection.execute("SELECT candidate_id,record FROM advocacy_plans ORDER BY candidate_id,revision"):
            result.setdefault(cid, []).append(json.loads(record))
        return result

    @staticmethod
    def followup_histories(connection):
        result = {}
        for cid, record in connection.execute("SELECT candidate_id,record FROM followups ORDER BY candidate_id,sequence"):
            result.setdefault(cid, []).append(json.loads(record))
        return result

    @staticmethod
    def campaign_histories(connection):
        result = {}
        for cid, record in connection.execute("SELECT candidate_id,record FROM campaign_analyses ORDER BY candidate_id,revision"):
            result.setdefault(cid, []).append(json.loads(record))
        return result

    def state(self):
        with self.connection() as connection:
            connection.execute("BEGIN")
            candidates = self.candidates(connection)
            history = self.histories(connection)
            advocacy_history = self.advocacy_histories(connection)
            followups = self.followup_histories(connection)
            campaign_history = self.campaign_histories(connection)
        return {"dataset": self.dataset, "candidates": list(candidates.values()),
                "reviews": {cid: rows[-1] for cid, rows in history.items()}, "history": history,
                "advocacy": {cid: rows[-1] for cid, rows in advocacy_history.items()},
                "advocacy_history": advocacy_history, "followups": followups,
                "campaigns": {cid: rows[-1] for cid, rows in campaign_history.items()}, "campaign_history": campaign_history}

    def review(self, cid, payload):
        identifier(cid)
        fields = {"expected_revision", "reviewer", "decision", "reason", "duplicate_of", "corrections", "included_claim_ids"}
        require_fields(payload, fields)
        revision = payload["expected_revision"]
        if type(revision) is not int or revision < 0:
            raise APIError("expected_revision must be a nonnegative integer.")
        reviewer = string(payload["reviewer"], "reviewer", 200)
        reason = string(payload["reason"], "reason", 8000)
        decision = payload["decision"]
        if not isinstance(decision, str) or decision not in {"include", "defer", "exclude", "duplicate"}:
            raise APIError("Invalid review decision.")
        if not isinstance(payload["corrections"], list) or len(payload["corrections"]) > 500:
            raise APIError("corrections must be an array of at most 500 items.")
        included = payload["included_claim_ids"]
        if not isinstance(included, list) or any(not isinstance(value, str) for value in included) or len(included) != len(set(included)):
            raise APIError("included_claim_ids must contain unique claim IDs.")
        if decision == "include" and not included:
            raise APIError("Include at least one supported claim in an included brief.")
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidates = self.candidates(connection)
            candidate = candidates.get(cid)
            if candidate is None:
                raise APIError("Candidate not found.", 404, "not_found")
            history = self.histories(connection)
            current_revision = history.get(cid, [{}])[-1].get("revision", 0)
            if current_revision != revision:
                raise APIError("Another review was saved. Reload the candidate before saving your changes.", 409, "revision_conflict")
            target = payload["duplicate_of"]
            if decision == "duplicate":
                if not isinstance(target, str) or target not in candidates or target == cid:
                    raise APIError("Choose a different existing candidate as the duplicate target.")
                if history.get(target, [{}])[-1].get("decision") == "duplicate":
                    raise APIError("Duplicate chains are not supported. Link to the original candidate.")
                if any(rows[-1].get("duplicate_of") == cid for rows in history.values()):
                    raise APIError("Other duplicates already point here. Keep this candidate as their original.")
            elif target is not None:
                raise APIError("duplicate_of must be null unless decision is duplicate.")
            claims = {claim["id"]: claim for claim in candidate["claims"]}
            sources = {source["id"]: source for source in candidate["sources"]}
            if not set(included) <= claims.keys():
                raise APIError("Included claim ID does not belong to this candidate.")
            corrections, corrected_ids = [], set()
            for item in payload["corrections"]:
                require_fields(item, {"claim_id", "text", "event_date", "source_id", "excerpt", "locator"})
                claim_id = item["claim_id"]
                if not isinstance(claim_id, str) or claim_id not in claims or claim_id in corrected_ids:
                    raise APIError("Correction has an unknown or repeated claim ID.")
                source_id = item["source_id"]
                if not isinstance(source_id, str) or source_id not in sources:
                    raise APIError("Correction source does not belong to this candidate.")
                correction = {"claim_id": claim_id, "text": string(item["text"], "correction text"),
                              "event_date": iso_date(item["event_date"], "correction event_date"),
                              "source_id": source_id, "excerpt": string(item["excerpt"], "correction excerpt"),
                              "locator": string(item["locator"], "correction locator", 2000)}
                capture = connection.execute("SELECT source_text FROM intakes WHERE id=?", (cid,)).fetchone()
                if capture and correction["excerpt"] not in capture[0]:
                    raise APIError("Correction excerpt is not present in the saved intake text.")
                source_capture = connection.execute("SELECT source_text FROM rights_source_texts WHERE candidate_id=? AND source_id=?", (cid, source_id)).fetchone()
                if source_capture and correction["excerpt"] not in source_capture[0]:
                    raise APIError("Correction excerpt is not present in this source's saved structured-intake text.")
                corrected_ids.add(claim_id)
                corrections.append(correction)
            review = {"candidate_id": cid, "revision": revision + 1, "reviewer": reviewer,
                      "reviewed_at": now(), "decision": decision, "reason": reason,
                      "duplicate_of": target, "corrections": corrections, "included_claim_ids": included,
                      "scope": "Human triage only; no whole-card factual approval or current-status verification."}
            connection.execute("INSERT INTO reviews VALUES (?,?,?)", (cid, review["revision"], encoded(review)))
        return review

    def intake(self, payload):
        fields = {"title", "person", "country", "source_title", "url", "publisher", "publication_date", "source_text", "summary", "excerpt", "locator"}
        require_fields(payload, fields)
        values = {key: string(payload[key], key, 500000 if key == "source_text" else 12000) for key in fields - {"publication_date"}}
        public_url(values["url"])
        country = string(values["country"], "country", 100)
        publication_date = iso_date(payload["publication_date"], "publication_date")
        if values["excerpt"] not in values["source_text"]:
            raise APIError("The exact excerpt must appear in the supplied source text.")
        cid = "intake_" + uuid4().hex
        source_id, claim_id = "source_1", "claim_1"
        candidate = {"id": cid, "title": values["title"], "person": values["person"],
                     "proceeding": "Not independently established; manual intake", "country": country,
                     "material_type": "manual_intake", "as_of": None, "summary": values["summary"],
                     "suggested_decision": "uncertain", "review_reasons": ["Manual intake; not AI extracted. A reviewer must assess relevance and source support."],
                     "unknowns": ["Current case status, source authenticity, proceeding identity, and substantive support have not been independently checked."],
                     "sources": [{"id": source_id, "title": values["source_title"], "publisher": values["publisher"], "url": values["url"],
                                  "publication_date": publication_date, "retrieved_at": now(), "language": "und",
                                  "translation_status": "Not recorded; user supplied text", "access_note": "User-supplied text saved locally; URL was not fetched. Timestamp records intake, not web retrieval.",
                                  "lineage_note": "Unknown; independent corroboration not established."}],
                     "claims": [{"id": claim_id, "text": values["summary"], "source_id": source_id,
                                 "excerpt": values["excerpt"], "locator": values["locator"], "event_date": None,
                                 "date_note": "Event date unknown; publication date is not substituted.",
                                 "attribution": "User-entered summary of the supplied source; substantive support unverified."}],
                     "related_candidate_ids": [], "notes": ["Manual intake; not AI extracted. Exact excerpt matching confirms text presence only."]}
        validate_candidate(candidate)
        with self.connection() as connection:
            connection.execute("INSERT INTO intakes VALUES (?,?,?)", (cid, encoded(candidate), values["source_text"]))
        return candidate

    def export(self, cid):
        identifier(cid)
        state = self.state()
        candidate = next((value for value in state["candidates"] if value["id"] == cid), None)
        if candidate is None:
            raise APIError("Candidate not found.", 404, "not_found")
        review = state["reviews"].get(cid)
        return self.evidence_export(candidate, review)

    def evidence_export(self, candidate, review):
        """Build an evidence view from records read in the caller's transaction."""
        cid = candidate["id"]
        selected = review["included_claim_ids"] if review else [claim["id"] for claim in candidate["claims"]]
        corrections = {item["claim_id"]: item for item in review["corrections"]} if review else {}
        source_index = {source["id"]: source for source in candidate["sources"]}
        claims = []
        for original in candidate["claims"]:
            if original["id"] not in selected:
                continue
            displayed = dict(original)
            if original["id"] in corrections:
                correction = corrections[original["id"]]
                displayed.update({key: value for key, value in correction.items() if key != "claim_id"})
                displayed["verification"] = "Human correction; not independently verified."
                displayed["original"] = original
                # The legacy correction contract does not ask the reviewer to
                # classify the changed statement. Do not inherit the original
                # source's allegation/finding/position type after a source edit.
                displayed["attribution_kind"] = "analyst_proposition"
                displayed["attribution"] = "Human reviewer correction attributed to " + source_index[correction["source_id"]]["publisher"] + "; support not independently verified."
                displayed["date_note"] = "Human correction; date and source support not independently verified. Original date note retained below."
            else:
                displayed["verification"] = "Source-attributed candidate claim; not independently verified."
            claims.append(displayed)
        return {"schema_version": 1, "dataset": self.dataset, "candidate_id": cid,
                "title": candidate["title"], "person": candidate["person"], "proceeding": candidate["proceeding"],
                "country": candidate["country"], "material_type": candidate["material_type"], "as_of": candidate["as_of"],
                "brief_status": "human_triage_recorded" if review else "pending_draft",
                "current_review_status": {"status": "human_triage_recorded" if review else "pending",
                                          "revision": review["revision"] if review else 0,
                                          "reviewer": review["reviewer"] if review else None,
                                          "included_claim_ids": review["included_claim_ids"] if review else [],
                                          "scope": review["scope"] if review else "No observations have a saved human triage decision."},
                "preparation_status_note": "Review reasons and notes retain preparation-time provenance. Current saved review status and exact selected observations are shown separately; pending-at-preparation text does not override later scoped decisions.",
                "review": review, "claims": claims,
                "sources": [source for source in candidate["sources"] if source["id"] in {claim["source_id"] for claim in claims} | {claim["original"]["source_id"] for claim in claims if "original" in claim}],
                "review_reasons": candidate["review_reasons"], "unknowns": candidate["unknowns"],
                "notes": candidate["notes"], "related_candidate_ids": candidate["related_candidate_ids"],
                "disclaimer": DISCLAIMER,
                "correction_policy": "Human corrections are unverified edits. Original claims remain available beside each correction and in immutable seed data. Duplicate decisions link candidates; they do not merge their claims."}

    def advocacy(self, cid, payload):
        identifier(cid)
        fields = {"expected_revision", "expected_review_revision", "analyst", "objective", "audience",
                  "requested_action", "rationale", "risks", "success_indicator", "follow_up_date", "additional_gaps"}
        require_fields(payload, fields)
        for field in ("expected_revision", "expected_review_revision"):
            if type(payload[field]) is not int or payload[field] < 0:
                raise APIError(f"{field} must be a nonnegative integer.")
        values = {field: string(payload[field], field, 200 if field == "analyst" else 8000,
                                blank=field == "additional_gaps")
                  for field in fields - {"expected_revision", "expected_review_revision", "follow_up_date"}}
        values["follow_up_date"] = iso_date(payload["follow_up_date"], "follow_up_date")
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidate = self.candidates(connection).get(cid)
            if candidate is None:
                raise APIError("Candidate not found.", 404, "not_found")
            current = connection.execute("SELECT revision FROM advocacy_plans WHERE candidate_id=? ORDER BY revision DESC LIMIT 1", (cid,)).fetchone()
            revision = current[0] if current else 0
            if revision != payload["expected_revision"]:
                raise APIError("Another advocacy plan was saved. Reload before saving your changes.", 409, "revision_conflict")
            row = connection.execute("SELECT record FROM reviews WHERE candidate_id=? ORDER BY revision DESC LIMIT 1", (cid,)).fetchone()
            review = json.loads(row[0]) if row else None
            if (review["revision"] if review else 0) != payload["expected_review_revision"]:
                raise APIError("The evidence review changed. Reload and inspect it before saving a plan.", 409, "review_revision_conflict")
            if not review or review["decision"] != "include":
                raise APIError("Save an include decision with supported statements before creating an advocacy plan.", 409, "review_required")
            snapshot = json.loads(encoded(self.evidence_export(candidate, review)))
            plan = {"candidate_id": cid, "revision": revision + 1, "review_revision": review["revision"],
                    "saved_at": now(), **values, "evidence_snapshot": snapshot,
                    "scope": "Analyst proposal; no outreach, factual certification, or demonstrated impact implied."}
            connection.execute("INSERT INTO advocacy_plans VALUES (?,?,?)", (cid, plan["revision"], encoded(plan)))
        return plan

    def followup(self, cid, payload):
        identifier(cid)
        require_fields(payload, {"expected_plan_revision", "author", "kind", "event_date", "text", "source_url", "excerpt", "locator"})
        revision = payload["expected_plan_revision"]
        if type(revision) is not int or revision < 1:
            raise APIError("expected_plan_revision must be a positive integer.")
        kind = payload["kind"]
        if not isinstance(kind, str) or kind not in {"planned_action", "completed_action", "observed_outcome"}:
            raise APIError("Invalid follow-up kind.")
        requires_evidence = kind != "planned_action"
        source_url = public_url(payload["source_url"]) if payload["source_url"] is not None else None
        if requires_evidence and source_url is None:
            raise APIError("Completed actions and observed outcomes require a source URL, exact excerpt, and locator.")
        values = {"author": string(payload["author"], "author", 200), "kind": kind,
                  "event_date": iso_date(payload["event_date"], "event_date"),
                  "text": string(payload["text"], "text", 8000), "source_url": source_url,
                  "excerpt": string(payload["excerpt"], "excerpt", 12000, blank=not requires_evidence),
                  "locator": string(payload["locator"], "locator", 2000, blank=not requires_evidence)}
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if cid not in self.candidates(connection):
                raise APIError("Candidate not found.", 404, "not_found")
            row = connection.execute("SELECT revision FROM advocacy_plans WHERE candidate_id=? ORDER BY revision DESC LIMIT 1", (cid,)).fetchone()
            if not row:
                raise APIError("Save an advocacy plan before recording follow-up.", 409, "plan_required")
            if row[0] != revision:
                raise APIError("The advocacy plan changed. Reload before recording follow-up.", 409, "revision_conflict")
            sequence = connection.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM followups WHERE candidate_id=?", (cid,)).fetchone()[0]
            entry = {"id": "followup_" + uuid4().hex, "candidate_id": cid, "sequence": sequence,
                     "plan_revision": revision, "recorded_at": now(), **values,
                     "provenance": ("Analyst-entered proposal; not a completed action." if kind == "planned_action" else
                                    "Author-entered source-attributed record; URL not fetched, excerpt and substantive support not independently verified."),
                     "causation_note": "Chronology does not establish causation. No impact measurement or causal attribution is made."}
            connection.execute("INSERT INTO followups VALUES (?,?,?)", (cid, sequence, encoded(entry)))
        return entry

    def advocacy_export(self, cid):
        identifier(cid)
        state = self.state()
        if cid not in {candidate["id"] for candidate in state["candidates"]}:
            raise APIError("Candidate not found.", 404, "not_found")
        plan = state["advocacy"].get(cid)
        if plan is None:
            raise APIError("Save an advocacy plan before exporting a briefing.", 409, "plan_required")
        snapshot = plan["evidence_snapshot"]
        review = state["reviews"].get(cid)
        current_revision = review["revision"] if review else 0
        timeline = {"dated": sorted((claim for claim in snapshot["claims"] if claim["event_date"]),
                                    key=lambda claim: (claim["event_date"], claim["id"])),
                    "undated": [claim for claim in snapshot["claims"] if claim["event_date"] is None]}
        return {"schema_version": 1, "document_type": "advocacy_brief", "candidate_id": cid,
                "title": snapshot["title"], "dataset": snapshot["dataset"],
                "material_type": snapshot["material_type"], "as_of": snapshot["as_of"],
                "exported_at": now(), "plan": plan, "evidence_timeline": timeline,
                "gaps": {"source_unknowns": snapshot["unknowns"],
                         "analyst_identified": [line.strip() for line in plan["additional_gaps"].splitlines() if line.strip()]},
                "followups": state["followups"].get(cid, []),
                "stale_review": current_revision != plan["review_revision"],
                "current_review_revision": current_revision, "current_review_decision": review["decision"] if review else None,
                "snapshot_policy": "Evidence is frozen at the saved plan's review revision. Later reviews do not silently change this plan. Re-save the plan after inspecting a changed review.",
                "current_status": "Unknown; historical reporting and recorded follow-up do not independently establish current case status.",
                "disclaimer": ADVOCACY_DISCLAIMER}

    def campaign(self, cid, payload):
        identifier(cid)
        require_fields(payload, {"expected_revision", "expected_review_revision", "analyst", "campaign_label", "objective",
                                 "interpretation", "alternative_explanations", "limitations", "codings"})
        for field in ("expected_revision", "expected_review_revision"):
            if type(payload[field]) is not int or payload[field] < 0:
                raise APIError(f"{field} must be a nonnegative integer.")
        values = {field: string(payload[field], field, 200 if field == "analyst" else 8000)
                  for field in ("analyst", "campaign_label", "objective", "interpretation", "alternative_explanations", "limitations")}
        if not isinstance(payload["codings"], list) or not 1 <= len(payload["codings"]) <= 500:
            raise APIError("codings must contain 1–500 classified statements.")
        codings, seen = [], set()
        for item in payload["codings"]:
            require_fields(item, {"claim_id", "category"})
            claim_id = identifier(item["claim_id"], "claim_id")
            category = item["category"]
            if not isinstance(category, str) or category not in CAMPAIGN_CATEGORIES:
                raise APIError("Unknown campaign evidence category.")
            if claim_id in seen:
                raise APIError("Code each selected statement exactly once; repeated claim ID.")
            seen.add(claim_id)
            codings.append({"claim_id": claim_id, "category": category})
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidate = self.candidates(connection).get(cid)
            if candidate is None:
                raise APIError("Candidate not found.", 404, "not_found")
            row = connection.execute("SELECT revision FROM campaign_analyses WHERE candidate_id=? ORDER BY revision DESC LIMIT 1", (cid,)).fetchone()
            revision = row[0] if row else 0
            if revision != payload["expected_revision"]:
                raise APIError("Another campaign analysis was saved. Reload before saving your changes.", 409, "revision_conflict")
            row = connection.execute("SELECT record FROM reviews WHERE candidate_id=? ORDER BY revision DESC LIMIT 1", (cid,)).fetchone()
            review = json.loads(row[0]) if row else None
            if (review["revision"] if review else 0) != payload["expected_review_revision"]:
                raise APIError("The evidence review changed. Reload and inspect it before coding a campaign.", 409, "review_revision_conflict")
            if not review or review["decision"] != "include":
                raise APIError("Save an include decision with supported statements before comparing a campaign.", 409, "review_required")
            if seen != set(review["included_claim_ids"]):
                raise APIError("Code every selected statement exactly once; omit unselected and unknown statements.")
            snapshot = json.loads(encoded(self.evidence_export(candidate, review)))
            record = {"candidate_id": cid, "revision": revision + 1, "review_revision": review["revision"],
                      "saved_at": now(), **values, "codings": codings, "evidence_snapshot": snapshot,
                      "coding_method": "Analyst-coded categories; not AI extraction. Coding does not certify source support or causal relationships."}
            connection.execute("INSERT INTO campaign_analyses VALUES (?,?,?)", (cid, record["revision"], encoded(record)))
        return record

    def campaign_export(self):
        state = self.state()
        if not state["campaigns"]:
            raise APIError("Save at least one campaign analysis before exporting a comparison.", 409, "campaign_required")
        campaigns, all_urls = [], set()
        # Match the dossier order shown in the workspace; this order is not a ranking.
        for candidate in state["candidates"]:
            cid = candidate["id"]
            analysis = state["campaigns"].get(cid)
            if analysis is None:
                continue
            snapshot = analysis["evidence_snapshot"]
            sources = {source["id"]: source for source in snapshot["sources"]}
            claims = {claim["id"]: claim for claim in snapshot["claims"]}
            grouped = {category: [] for category in CAMPAIGN_CATEGORIES}
            for coding in analysis["codings"]:
                claim = claims[coding["claim_id"]]
                grouped[coding["category"]].append({**claim, "source": sources[claim["source_id"]],
                                                    "category": coding["category"], "classification": "Analyst coding; source support unverified"})
            timelines = {category: {"dated": sorted((claim for claim in entries if claim["event_date"]),
                                                   key=lambda claim: (claim["event_date"], claim["id"])),
                                    "undated": [claim for claim in entries if claim["event_date"] is None]}
                         for category, entries in grouped.items()}
            category_summary = {category: {"count": len(entries), "status": "documented_in_selected_evidence" if entries else "not_documented_in_selected_evidence"}
                                for category, entries in grouped.items()}
            review = state["reviews"].get(cid)
            current_revision = review["revision"] if review else 0
            urls = {source["url"] for source in snapshot["sources"]}
            all_urls |= urls
            dates = sorted(claim["event_date"] for claim in claims.values() if claim["event_date"] is not None)
            campaigns.append({"candidate_id": cid, "campaign_label": analysis["campaign_label"], "analysis": analysis,
                              "material_type": snapshot["material_type"], "as_of": snapshot["as_of"],
                              "stale_review": current_revision != analysis["review_revision"],
                              "review_no_longer_included": not review or review["decision"] != "include",
                              "current_review_revision": current_revision, "current_review_decision": review["decision"] if review else None,
                              "category_summary": category_summary, "timelines": timelines,
                              "outcomes": {category: {"evidence_status": category_summary[category]["status"],
                                                      "claim_ids": [claim["id"] for claim in grouped[category]],
                                                      "meaning": (("Reported policy proposal, decision, or implementation stage; not adopted policy by default or proof of campaign effect"
                                                                   if category == "policy_outcome" else "Reported outcome evidence, not proof of campaign effect")
                                                                  if grouped[category] else "Unknown; absence of selected evidence does not establish no outcome or development")}
                                           for category in ("legal_outcome", "policy_outcome")},
                              "unique_source_count": len(urls), "coded_observation_count": len(claims),
                              "known_event_range": {"start": dates[0], "end": dates[-1]} if dates else None,
                              "unknown_event_dates": sum(claim["event_date"] is None for claim in claims.values())})
        return {"schema_version": 1, "document_type": "campaign_evidence_comparison", "dataset": state["dataset"],
                "exported_at": now(), "campaigns": campaigns, "category_labels": CAMPAIGN_CATEGORIES,
                "summary": {"campaign_dossiers": len(campaigns),
                            "coded_observations": sum(item["coded_observation_count"] for item in campaigns),
                            "unique_cited_sources": len(all_urls)},
                "comparison_scope": "Latest saved analysis per dossier. All prior revisions are retained in local history. Dossiers are not automatically distinct cases.",
                "counting_method": "Observations count selected coded statements. Sources count distinct exact cited URLs, including preserved correction originals; neither is a reach or impact measure.",
                "date_policy": "Known event range covers only dated selected statements, not campaign duration. Unknown dates remain separate; publication dates are not substituted.",
                "snapshot_policy": "Each analysis preserves its saved review snapshot. Later reviews flag it stale without silently changing the comparison.",
                "disclaimer": CAMPAIGN_DISCLAIMER, "limitations": CAMPAIGN_LIMITATIONS}


def markdown_text(value):
    text = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", text)


def evidence_markdown_rows(claims, source_list, heading_level=3):
    """Shared citation rendering keeps source limits and correction originals in both exports."""
    m = markdown_text
    rows = []
    sources = {source["id"]: source for source in source_list}
    for index, claim in enumerate(claims, 1):
        source = sources[claim["source_id"]]
        destination = quote(source["url"], safe=":/?#[]@!$&'*+,;=%")
        rows += ["#" * heading_level + f" {index}. " + m(claim["text"]), "", "Attribution: " + m(claim["attribution"]), "",
                 "Event date: " + m(claim["event_date"] or "unknown") + ". " + m(claim["date_note"]), "",
                 "Source: [" + m(source["title"]) + "](" + destination + ") — " + m(source["publisher"]), "",
                 "Published: " + m(source["publication_date"] or "unknown") + "; captured/recorded: " + m(source["retrieved_at"] or "not recorded"), "",
                 "Exact excerpt: " + m(claim["excerpt"]), "", "Locator: " + m(claim["locator"]), "",
                 "Verification: " + m(claim["verification"]), "",
                 "Source limits: " + m(source["access_note"]) + " " + m(source["lineage_note"]), "",
                 "Language/translation: " + m(source["language"]) + "; " + m(source["translation_status"]), ""]
        if "original" in claim:
            original = claim["original"]
            original_source = sources[original["source_id"]]
            original_url = quote(original_source["url"], safe=":/?#[]@!$&'*+,;=%")
            rows += ["**Original statement preserved:** " + m(original["text"]), "",
                     "Original attribution: " + m(original["attribution"]), "",
                     "Original event date: " + m(original["event_date"] or "unknown") + ". " + m(original["date_note"]), "",
                     "Original source: [" + m(original_source["title"]) + "](" + original_url + ") — " + m(original_source["publisher"]) + "; excerpt: " + m(original["excerpt"]) + "; locator: " + m(original["locator"]), "",
                     "Original source published: " + m(original_source["publication_date"] or "unknown") + "; captured/recorded: " + m(original_source["retrieved_at"] or "not recorded"), "",
                     "Original source limits: " + m(original_source["access_note"]) + " " + m(original_source["lineage_note"]), "",
                     "Original language/translation: " + m(original_source["language"]) + "; " + m(original_source["translation_status"]), ""]
    return rows


def render_markdown(brief):
    m = markdown_text
    rows = ["# " + m(brief["title"]), "", "**Material: " + m(brief["material_type"]) + "**",
            "", "Status: " + m(brief["brief_status"]), "", DISCLAIMER, "",
            "Dataset: " + m(brief["dataset"]["label"]), "",
            "Country: " + m(brief["country"]) + " · Person: " + m(brief["person"]), "",
            "Proceeding: " + m(brief["proceeding"]), "", "As of: " + m(brief["as_of"] or "unknown"), ""]
    review = brief["review"]
    if review:
        rows += ["## Human triage", "", "Decision: " + m(review["decision"]), "",
                 "Reviewer: " + m(review["reviewer"]) + " · " + m(review["reviewed_at"]) + " · Revision " + str(review["revision"]),
                 "", "Reason: " + m(review["reason"]), "",
                 "Exact selected observation IDs: " + m(", ".join(review["included_claim_ids"]) or "none"), "", m(review["scope"]), ""]
        if review["duplicate_of"]:
            rows += ["Duplicate of: " + m(review["duplicate_of"]) + ". Linked only; no claims merged.", ""]
    else:
        rows += ["**Pending draft: no human decision has been recorded.**", ""]
    rows += ["## Selected evidence-backed statements", ""]
    rows += evidence_markdown_rows(brief["claims"], brief["sources"])
    if not brief["claims"]:
        rows += ["No claims selected for this brief.", ""]
    rows += [brief.get("preparation_status_note", "Preparation-time notes and current scoped human decisions are separate."), ""]
    for title, items in (("Preparation-time review reasons", brief["review_reasons"]), ("Still unknown", brief["unknowns"]), ("Preparation provenance and notes", brief["notes"])):
        rows += ["## " + title, ""] + ["- " + m(item) for item in items] + [""]
    rows += [brief["correction_policy"], ""]
    return "\n".join(rows)


def render_advocacy_markdown(brief):
    m = markdown_text
    plan = brief["plan"]
    evidence = plan["evidence_snapshot"]
    review = evidence["review"]
    rows = ["# Advocacy briefing: " + m(brief["title"]), "",
            "**Material: " + m(brief["material_type"]) + "** · Dataset: " + m(brief["dataset"]["label"]), "",
            ADVOCACY_DISCLAIMER, "", "Current status: " + m(brief["current_status"]), "",
            "Country: " + m(evidence["country"]) + " · Person: " + m(evidence["person"]), "",
            "Proceeding: " + m(evidence["proceeding"]) + " · Evidence as of: " + m(evidence["as_of"] or "unknown"), "",
            "Plan revision: " + str(plan["revision"]) + " · Evidence review revision: " + str(plan["review_revision"]), "",
            "Analyst: " + m(plan["analyst"]) + " · Plan saved: " + m(plan["saved_at"]) + " · Exported: " + m(brief["exported_at"]), "",
            "stale_review: " + str(brief["stale_review"]).lower() + " · Current review revision: " + str(brief["current_review_revision"]), ""]
    if brief["stale_review"]:
        rows += ["**REVIEW CHANGED: this plan retains an earlier evidence snapshot. Inspect the latest review and re-save the plan before relying on it.**", "",
                 "Latest review decision: " + m(brief["current_review_decision"] or "unknown"), ""]
    rows += [brief["snapshot_policy"], "", "## Analyst proposal", "",
             "The following choices and rationale are analyst judgments and proposals, not source-attributed facts.", ""]
    for field, label in (("objective", "Objective"), ("audience", "Audience"), ("requested_action", "Requested action"),
                         ("rationale", "Rationale"), ("risks", "Risks and safeguards"), ("success_indicator", "What to look for next")):
        rows += ["### " + label, "", m(plan[field]), ""]
    rows += ["Follow-up date: " + m(plan["follow_up_date"] or "not scheduled"), "",
             "An intended success indicator is a future observation to seek, not evidence of achieved impact.", "",
             "## Evidence gaps", "", "### Unknowns retained from the evidence", ""]
    rows += ["- " + m(item) for item in brief["gaps"]["source_unknowns"]] or ["No additional unknowns recorded; this is not a finding of completeness."]
    rows += ["", "### Analyst-identified gaps", ""]
    rows += ["- " + m(item) for item in brief["gaps"]["analyst_identified"]] or ["None recorded."]
    rows += ["", "## Dated evidence timeline", "",
             "Selected source-attributed statements, ordered by stated event date. Publication and retrieval dates remain distinct.", ""]
    rows += evidence_markdown_rows(brief["evidence_timeline"]["dated"], evidence["sources"]) or ["No selected statements have a known event date.", ""]
    rows += ["## Event date unknown", "", "Publication dates are not substituted for unknown event dates.", ""]
    rows += evidence_markdown_rows(brief["evidence_timeline"]["undated"], evidence["sources"]) or ["No selected undated statements.", ""]
    rows += ["## Follow-up and observed changes", "",
             "Entries appear in recorded order. Event date is separate from recorded time. Chronology does not establish causation.", ""]
    for entry in brief["followups"]:
        rows += ["### " + str(entry["sequence"]) + ". " + m(entry["kind"].replace("_", " ")), "",
                 m(entry["text"]), "", "Author: " + m(entry["author"]) + " · Plan revision: " + str(entry["plan_revision"]), "",
                 "Event date: " + m(entry["event_date"] or "unknown") + " · Recorded: " + m(entry["recorded_at"]), "",
                 "Provenance: " + m(entry["provenance"]), ""]
        if entry["source_url"]:
            rows += ["Source: [supplied source](" + quote(entry["source_url"], safe=":/?#[]@!$&'*+,;=%") + ")", ""]
        if entry["excerpt"]:
            rows += ["Exact excerpt: " + m(entry["excerpt"]), ""]
        if entry["locator"]:
            rows += ["Locator: " + m(entry["locator"]), ""]
    if not brief["followups"]:
        rows += ["No follow-up entries recorded. No intervention or outcome is implied.", ""]
    rows += ["## Evidence review and provenance", "",
             "Reviewer: " + m(review["reviewer"]) + " · Recorded: " + m(review["reviewed_at"]), "",
             "Decision: " + m(review["decision"]) + " · Reason: " + m(review["reason"]), "",
             m(review["scope"]), "", "Related candidate links: " + m(", ".join(evidence["related_candidate_ids"]) or "none") + ". Links do not merge evidence.", ""]
    rows += ["- " + m(item) for item in evidence["notes"]] + ["", evidence["correction_policy"], ""]
    return "\n".join(rows)


def render_campaign_markdown(comparison):
    m = markdown_text
    summary = comparison["summary"]
    categories = comparison["category_labels"]
    changed = sum(item["stale_review"] or item["review_no_longer_included"] for item in comparison["campaigns"])
    rows = ["# Campaign evidence comparison", "", "Dataset: " + m(comparison["dataset"]["label"]), "",
            "Exported: " + m(comparison["exported_at"]), "", comparison["disclaimer"], "",
            str(summary["campaign_dossiers"]) + " saved campaign dossiers · " + str(summary["coded_observations"]) +
            " coded observations · " + str(summary["unique_cited_sources"]) + " distinct cited source URLs", "",
            comparison["comparison_scope"], "", comparison["counting_method"], ""]
    if changed:
        rows += ["**REVIEW CHANGED: " + str(changed) + " saved dossier(s) use an earlier or no-longer-included evidence review. Their table labels are flagged; reconcile the current review before relying on the comparison.**", ""]
    rows += ["## Comparison of documented evidence", "",
            "Documented means selected evidence has been assigned this category by an analyst. Unknown means no selected statement was coded here; it does not mean the activity or outcome was absent.", "",
            "| Campaign dossier | Social media | International attention | Campaign action | Legal outcome | Policy development evidence |",
            "| --- | --- | --- | --- | --- | --- |"]
    for item in comparison["campaigns"]:
        review_flag = " **[REVIEW CHANGED]**" if item["stale_review"] or item["review_no_longer_included"] else ""
        cells = [m(item["campaign_label"]) + review_flag]
        for category in ("social_media", "international_attention", "campaign_action", "legal_outcome", "policy_outcome"):
            count = item["category_summary"][category]["count"]
            cells.append("Documented (" + str(count) + ")" if count else "Unknown")
        rows.append("| " + " | ".join(cells) + " |")
    rows += ["", "Counts describe evidence, not reach or effectiveness. Reported legal or policy changes are not attributed to a campaign.", "",
             "Policy development evidence may document a proposal, decision, or implementation stage. It does not establish adopted policy by default; inspect each statement's stage and qualifications.", "",
             "## Limits on comparison", ""]
    rows += ["- " + m(value) for value in comparison["limitations"]]
    rows += ["", comparison["date_policy"], "", comparison["snapshot_policy"], ""]
    for item in comparison["campaigns"]:
        analysis = item["analysis"]
        snapshot = analysis["evidence_snapshot"]
        review = snapshot["review"]
        rows += ["## " + m(item["campaign_label"]), "", "**Material: " + m(item["material_type"]) + "**", "",
                 "Dossier: " + m(snapshot["title"]) + " · Country: " + m(snapshot["country"]) + " · Person: " + m(snapshot["person"]), "",
                 "Proceeding: " + m(snapshot["proceeding"]) + " · Source evidence as of: " + m(item["as_of"] or "unknown"), "",
                 "Analysis revision: " + str(analysis["revision"]) + " · Saved review revision: " + str(analysis["review_revision"]), "",
                 "Analyst: " + m(analysis["analyst"]) + " · Saved: " + m(analysis["saved_at"]), "",
                 "stale_review: " + str(item["stale_review"]).lower() + " · review_no_longer_included: " + str(item["review_no_longer_included"]).lower(), ""]
        if item["stale_review"] or item["review_no_longer_included"]:
            rows += ["**REVIEW CHANGED: this analysis retains an earlier evidence snapshot. Reconcile the latest review before relying on it.**", "",
                     "Current review revision: " + str(item["current_review_revision"]) + " · Decision: " + m(item["current_review_decision"] or "unknown"), ""]
        rows += ["### Analyst judgments", "", "The objective, interpretation, alternatives, and limitations below are analyst-entered judgments, not source-attributed facts.", ""]
        for field, label in (("objective", "Campaign objective under comparison"), ("interpretation", "Interpretation of the evidence"),
                             ("alternative_explanations", "Alternative explanations"), ("limitations", "Dossier limitations")):
            rows += ["**" + label + ":** " + m(analysis[field]), ""]
        rows += [analysis["coding_method"], "", "### Evidence coverage and unresolved gaps", "",
                 str(item["coded_observation_count"]) + " coded observations · " + str(item["unique_source_count"]) +
                 " distinct cited source URLs · " + str(item["unknown_event_dates"]) + " unknown event dates", ""]
        date_range = item["known_event_range"]
        rows += ["Known event-date range: " + (m(date_range["start"]) + " to " + m(date_range["end"]) if date_range else "unknown") + ". This is evidence coverage, not campaign duration.", ""]
        rows += ["- " + m(value) for value in snapshot["unknowns"]] + [""]
        for category, label in categories.items():
            timeline = item["timelines"][category]
            rows += ["### " + label, ""]
            if not timeline["dated"] and not timeline["undated"]:
                rows += ["Unknown: no selected statement was coded in this category. No absence of activity or outcome is inferred.", ""]
                continue
            if category == "policy_outcome":
                rows += ["Source-reported policy proposal, decision, or implementation stage. Adoption and implementation are not assumed; no campaign effect is established.", ""]
            elif category == "legal_outcome":
                rows += ["Source-attributed reported outcome evidence; no campaign effect is established.", ""]
            if timeline["dated"]:
                rows += ["#### Known event dates, earliest first", ""]
                rows += evidence_markdown_rows(timeline["dated"], snapshot["sources"], heading_level=5)
            if timeline["undated"]:
                rows += ["#### Event date unknown", "", "Publication dates are not substituted for event dates.", ""]
                rows += evidence_markdown_rows(timeline["undated"], snapshot["sources"], heading_level=5)
        rows += ["### Saved review provenance", "", "Reviewer: " + m(review["reviewer"]) + " · Recorded: " + m(review["reviewed_at"]), "",
                 "Decision: " + m(review["decision"]) + " · Reason: " + m(review["reason"]), "", m(review["scope"]), "",
                 "Related dossier links: " + m(", ".join(snapshot["related_candidate_ids"]) or "none") + ". Links do not merge cases or evidence.", ""]
        rows += ["- " + m(value) for value in snapshot["notes"]] + ["", snapshot["correction_policy"], ""]
    return "\n".join(rows)


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, store, port=8765, static_dir=None):
        self.store = store
        self.static_dir = Path(static_dir or Path(__file__).parent / "static").resolve()
        super().__init__(("127.0.0.1", port), ReviewHandler)


class ReviewHandler(BaseHTTPRequestHandler):
    server_version = "TrialWatchReviewDesk/1"

    def safe_request(self, writing=False):
        host = self.headers.get("Host", "").lower()
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if port == 80:
            allowed |= {"127.0.0.1", "localhost"}
        if host not in allowed:
            raise APIError("Only the local review desk host is permitted.", 403, "invalid_host")
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + value for value in allowed}:
            raise APIError("Cross-origin requests are not permitted.", 403, "invalid_origin")
        if writing and self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise APIError("Cross-site writes are not permitted.", 403, "invalid_origin")

    def respond(self, status, body, content_type="application/json; charset=utf-8", filename=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, status, value):
        self.respond(status, encoded(value))

    def handle_error(self, error):
        self.json_response(error.status, {"error": str(error), "code": error.code})

    def do_GET(self):
        try:
            self.safe_request()
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            if path == "/api/health":
                return self.json_response(200, {"status": "ok", "mode": "local_saved_evidence_and_manual_review"})
            if path == "/api/state":
                return self.json_response(200, self.server.store.state())
            if path == "/api/rights/rubric":
                from .rights import RUBRIC_VERSION, rubric_for
                version = parse_qs(parsed.query).get("version", [RUBRIC_VERSION])[0]
                return self.json_response(200, rubric_for(version))
            if path == "/api/rights/state":
                return self.json_response(200, {**self.server.store.state(), "rights": self.server.store.rights.state()})
            if path.startswith("/api/rights/source-text/"):
                parts = path.removeprefix("/api/rights/source-text/").split("/")
                if len(parts) != 2:
                    raise APIError("Source route requires a case and source ID.", 404, "not_found")
                document = self.server.store.rights.retained_source(*parts)
                source = document["source"]
                e = html.escape
                body = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                        '<meta name="viewport" content="width=device-width,initial-scale=1">'
                        '<title>' + e(source["title"]) + ' · Retained source</title>'
                        '<link rel="stylesheet" href="/rights.css"></head><body>'
                        '<main class="retained-source-page"><a href="/rights.html?case=' + quote(parts[0], safe="") + '&amp;tab=evidence">Back to case evidence</a>'
                        '<p class="eyebrow">RETAINED SUPPLIED TEXT</p><h1>' + e(source["title"]) + '</h1>'
                        '<p class="retained-source-metadata">' + e(source["publisher"]) + '<br>'
                        + e(source["language"]) + ' · ' + e(source["translation_status"]) + '</p>'
                        '<details><summary>Source provenance</summary><p>' + e(source["access_note"]) + '</p><p>'
                        + e(source["lineage_note"]) + '</p></details>'
                        '<p>Search this text with your browser’s Find command. Check the supplied document copy for layout, comments, signatures and original page numbering.</p>'
                        '<pre aria-label="Retained source text">' + e(document["text"]) + '</pre></main></body></html>')
                return self.respond(200, body, "text/html; charset=utf-8")
            if path.startswith("/api/ai-drafts/state/"):
                return self.json_response(200, self.server.store.ai_drafts.state(path.removeprefix("/api/ai-drafts/state/")))
            if path.startswith("/api/ai-drafts/export/"):
                from .ai_drafts import render_draft_markdown
                did = path.removeprefix("/api/ai-drafts/export/")
                format_name = parse_qs(parsed.query).get("format", ["md"])[0]
                if format_name not in {"md", "json"}:
                    raise APIError("Export format must be md or json.")
                document = self.server.store.ai_drafts.export(did)
                body = render_draft_markdown(document) if format_name == "md" else json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                return self.respond(200, body, "text/markdown; charset=utf-8" if format_name == "md" else "application/json; charset=utf-8", f"{did}.pending-draft.{format_name}")
            if path.startswith("/api/interventions/state/"):
                return self.json_response(200, self.server.store.interventions.state(path.removeprefix("/api/interventions/state/")))
            if path.startswith("/api/interventions/export/"):
                from .intervention import render_intervention_markdown
                rid = path.removeprefix("/api/interventions/export/")
                format_name = parse_qs(parsed.query).get("format", ["md"])[0]
                if format_name not in {"md", "json"}:
                    raise APIError("Export format must be md or json.")
                document = self.server.store.interventions.export(rid)
                body = render_intervention_markdown(document) if format_name == "md" else json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                content_type = "text/markdown; charset=utf-8" if format_name == "md" else "application/json; charset=utf-8"
                return self.respond(200, body, content_type, f"{rid}.intervention.{format_name}")
            if path.startswith("/api/rights/export/"):
                from .rights import render_rights_markdown
                cid = path.removeprefix("/api/rights/export/")
                format_name = parse_qs(parsed.query).get("format", ["md"])[0]
                if format_name not in {"md", "json"}:
                    raise APIError("Export format must be md or json.")
                profile = self.server.store.rights.export(cid)
                body = render_rights_markdown(profile) if format_name == "md" else json.dumps(profile, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                content_type = "text/markdown; charset=utf-8" if format_name == "md" else "application/json; charset=utf-8"
                return self.respond(200, body, content_type, f"{cid}.rights.{format_name}")
            if path == "/api/campaign-export":
                format_name = parse_qs(parsed.query).get("format", ["md"])[0]
                if format_name not in {"md", "json"}:
                    raise APIError("Export format must be md or json.")
                comparison = self.server.store.campaign_export()
                body = render_campaign_markdown(comparison) if format_name == "md" else json.dumps(comparison, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                content_type = "text/markdown; charset=utf-8" if format_name == "md" else "application/json; charset=utf-8"
                return self.respond(200, body, content_type, f"campaign-comparison.{format_name}")
            if path.startswith("/api/advocacy-export/"):
                cid = path.removeprefix("/api/advocacy-export/")
                format_name = parse_qs(parsed.query).get("format", ["md"])[0]
                if format_name not in {"md", "json"}:
                    raise APIError("Export format must be md or json.")
                brief = self.server.store.advocacy_export(cid)
                body = render_advocacy_markdown(brief) if format_name == "md" else json.dumps(brief, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                content_type = "text/markdown; charset=utf-8" if format_name == "md" else "application/json; charset=utf-8"
                return self.respond(200, body, content_type, f"{cid}.advocacy.{format_name}")
            if path.startswith("/api/export/"):
                cid = path.removeprefix("/api/export/")
                format_name = parse_qs(parsed.query).get("format", ["md"])[0]
                if format_name not in {"md", "json"}:
                    raise APIError("Export format must be md or json.")
                brief = self.server.store.export(cid)
                body = render_markdown(brief) if format_name == "md" else json.dumps(brief, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                content_type = "text/markdown; charset=utf-8" if format_name == "md" else "application/json; charset=utf-8"
                return self.respond(200, body, content_type, f"{cid}.brief.{format_name}")
            if path.startswith("/api/"):
                raise APIError("Route not found.", 404, "not_found")
            relative = ("rights.html" if self.server.store.has_rights_seed else "index.html") if path == "/" else path.lstrip("/")
            if "\\" in path or "\x00" in path or ".." in Path(relative).parts:
                raise APIError("Invalid static path.", 404, "not_found")
            target = (self.server.static_dir / relative).resolve()
            if (self.server.static_dir not in target.parents or not target.is_file()
                    or target.suffix not in {".html", ".js", ".css", ".svg", ".png", ".ico"}):
                raise APIError("File not found.", 404, "not_found")
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".js":
                content_type = "text/javascript"
            return self.respond(200, target.read_bytes(), content_type + "; charset=utf-8")
        except APIError as exc:
            self.handle_error(exc)
        except (OSError, sqlite3.Error):
            self.handle_error(APIError("Local storage is unavailable; no successful save was confirmed.", 503, "storage_error"))

    def do_POST(self):
        try:
            self.safe_request(writing=True)
            if self.headers.get_content_type() != "application/json":
                raise APIError("Writes require application/json.", 415, "content_type")
            if self.headers.get("Transfer-Encoding"):
                raise APIError("Transfer encoding is not supported.")
            try:
                length = int(self.headers.get("Content-Length", "-1"))
            except ValueError as exc:
                raise APIError("Invalid Content-Length.") from exc
            if not 0 <= length <= MAX_BODY:
                raise APIError("Request body exceeds the 1 MiB limit or has no length.", 413, "body_size")
            self.connection.settimeout(10)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise APIError("Incomplete request body.")
            payload = decode(raw)
            path = unquote(urlsplit(self.path).path)
            if path == "/api/intake":
                return self.json_response(201, self.server.store.intake(payload))
            if path == "/api/rights/intake":
                return self.json_response(201, self.server.store.rights.intake(payload))
            if path in {"/api/judgments/inspect", "/api/judgments/preview"}:
                from .judgment_import import inspect_judgment, preview_judgment
                with self.server.store.connection() as connection:
                    existing = list(self.server.store.candidates(connection).values())
                prepare = inspect_judgment if path.endswith("/inspect") else preview_judgment
                return self.json_response(200, prepare(payload, existing))
            if path.startswith("/api/ai-drafts/import/"):
                return self.json_response(201, self.server.store.ai_drafts.import_draft(path.removeprefix("/api/ai-drafts/import/"), payload))
            if path.startswith("/api/ai-drafts/live/"):
                return self.json_response(201, self.server.store.ai_drafts.live(path.removeprefix("/api/ai-drafts/live/"), payload))
            if path.startswith("/api/ai-drafts/addenda/"):
                return self.json_response(201, self.server.store.ai_drafts.addendum(path.removeprefix("/api/ai-drafts/addenda/"), payload))
            if path.startswith("/api/ai-drafts/source-reviews/"):
                return self.json_response(201, self.server.store.ai_drafts.source_review(path.removeprefix("/api/ai-drafts/source-reviews/"), payload))
            if path.startswith("/api/ai-drafts/worksheet/"):
                return self.json_response(201, self.server.store.ai_drafts.worksheet(path.removeprefix("/api/ai-drafts/worksheet/"), payload))
            if path.startswith("/api/interventions/contexts/"):
                return self.json_response(201, self.server.store.interventions.context(path.removeprefix("/api/interventions/contexts/"), payload))
            if path.startswith("/api/interventions/proposals/"):
                return self.json_response(201, self.server.store.interventions.propose(path.removeprefix("/api/interventions/proposals/"), payload))
            if path.startswith("/api/interventions/reviews/"):
                return self.json_response(201, self.server.store.interventions.review(path.removeprefix("/api/interventions/reviews/"), payload))
            if path.startswith("/api/interventions/followups/"):
                return self.json_response(201, self.server.store.interventions.followup(path.removeprefix("/api/interventions/followups/"), payload))
            if path.startswith("/api/rights/draft/"):
                return self.json_response(200, self.server.store.rights.draft(path.removeprefix("/api/rights/draft/"), payload))
            if path.startswith("/api/rights/evidence-additions/"):
                return self.json_response(201, self.server.store.rights.add_evidence(path.removeprefix("/api/rights/evidence-additions/"), payload))
            if path.startswith("/api/rights/assessments/"):
                return self.json_response(201, self.server.store.rights.save(path.removeprefix("/api/rights/assessments/"), payload))
            if path.startswith("/api/rights/reviews/"):
                return self.json_response(201, self.server.store.rights.review(path.removeprefix("/api/rights/reviews/"), payload))
            if path.startswith("/api/reviews/"):
                return self.json_response(201, self.server.store.review(path.removeprefix("/api/reviews/"), payload))
            if path.startswith("/api/campaigns/"):
                return self.json_response(201, self.server.store.campaign(path.removeprefix("/api/campaigns/"), payload))
            if path.startswith("/api/advocacy/"):
                return self.json_response(201, self.server.store.advocacy(path.removeprefix("/api/advocacy/"), payload))
            if path.startswith("/api/followups/"):
                return self.json_response(201, self.server.store.followup(path.removeprefix("/api/followups/"), payload))
            raise APIError("Route not found.", 404, "not_found")
        except APIError as exc:
            self.handle_error(exc)
        except (OSError, sqlite3.Error):
            self.handle_error(APIError("Local storage is unavailable; no successful save was confirmed.", 503, "storage_error"))

    def log_message(self, format, *args):
        # Do not log user source text or review details.
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=Path(__file__).parent / "rights.synthetic.v2.json")
    parser.add_argument("--state-dir", type=Path, default=Path("data/processed/rightsdesk-v2"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--allow-live-draft", action="store_true", help="Enable at most one bounded local Codex request in this isolated state; default off.")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be 0–65535")
    try:
        store = ReviewStore(args.seed, args.state_dir)
        store.ai_drafts.allow_live = args.allow_live_draft
        server = ReviewServer(store, args.port)
    except (APIError, OSError, sqlite3.Error) as exc:
        parser.error(str(exc))
    print(f"Review desk: http://127.0.0.1:{server.server_port}/", flush=True)
    print(f"Local review storage: {store.path}", flush=True)
    print("Saved evidence/manual intake; bounded live draft " + ("enabled for one attempt" if args.allow_live_draft else "disabled") + "; no source collection or monitoring.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
