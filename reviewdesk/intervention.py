"""Append-only, explicit advocacy worksheets; no AI runtime or action execution."""
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from .server import APIError, encoded, identifier, iso_date, markdown_text, now, public_url, require_fields, string

VERSION = "intervention-decision/1"
DISPOSITIONS = ["intervene_now", "prepare_verify", "refer_coordinate", "defer", "against", "insufficient_basis"]
ROUTES = ["legal_support", "partner_coordination", "quiet_engagement", "public_advocacy", "policy_advocacy", "mechanism_referral", "verification", "deferral"]
TOPICS = {"procedure", "deadline", "issue", "affected_groups", "organization", "attention", "institution", "issue_position", "legal_opportunity", "capacity", "harm", "preferences", "party_label", "country_indicator", "historical_action", "historical_outcome"}
ORIGINS = {"manual", "ai_prepared", "synthetic_prepared"}
SOURCE_FIELDS = {"id", "title", "publisher", "url", "publication_date", "retrieved_at", "language", "translation_status", "access_note", "lineage_note"}
CLAIM_FIELDS = {"id", "topic", "text", "source_id", "excerpt", "locator", "relevant_date", "date_note", "attribution", "uncertainty", "freshness_note"}
REFERENCE_FIELDS = {"support_context_ids", "contrary_context_ids", "authority_context_ids", "timing_context_ids", "feasibility_context_ids", "harm_context_ids", "preferences_context_ids"}
OPTION_FIELDS = {"id", "label", "route", "actor", "authority", "objective", "beneficiary", "timing_window", "preconditions", "blocking_unknowns", "benefits", "harms", "alternative_explanations", "next_step", "reconsideration_trigger", "factors"} | REFERENCE_FIELDS
DISCLAIMER = "Local provisional decision support for human review, not an official TrialWatch recommendation, legal finding, probability or effectiveness estimate. Saving a proposal or followup executes no advocacy. Pending rights analysis remains pending; missing evidence and preferences remain unknown."


def enum(value, choices, field):
    if not isinstance(value, str) or value not in choices:
        raise APIError("Invalid " + field + ".")
    return value


def number(value, field):
    if type(value) is not int or value < 0:
        raise APIError(field + " must be a nonnegative integer.")
    return value


def ids(value, field):
    if not isinstance(value, list) or len(value) > 500:
        raise APIError(field + " must be an array of at most 500 IDs.")
    result = [identifier(x, field) for x in value]
    if len(result) != len(set(result)):
        raise APIError(field + " contains repeated IDs.")
    return result


def texts(value, field):
    if not isinstance(value, list) or len(value) > 100:
        raise APIError(field + " must be an array of at most 100 strings.")
    return [string(x, field, 8000) for x in value]


def source_record(source):
    require_fields(source, SOURCE_FIELDS)
    record = {key: string(source[key], key, 12000) for key in SOURCE_FIELDS - {"publication_date", "retrieved_at", "url", "id"}}
    record.update(id=identifier(source["id"]), url=public_url(source["url"]), publication_date=iso_date(source["publication_date"], "publication_date"), retrieved_at=None if source["retrieved_at"] is None else string(source["retrieved_at"], "retrieved_at", 200))
    return record


class InterventionService:
    def __init__(self, store):
        self.store = store
        with store.connection() as connection:
            connection.executescript("""
            CREATE TABLE IF NOT EXISTS intervention_contexts (candidate_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL, PRIMARY KEY(candidate_id,revision));
            CREATE TABLE IF NOT EXISTS intervention_context_texts (candidate_id TEXT NOT NULL, revision INTEGER NOT NULL, source_id TEXT NOT NULL, source_text TEXT NOT NULL, PRIMARY KEY(candidate_id,revision,source_id));
            CREATE TABLE IF NOT EXISTS intervention_proposals (id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL, UNIQUE(candidate_id,revision));
            CREATE TABLE IF NOT EXISTS intervention_reviews (recommendation_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL, PRIMARY KEY(recommendation_id,revision));
            CREATE TABLE IF NOT EXISTS intervention_followups (recommendation_id TEXT NOT NULL, sequence INTEGER NOT NULL, record TEXT NOT NULL, PRIMARY KEY(recommendation_id,sequence));
            """)

    @staticmethod
    def _rows(connection, table, field, value, order="revision"):
        return [json.loads(row[0]) for row in connection.execute("SELECT record FROM " + table + " WHERE " + field + "=? ORDER BY " + order, (value,))]

    def _candidate(self, connection, cid):
        identifier(cid)
        candidate = self.store.candidates(connection).get(cid)
        if not candidate:
            raise APIError("Candidate not found.", 404, "not_found")
        return candidate

    def _context(self, connection, cid):
        history = self._rows(connection, "intervention_contexts", "candidate_id", cid)
        return history[-1] if history else None

    @staticmethod
    def _revision(connection, table, field, value):
        row = connection.execute("SELECT MAX(revision) FROM " + table + " WHERE " + field + "=?", (value,)).fetchone()
        return row[0] or 0

    def _dependencies(self, connection, cid, members):
        result = {"context_revision": self._revision(connection, "intervention_contexts", "candidate_id", cid), "cases": {member: {"assessment_revision": self._revision(connection, "rights_assessments", "candidate_id", member), "evidence_revision": self.store.evidence_revision(connection, member), "rights_review_revision": self._revision(connection, "rights_reviews", "candidate_id", member)} for member in members}}
        if connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_drafts'").fetchone():
            row = connection.execute("SELECT id,revision,record FROM ai_drafts WHERE candidate_id=? ORDER BY revision DESC LIMIT 1", (cid,)).fetchone()
            if row:
                result["ai_draft"] = {"id": row[0], "revision": row[1], "raw_hashes": json.loads(row[2])["raw_hashes"]}
        return result

    def _stale(self, connection, record):
        current = self._dependencies(connection, record["candidate_id"], record["dependencies"]["cases"])
        reasons = []
        if current["context_revision"] != record["dependencies"]["context_revision"]:
            reasons.append("Context revision changed.")
        if record["dependencies"].get("ai_draft") is not None and current.get("ai_draft") != record["dependencies"]["ai_draft"]:
            reasons.append("Pending AI draft revision changed; original proposal and decisions preserved.")
        for cid, old in record["dependencies"]["cases"].items():
            for key, value in old.items():
                if current["cases"][cid][key] != value:
                    reasons.append(cid + ": " + key.replace("_", " ") + " changed.")
        return reasons, current

    def _proposal(self, connection, rid):
        identifier(rid)
        row = connection.execute("SELECT record FROM intervention_proposals WHERE id=?", (rid,)).fetchone()
        if not row:
            raise APIError("Recommendation not found.", 404, "not_found")
        return json.loads(row[0])

    def _decorate(self, connection, record):
        reasons, current = self._stale(connection, record)
        reviews = self._rows(connection, "intervention_reviews", "recommendation_id", record["id"])
        followups = self._rows(connection, "intervention_followups", "recommendation_id", record["id"], "sequence")
        return {**record, "stale": bool(reasons), "stale_reasons": reasons, "current_dependencies": current, "reviews": reviews, "followups": followups, "review_status": "stale" if reasons else reviews[-1]["decision"] if reviews else "pending_human_review"}

    def context(self, cid, payload):
        require_fields(payload, {"schema_version", "expected_revision", "author", "origin", "evidence_cutoff", "sources", "source_texts", "claims", "unknowns", "cluster", "comparables"})
        if payload["schema_version"] != "intervention-context/1":
            raise APIError("Unsupported context contract.")
        expected = number(payload["expected_revision"], "expected_revision")
        author = string(payload["author"], "author", 200)
        origin = enum(payload["origin"], ORIGINS, "origin")
        cutoff = iso_date(payload["evidence_cutoff"], "evidence_cutoff")
        if cutoff is None:
            raise APIError("A context evidence cutoff is required.")
        if not isinstance(payload["sources"], list) or len(payload["sources"]) > 100:
            raise APIError("sources must be an array of at most 100 sources.")
        sources = [source_record(x) for x in payload["sources"]]
        if any(s["publication_date"] and s["publication_date"] > cutoff for s in sources):
            raise APIError("A source published after the context cutoff cannot be evidence known at that cutoff.")
        sids = [s["id"] for s in sources]
        if len(set(sids)) != len(sids):
            raise APIError("Context source IDs must be unique.")
        source_texts = payload["source_texts"]
        if not isinstance(source_texts, dict) or set(source_texts) != set(sids):
            raise APIError("Supply exactly one source text for every context source.")
        captures = {sid: string(text, "source_text", 500000) for sid, text in source_texts.items()}
        if not isinstance(payload["claims"], list) or len(payload["claims"]) > 500:
            raise APIError("claims must be an array of at most 500 contextual propositions.")
        claims = []
        for item in payload["claims"]:
            require_fields(item, CLAIM_FIELDS)
            claim = {field: string(item[field], field, 12000) for field in CLAIM_FIELDS - {"id", "source_id", "topic", "relevant_date"}}
            claim.update(id=identifier(item["id"]), source_id=identifier(item["source_id"]), topic=enum(item["topic"], TOPICS, "topic"), relevant_date=iso_date(item["relevant_date"], "relevant_date"))
            if claim["source_id"] not in captures or claim["excerpt"] not in captures[claim["source_id"]]:
                raise APIError("Each context excerpt must occur exactly in its own supplied source text.")
            if claim["relevant_date"] and claim["relevant_date"] > cutoff and claim["topic"] != "deadline":
                raise APIError("A future non-deadline event cannot be presented as observed context at this cutoff.")
            claims.append(claim)
        claim_ids = ids([c["id"] for c in claims], "context claim IDs")
        unknowns = texts(payload["unknowns"], "unknowns")
        comparables = self._comparables(payload["comparables"], set(claim_ids))
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidate = self._candidate(connection, cid)
            if origin == "synthetic_prepared" and candidate["material_type"] != "synthetic":
                raise APIError("Synthetic context cannot be attached to real material.")
            current = self._revision(connection, "intervention_contexts", "candidate_id", cid)
            if expected != current:
                raise APIError("Context changed. Reload before saving.", 409, "revision_conflict")
            cluster = self._cluster(connection, cid, payload["cluster"], set(claim_ids))
            record = {"schema_version": "intervention-context/1", "candidate_id": cid, "revision": current + 1, "author": author, "origin": origin, "recorded_at": now(), "evidence_cutoff": cutoff, "sources": sources, "claims": claims, "unknowns": unknowns, "cluster": cluster, "comparables": comparables, "review_status": "context_prepared_not_factual_approval", "disclaimer": DISCLAIMER}
            connection.execute("INSERT INTO intervention_contexts VALUES (?,?,?)", (cid, record["revision"], encoded(record)))
            for sid, text in captures.items():
                connection.execute("INSERT INTO intervention_context_texts VALUES (?,?,?,?)", (cid, record["revision"], sid, text))
        return record

    def _cluster(self, connection, cid, item, claim_ids):
        if item is None:
            return None
        require_fields(item, {"candidate_ids", "memberships", "reviewer", "reason", "reviewed_context_ids"})
        members = ids(item["candidate_ids"], "cluster candidate IDs")
        if len(members) < 2 or cid not in members:
            raise APIError("A candidate cluster needs at least two cases and its primary case.")
        for member in members:
            self._candidate(connection, member)
        if not isinstance(item["memberships"], list) or len(item["memberships"]) != len(members):
            raise APIError("Explain every candidate cluster membership exactly once.")
        memberships = []
        for link in item["memberships"]:
            require_fields(link, {"candidate_id", "basis", "material_differences", "identity_uncertainty"})
            memberships.append({"candidate_id": identifier(link["candidate_id"]), **{key: string(link[key], key, 8000) for key in ("basis", "material_differences", "identity_uncertainty")}})
        if set(ids([x["candidate_id"] for x in memberships], "membership IDs")) != set(members):
            raise APIError("Membership IDs must match the candidate cluster scope.")
        reviewed = ids(item["reviewed_context_ids"], "reviewed_context_ids")
        if not reviewed or not set(reviewed) <= claim_ids:
            raise APIError("Cluster review needs resolving contextual passages.")
        return {"candidate_ids": members, "memberships": memberships, "reviewer": string(item["reviewer"], "reviewer", 200), "reason": string(item["reason"], "reason", 8000), "reviewed_context_ids": reviewed, "reviewed_at": now(), "scope": "Candidate membership links only; no factual authentication, identity merge, incidence estimate or coordinated-movement finding."}

    @staticmethod
    def _comparables(items, claim_ids):
        if not isinstance(items, list) or len(items) > 30:
            raise APIError("comparables must contain at most 30 histories.")
        result = []
        for item in items:
            require_fields(item, {"label", "basis", "material_differences", "action_context_ids", "outcome_context_ids", "period", "contribution", "limitations"})
            record = {key: string(item[key], key, 8000) for key in item.keys() - {"action_context_ids", "outcome_context_ids"}}
            for key in ("action_context_ids", "outcome_context_ids"):
                record[key] = ids(item[key], key)
                if not set(record[key]) <= claim_ids:
                    raise APIError("Comparable history passage does not resolve.")
            if not record["action_context_ids"]:
                raise APIError("Comparable advocacy needs a cited documented action; unknown outcomes may stay empty.")
            result.append(record)
        return result

    @staticmethod
    def _options(items, context):
        if not isinstance(items, list) or not 2 <= len(items) <= 12:
            raise APIError("Compare 2–12 options, including a deferral alternative.")
        claim_ids = {c["id"] for c in context["claims"]}
        result = []
        for item in items:
            require_fields(item, OPTION_FIELDS)
            option = {key: string(item[key], key, 8000) for key in {"label", "actor", "authority", "objective", "beneficiary", "timing_window", "alternative_explanations", "next_step", "reconsideration_trigger"}}
            option.update(id=identifier(item["id"]), route=enum(item["route"], ROUTES, "route"))
            for key in REFERENCE_FIELDS:
                option[key] = ids(item[key], key)
                if not set(option[key]) <= claim_ids:
                    raise APIError("Option context citation does not resolve.")
            if set(option["support_context_ids"]) & set(option["contrary_context_ids"]):
                raise APIError("An option passage cannot be both supporting and contrary; describe ambiguity explicitly.")
            for key in ("preconditions", "blocking_unknowns", "benefits", "harms"):
                option[key] = texts(item[key], key)
            require_fields(item["factors"], {"urgency", "opportunity", "feasibility", "harm", "preferences", "reason"})
            f = item["factors"]
            option["factors"] = {"urgency": enum(f["urgency"], {"unknown", "routine", "time_sensitive"}, "urgency"), "opportunity": enum(f["opportunity"], {"unknown", "not_established", "supported"}, "opportunity"), "feasibility": enum(f["feasibility"], {"unknown", "needs_verification", "feasible"}, "feasibility"), "harm": enum(f["harm"], {"unknown", "material_risk", "mitigated"}, "harm"), "preferences": enum(f["preferences"], {"unknown", "requested", "opposed"}, "preferences"), "reason": string(f["reason"], "factor reason", 8000)}
            result.append(option)
        ids([x["id"] for x in result], "option IDs")
        if not any(x["route"] == "deferral" for x in result):
            raise APIError("Include a concrete deferral alternative; deferral is not doing nothing.")
        return result

    @staticmethod
    def _decide(requested, option, context, legal_available):
        claims = {c["id"]: c for c in context["claims"]}
        factors = option["factors"]
        reasons = []
        def topic(refs, topics):
            return any(claims[x]["topic"] in topics for x in refs)
        opportunity = topic(option["support_context_ids"], {"legal_opportunity", "issue_position", "institution"}) and topic(option["authority_context_ids"], {"institution", "legal_opportunity"}) and factors["opportunity"] == "supported"
        if requested == "insufficient_basis":
            return requested, ["Explicit abstention: the supplied worksheet does not establish a sufficient basis. This is not a recommendation against intervention."]
        if requested == "defer":
            return requested, ["Defer the specified route until its stated reconsideration condition; other verification/preparation options remain available."]
        if requested == "against":
            if not option["contrary_context_ids"] and not topic(option["harm_context_ids"], {"harm", "preferences"}):
                return "insufficient_basis", ["A recommendation against a route needs cited contrary evidence or a sourced harm/preference reason; mere missingness is insufficient."]
            return requested, ["Specified route opposed at present on cited contrary/harm evidence; this does not exclude other routes."]
        if requested == "prepare_verify":
            if not legal_available and not any(claims[x]["topic"] not in {"party_label", "country_indicator", "attention"} for x in option["support_context_ids"]):
                return "insufficient_basis", ["No case-specific rights/context basis identifies a targeted verification task; missingness is not a confident strategy recommendation."]
            return requested, ["Targeted verification/preparation is an explicit limited next step; it does not authorize the proposed intervention."]
        if not opportunity:
            reasons.append("Issue-specific opportunity and institutional authority are not both supported; party labels, country indicators and deadlines alone cannot supply them.")
        if not legal_available:
            reasons.append("Relevant rights dimensions are unassessed or their saved evidence is stale.")
        if requested == "refer_coordinate":
            if option["route"] not in {"partner_coordination", "mechanism_referral"}:
                reasons.append("Referral needs a partner/mechanism route with applicable authority.")
            if not topic(option["feasibility_context_ids"], {"capacity", "organization"}):
                reasons.append("Partner availability/capacity remains unsupported.")
        elif option["route"] in {"verification", "deferral"}:
            reasons.append("Verification/deferral is not an immediate intervention route.")
        if factors["feasibility"] != "feasible" or not topic(option["feasibility_context_ids"], {"capacity", "organization"}):
            reasons.append("Practical feasibility requires a sourced capacity/access basis.")
        if factors["harm"] != "mitigated" or not topic(option["harm_context_ids"], {"harm"}):
            reasons.append("Potential harm is not documented and mitigated in the worksheet.")
        if factors["preferences"] != "requested" or not topic(option["preferences_context_ids"], {"preferences"}):
            reasons.append("Affected people's relevant stated preferences remain unknown, opposed or unsupported; do not assume consent.")
        if factors["urgency"] == "time_sensitive" and not any(claims[x]["topic"] in {"deadline", "procedure"} and claims[x]["relevant_date"] for x in option["timing_context_ids"]):
            reasons.append("The urgent timing window lacks a dated procedural/deadline passage.")
        if factors["urgency"] == "unknown":
            reasons.append("Timing/urgency remains unknown.")
        if option["blocking_unknowns"]:
            reasons.append("Explicit blocking unknowns require verification before intervention.")
        if reasons:
            return ("prepare_verify" if option["support_context_ids"] or legal_available else "insufficient_basis"), reasons
        return requested, ["Explicit gates met for this specified route: relevant rights scope, issue-specific opportunity/authority, capacity, examined harms, preferences and timing. This provisional worksheet is not evidence of effectiveness or authorization to act."]

    def propose(self, cid, payload):
        require_fields(payload, {"expected_revision", "expected_context_revision", "expected_assessment_revision", "author", "origin", "dimension_ids", "selected_option_id", "requested_disposition", "options", "rationale"})
        expected = number(payload["expected_revision"], "expected_revision")
        expected_context = number(payload["expected_context_revision"], "expected_context_revision")
        expected_assessment = number(payload["expected_assessment_revision"], "expected_assessment_revision")
        author = string(payload["author"], "author", 200)
        origin = enum(payload["origin"], ORIGINS, "origin")
        dimensions = ids(payload["dimension_ids"], "dimension_ids")
        requested = enum(payload["requested_disposition"], DISPOSITIONS, "requested_disposition")
        rationale = string(payload["rationale"], "rationale", 8000)
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidate = self._candidate(connection, cid)
            if origin == "synthetic_prepared" and candidate["material_type"] != "synthetic":
                raise APIError("Synthetic proposal cannot be attached to real material.")
            context = self._context(connection, cid)
            if not context:
                raise APIError("Save dated context before preparing a proposal.", 409, "context_required")
            current = self._revision(connection, "intervention_proposals", "candidate_id", cid)
            if expected != current or expected_context != context["revision"]:
                raise APIError("Proposal/context changed. Reinspect current versions.", 409, "revision_conflict")
            members = context["cluster"]["candidate_ids"] if context["cluster"] else [cid]
            dependencies = self._dependencies(connection, cid, members)
            if dependencies["cases"][cid]["assessment_revision"] != expected_assessment:
                raise APIError("Rights assessment changed. Reinspect it.", 409, "assessment_revision_conflict")
            rights = {}
            for member in members:
                rights[member] = self.store.rights.export(member) if dependencies["cases"][member]["assessment_revision"] else {"case_profile": {"candidate_id": member, "assessment": None, "review_status": "unassessed"}, "disclaimer": "No rights assessment exists for this linked candidate."}
                saved = rights[member]["case_profile"]["assessment"]
                if saved and any(s.get("publication_date") and s["publication_date"] > context["evidence_cutoff"] for s in saved["evidence_snapshot"]["sources"]):
                    raise APIError("Linked rights evidence includes a source after the context cutoff. Update the dated context before proposing.")
            primary = rights[cid]["case_profile"]
            assessment = primary["assessment"]
            available = {d["dimension_id"]: d for d in assessment["dimensions"]} if assessment else {}
            if not set(dimensions) <= available.keys():
                raise APIError("Selected rights dimensions must resolve to the exact saved assessment.")
            legal_available = bool(dimensions and not primary.get("stale_evidence") and any(available[d]["status"] != "not_assessed" for d in dimensions))
            options = self._options(payload["options"], context)
            selected_id = identifier(payload["selected_option_id"])
            selected = next((x for x in options if x["id"] == selected_id), None)
            if not selected:
                raise APIError("Selected option ID does not resolve.")
            disposition, reasons = self._decide(requested, selected, context, legal_available)
            references = {x for option in options for field in REFERENCE_FIELDS for x in option[field]}
            for comparable in context["comparables"]:
                references.update(comparable["action_context_ids"] + comparable["outcome_context_ids"])
            if context["cluster"]:
                references.update(context["cluster"]["reviewed_context_ids"])
            record = {"schema_version": VERSION, "id": "recommendation_" + uuid4().hex, "candidate_id": cid, "revision": current + 1, "created_at": now(), "author": author, "origin": origin, "evidence_cutoff": context["evidence_cutoff"], "dependencies": dependencies, "dimension_ids": dimensions, "rights_snapshots": rights, "context_snapshot": context, "options": options, "selected_option_id": selected_id, "requested_disposition": requested, "disposition": disposition, "rule_reasons": reasons, "rationale": rationale, "factors": deepcopy(selected["factors"]), "legal_concern": [deepcopy(available[d]) for d in dimensions], "rights_scope_status": primary["review_status"], "review_scope": {"dimension_ids": dimensions, "context_claim_ids": sorted(references)}, "review_status": "pending_human_review", "disclaimer": DISCLAIMER}
            connection.execute("INSERT INTO intervention_proposals VALUES (?,?,?,?)", (record["id"], cid, record["revision"], encoded(record)))
        return {**record, "stale": False, "stale_reasons": [], "reviews": [], "followups": []}

    def review(self, rid, payload):
        require_fields(payload, {"expected_review_revision", "reviewer", "decision", "reason", "dimension_ids", "context_claim_ids", "revised_disposition", "revision_note"})
        expected = number(payload["expected_review_revision"], "expected_review_revision")
        decision = enum(payload["decision"], {"accept", "revise", "reject", "defer"}, "decision")
        reviewer, reason = string(payload["reviewer"], "reviewer", 200), string(payload["reason"], "reason", 8000)
        revised = payload["revised_disposition"]
        if decision == "revise":
            revised = enum(revised, DISPOSITIONS, "revised_disposition")
            note = string(payload["revision_note"], "revision_note", 8000)
        else:
            if revised is not None:
                raise APIError("Only a revise decision supplies a revised disposition.")
            note = string(payload["revision_note"], "revision_note", 8000, blank=True)
        dimensions, context_ids = ids(payload["dimension_ids"], "dimension_ids"), ids(payload["context_claim_ids"], "context_claim_ids")
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            record = self._proposal(connection, rid)
            if set(dimensions) != set(record["review_scope"]["dimension_ids"]) or set(context_ids) != set(record["review_scope"]["context_claim_ids"]):
                raise APIError("Human review must name the exact proposed dimensions and all compared option/context passages, including contrary evidence.")
            stale, _ = self._stale(connection, record)
            if stale and decision in {"accept", "revise"}:
                raise APIError("Recommendation dependencies changed. Prepare a fresh proposal before acceptance/revision.", 409, "stale_recommendation")
            current = self._revision(connection, "intervention_reviews", "recommendation_id", rid)
            if current != expected:
                raise APIError("Recommendation review changed. Reload.", 409, "review_revision_conflict")
            review = {"schema_version": "intervention-review/1", "recommendation_id": rid, "recommendation_revision": record["revision"], "revision": current + 1, "reviewer": reviewer, "decision": decision, "reason": reason, "reviewed_at": now(), "dimension_ids": dimensions, "context_claim_ids": context_ids, "dependencies": deepcopy(record["dependencies"]), "revised_disposition": revised, "revision_note": note, "stale_at_review": bool(stale), "scope": "Only this recommendation revision and its listed dimensions/context passages/options; rights approval, whole-case authentication and authority to execute advocacy are not implied."}
            connection.execute("INSERT INTO intervention_reviews VALUES (?,?,?)", (rid, review["revision"], encoded(review)))
        return review

    def followup(self, rid, payload):
        require_fields(payload, {"expected_sequence", "author", "kind", "text", "event_date", "period", "contribution", "source", "source_text", "excerpt", "locator", "uncertainty"})
        expected = number(payload["expected_sequence"], "expected_sequence")
        kind = enum(payload["kind"], {"observed_action", "observed_outcome", "conditional_scenario", "unknown_outcome"}, "kind")
        text = string(payload["text"], "text", 12000)
        author = string(payload["author"], "author", 200)
        event_date = iso_date(payload["event_date"], "event_date")
        values = {key: string(payload[key], key, 8000) for key in ("period", "contribution", "uncertainty")}
        source, excerpt, locator = None, None, None
        if payload["source"] is not None:
            source = source_record(payload["source"])
            capture = string(payload["source_text"], "source_text", 500000)
            excerpt, locator = string(payload["excerpt"], "excerpt", 12000), string(payload["locator"], "locator", 2000)
            if excerpt not in capture:
                raise APIError("Followup excerpt must occur in its own supplied source text.")
        elif any(payload[x] is not None for x in ("source_text", "excerpt", "locator")):
            raise APIError("A followup passage requires its resolving source.")
        if kind in {"observed_action", "observed_outcome"} and source is None:
            raise APIError("Observed action/outcome requires a source, exact excerpt and locator.")
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            proposal = self._proposal(connection, rid)
            row = connection.execute("SELECT MAX(sequence) FROM intervention_followups WHERE recommendation_id=?", (rid,)).fetchone()
            current = row[0] or 0
            if expected != current:
                raise APIError("Followup sequence changed. Reload.", 409, "sequence_conflict")
            record = {"schema_version": "intervention-followup/1", "recommendation_id": rid, "sequence": current + 1, "author": author, "kind": kind, "text": text, "event_date": event_date, "recorded_at": now(), "source": source, "excerpt": excerpt, "locator": locator, **values, "dependencies": deepcopy(proposal["dependencies"]), "interpretation": "Conditional scenario, not an observed outcome or probability." if kind == "conditional_scenario" else "Source-attributed observation; chronology does not establish contribution or effectiveness." if kind.startswith("observed") else "Outcome unknown; not absence of an outcome."}
            connection.execute("INSERT INTO intervention_followups VALUES (?,?,?)", (rid, record["sequence"], encoded(record)))
        return record

    def state(self, cid):
        with self.store.connection() as connection:
            connection.execute("BEGIN")
            self._candidate(connection, cid)
            contexts = self._rows(connection, "intervention_contexts", "candidate_id", cid)
            recommendations = [self._decorate(connection, x) for x in self._rows(connection, "intervention_proposals", "candidate_id", cid)]
        path = Path(__file__).resolve().parents[1] / "examples/intervention.synthetic.json"
        example = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        return {"candidate_id": cid, "context": contexts[-1] if contexts else None, "context_history": contexts, "recommendations": recommendations, "latest": recommendations[-1] if recommendations else None, "example": example, "dispositions": DISPOSITIONS, "routes": ROUTES, "disclaimer": DISCLAIMER}

    def export(self, rid):
        with self.store.connection() as connection:
            connection.execute("BEGIN")
            record = self._decorate(connection, self._proposal(connection, rid))
        return {"schema_version": VERSION, "document_type": "cited_intervention_decision", "exported_at": now(), "recommendation": record, "disclaimer": DISCLAIMER, "snapshot_policy": "Original rights/context/options/dependencies remain immutable; later evidence/context/reassessment/review changes flag recommendations stale. New proposals require new human review. Observed actions/outcomes, conditional scenarios and unknown outcomes remain distinct; no causal or calibrated likelihood estimate is supplied."}


def render_intervention_markdown(document):
    m = markdown_text
    r = document["recommendation"]
    context = r["context_snapshot"]
    rows = ["# Provisional intervention decision", "", document["disclaimer"], "", "Case: " + m(r["candidate_id"]) + " · Recommendation: " + m(r["id"]) + " · Revision " + str(r["revision"]), "", "Author: " + m(r["author"]) + " · Origin: " + m(r["origin"]) + " · Prepared: " + m(r["created_at"]) + " · Evidence cutoff: " + m(r["evidence_cutoff"]), "", "Requested disposition: " + m(r["requested_disposition"]) + " · Deterministic proposal: **" + m(r["disposition"]) + "** · Human status: " + m(r["review_status"]), "", "Rights scope status at preparation: " + m(r["rights_scope_status"]) + ". Pending analysis is not promoted by this recommendation.", "", "Rationale: " + m(r["rationale"]), ""]
    if r["stale"]:
        rows += ["**STALE RECOMMENDATION: " + m("; ".join(r["stale_reasons"])) + " Prepare and review a fresh proposal before relying on it.**", ""]
    rows += ["## Transparent rule reasons", ""] + ["- " + m(x) for x in r["rule_reasons"]] + ["", "Legal concern, urgency, opportunity, feasibility, harm and unknowns are separate judgments. No weighted score or probability is calculated.", ""]
    for option in r["options"]:
        rows += ["## Option " + m(option["id"]) + ": " + m(option["label"]) + (" — selected" if option["id"] == r["selected_option_id"] else " — alternative"), ""]
        for key in ("route", "actor", "authority", "objective", "beneficiary", "timing_window", "alternative_explanations", "next_step", "reconsideration_trigger"):
            rows += ["**" + key.replace("_", " ").title() + ":** " + m(option[key]), ""]
        for key in REFERENCE_FIELDS:
            rows += ["**" + key.replace("_", " ").title() + ":** " + ", ".join("[" + m(x) + "](#context-" + x + ")" for x in option[key]), ""]
        for key in ("preconditions", "blocking_unknowns", "benefits", "harms"):
            rows += ["**" + key.replace("_", " ").title() + ":** " + m("; ".join(option[key]) or "None recorded; this is not certification."), ""]
        rows += ["Separate factor judgments: " + m(json.dumps(option["factors"], ensure_ascii=False)), ""]
    rows += ["## Context passages and competing accounts", "", "Context revision " + str(context["revision"]) + " · Recorded " + m(context["recorded_at"]) + " · Unknowns: " + m("; ".join(context["unknowns"]) or "None recorded; not full knowledge."), ""]
    sources = {s["id"]: s for s in context["sources"]}
    for c in context["claims"]:
        s = sources[c["source_id"]]
        rows += ['<a id="context-' + c["id"] + '"></a>', "", "### Context " + m(c["id"]), "", m(c["text"]), "", "Exact excerpt: " + m(c["excerpt"]), "", "Source: [" + m(s["title"]) + "](" + quote(s["url"], safe=":/?#[]@!$&'*+,;=%") + ") · Locator: " + m(c["locator"]), "", "Attribution: " + m(c["attribution"]) + " · Relevant date: " + m(c["relevant_date"] or "unknown") + " · " + m(c["date_note"]), "", "Uncertainty: " + m(c["uncertainty"]) + " · Freshness: " + m(c["freshness_note"]), "", "Published: " + m(s["publication_date"] or "unknown") + " · Retrieved: " + m(s["retrieved_at"] or "unknown") + " · Language/translation: " + m(s["language"] + " / " + s["translation_status"]), "", "Source dependence/access: " + m(s["lineage_note"] + " / " + s["access_note"]), ""]
    rows += ["## Candidate cluster and comparable histories", "", m(json.dumps({"cluster": context["cluster"], "comparables": context["comparables"]}, ensure_ascii=False, indent=2)), "", "Candidate links do not establish shared identity, national incidence or a movement. Observed sequence does not establish effectiveness.", "", "## Exact review scope and dependencies", "", m(json.dumps(r["review_scope"], ensure_ascii=False)), "", m(json.dumps(r["dependencies"], ensure_ascii=False)), ""]
    for review in r["reviews"]:
        rows += ["Human " + m(review["decision"]) + " by " + m(review["reviewer"]) + " · " + m(review["reviewed_at"]) + " · Reason: " + m(review["reason"]), "", "Exact dimensions/context: " + m(json.dumps({"dimension_ids": review["dimension_ids"], "context_claim_ids": review["context_claim_ids"]}, ensure_ascii=False)), "", "Human revision: " + m(review["revised_disposition"] or "none") + " · " + m(review["revision_note"]) + " · " + m(review["scope"]), ""]
    rows += ["## Followup: observations versus conditional scenarios", ""]
    for f in r["followups"]:
        rows += ["### " + m(f["kind"]) + " · " + str(f["sequence"]), "", m(f["text"]), "", "Event: " + m(f["event_date"] or "unknown") + " · Period: " + m(f["period"]) + " · Recorded: " + m(f["recorded_at"]), "", m(f["interpretation"]) + " Contribution: " + m(f["contribution"]) + " Uncertainty: " + m(f["uncertainty"]), ""]
        if f["source"]:
            rows += ["Source: [" + m(f["source"]["title"]) + "](" + quote(f["source"]["url"], safe=":/?#[]@!$&'*+,;=%") + ") · Locator: " + m(f["locator"]), "", "Exact excerpt: " + m(f["excerpt"]), ""]
    rows += ["## Full saved legal profiles", ""]
    from .rights import render_rights_markdown
    for cid, rights in r["rights_snapshots"].items():
        rows += ["### Linked case " + m(cid), ""]
        rows += [render_rights_markdown(rights) if rights["case_profile"]["assessment"] else "Not assessed; no rights score was inferred.", ""]
    return "\n".join(rows + [document["snapshot_policy"], ""])
