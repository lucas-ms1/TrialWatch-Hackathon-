"""Validate saved evidence and AI outputs, calculate agreement, and render locally.

Standard library only. No browsing, AI invocation, semantic truth assessment, or
human-review decisions occur here. Frozen inputs are never modified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_data import load_json, validate_document  # noqa: E402

DECISIONS = {"relevant", "irrelevant", "uncertain"}
QUEUED = {"relevant", "uncertain"}
KINDS = {"prosecution_trigger", "procedural_event", "alleged_conduct", "context"}
CHANGES = {"new_reported_event", "newly_learned_older_fact", "conflicting_account", "repeated_report"}
ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,79}$")
LOCATOR = re.compile(r"^paragraph\s+(\d+)\b", re.IGNORECASE)
SOURCE_FIELDS = {"source_id", "url", "title", "publisher", "language", "translation_status",
                 "publication_date", "update_date", "update_note", "retrieved_at", "capture_method",
                 "access_status", "body", "text_sha256", "lineage_group", "upstream_sources",
                 "historical_availability", "capture_path"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def save_json(path: Path, value) -> None:
    save_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def save_immutable_json(path: Path, value) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError(f"Refusing to change frozen calculated result: {path}; use a separate output directory")
        return
    save_text(path, text)


def bind_output_directory(output: Path, run_id: str, prediction_version: str, input_hashes: dict) -> None:
    """Bind before any export, including failure reports; decisions alone are insufficient."""
    binding = {"run_id": run_id, "prediction_version": prediction_version, "input_hashes": input_hashes}
    path = output / "output_binding.json"
    if path.exists():
        if load_json(path) != binding:
            raise ValueError("Output directory is bound to different frozen inputs or prediction version; use a separate output directory")
        return
    owned_names = {"index.html", "style.css", "cards", "cards.md", "cases.json", "cases.early.json", "metrics.json",
                   "acceptance.json", "input_hashes.json", "baseline.json", "validation.json", "audit_inventory.json",
                   "source_metadata.json", "article_review_queue.json", "COMMANDS.md", "audit_provenance.json"}
    if output.exists() and any((output / name).exists() for name in owned_names):
        raise ValueError("Output directory contains unbound generated artifacts; use a separate output directory")
    save_immutable_json(path, binding)


def save_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    temporary.replace(path)


def is_date(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def is_timestamp(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return "T" in value and parsed.utcoffset() is not None
    except ValueError:
        return False


def nonblank(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def paragraphs(body: str) -> list[str]:
    return re.split(r"\n\s*\n", body.strip())


def index_unique(items, key, path, errors):
    result = {}
    if not isinstance(items, list):
        errors.append(f"{path}: expected array")
        return result
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not nonblank(item.get(key)):
            errors.append(f"{path}[{index}]: missing {key}")
            continue
        value = item[key]
        if value in result:
            errors.append(f"{path}: duplicate {key} {value}")
        if not ID.fullmatch(value):
            errors.append(f"{path}: invalid {key} {value!r}")
        result[value] = item
    return result


def check_corpus(corpus: dict, config: dict) -> dict:
    errors, warnings = [], []
    if not nonblank(corpus.get("run_id")):
        errors.append("corpus: run_id required")
    sources = index_unique(corpus.get("sources"), "source_id", "corpus.sources", errors)
    urls = {}
    for sid, source in sources.items():
        missing = SOURCE_FIELDS - set(source)
        if missing:
            errors.append(f"{sid}: missing fields {sorted(missing)}")
        for field in ("title", "publisher", "language", "translation_status", "body", "capture_method",
                      "historical_availability", "capture_path"):
            if not nonblank(source.get(field)):
                errors.append(f"{sid}.{field}: nonblank string required")
        if not re.fullmatch(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})*", str(source.get("language", ""))):
            errors.append(f"{sid}.language: expected BCP47 language code")
        url = source.get("url", "")
        try:
            safe_url(url)
        except (TypeError, ValueError):
            errors.append(f"{sid}.url: invalid public URL")
        if url in urls:
            errors.append(f"{sid}: duplicate URL also assigned to {urls[url]}")
        urls[url] = sid
        for field in ("publication_date", "update_date"):
            if not is_date(source.get(field)):
                errors.append(f"{sid}.{field}: ISO date or null required")
        if not is_timestamp(source.get("retrieved_at")):
            errors.append(f"{sid}.retrieved_at: timezone timestamp required")
        if source.get("access_status") not in {"readable", "partial"}:
            errors.append(f"{sid}.access_status: readable or partial required")
        if not isinstance(source.get("upstream_sources"), list):
            errors.append(f"{sid}.upstream_sources: array required")
        if isinstance(source.get("body"), str) and body_hash(source["body"]) != str(source.get("text_sha256", "")).lower():
            errors.append(f"{sid}: body text SHA256 mismatch")
        if source.get("publication_date") is None:
            warnings.append(f"{sid}: publication date unknown")
        if source.get("update_note") and source.get("historical_availability") == "unverified":
            warnings.append(f"{sid}: update notice with unverified historical text availability")
    minimum = config["corpus"]["min_reports"]
    if len(sources) < minimum:
        warnings.append(f"Corpus has {len(sources)} reports; minimum target is {minimum}")
    if len(sources) > config["corpus"]["max_reports"]:
        errors.append("Corpus exceeds frozen maximum reports")
    publisher_count = len({s.get("publisher") for s in sources.values()})
    if publisher_count < config["corpus"]["min_publishers_overall"]:
        warnings.append("Publisher diversity minimum unmet")
    lineage = defaultdict(list)
    for sid, source in sources.items():
        if source.get("lineage_group") is not None:
            lineage[source["lineage_group"]].append(sid)
    return {"errors": errors, "warnings": warnings, "reports": len(sources),
            "publishers": publisher_count, "known_lineage_groups": dict(sorted(lineage.items())),
            "independent_origin_count": None,
            "scope": "Structure and integrity only; publisher/URL counts do not prove independent corroboration."}


def check_packet(packet: dict, corpus: dict, expected_stage: str) -> dict:
    errors = []
    sources = index_unique(packet.get("sources"), "source_id", "packet.sources", errors)
    canonical = {s["source_id"]: s for s in corpus["sources"]}
    if packet.get("run_id") != corpus.get("run_id"):
        errors.append("packet: run_id mismatch")
    if packet.get("stage") != expected_stage:
        errors.append("packet: stage mismatch")
    if packet.get("view_type") != "publication_ordered_reconstruction":
        errors.append("packet: expected publication_ordered_reconstruction")
    for sid, source in sources.items():
        if sid not in canonical:
            errors.append(f"packet: unknown source {sid}")
        elif source != canonical[sid]:
            errors.append(f"packet: {sid} differs from frozen corpus source")
    early = packet.get("early_source_ids")
    if not isinstance(early, list) or len(early) != len(set(early)) or not set(early) <= set(sources):
        errors.append("packet: invalid early_source_ids membership")
    elif expected_stage == "early" and set(early) != set(sources):
        errors.append("early packet: early_source_ids must equal source membership")
    return {"errors": errors, "source_count": len(sources), "stage": expected_stage}


def run_baseline(corpus: dict, config: dict) -> dict:
    spec = config["baseline"]
    if spec["method"] != "case_insensitive_substring_role_AND_proceeding_in_article_body":
        raise ValueError("Unsupported frozen baseline method")
    rows = []
    for source in corpus["sources"]:
        body = source["body"].lower()
        roles = [term for term in spec["role_terms"] if term.lower() in body]
        proceedings = [term for term in spec["proceeding_terms"] if term.lower() in body]
        rows.append({"source_id": source["source_id"], "decision": "relevant" if roles and proceedings else "irrelevant",
                     "matched_role_terms": roles, "matched_proceeding_terms": proceedings})
    return {"run_id": corpus["run_id"], "method": spec["method"], "terms": spec,
            "article_decisions": rows, "scope": "Deterministic substring filter; no semantic role understanding."}


def assertion_inventory(predictions: dict, packet: dict | None = None) -> list[dict]:
    """Full displayed-input scope, including dates, attribution, uncertainty and metadata.

    IDs are deterministic within an exact frozen prediction/packet pair. Identity
    hashes bind an audit to that pair; the ordinal is never an identity shortcut.
    """
    rows = []
    def add(kind, identity, text, claim_ids=None, fields=None):
        rows.append({"assertion_id": f"{predictions['stage']}:a{len(rows) + 1:04d}", "type": kind,
                     "id": identity, "text": text, "claim_ids": claim_ids or [], "fields": fields or {}})
    for claim in predictions.get("claims", []):
        add("claim", claim["claim_id"], claim["text"], [claim["claim_id"]], dict(claim))
    for card in predictions.get("cards", []):
        pid = card["proceeding_id"]
        add("card_title", pid, card["title"])
        add("card_stage_membership", pid, "Source membership for earlier/later views", fields={"earlier_claim_ids": card["earlier_claim_ids"], "later_claim_ids": card["later_claim_ids"]})
        add("human_review_state", pid, card["human_review"])
        for field in ("changes", "review_reasons"):
            for index, item in enumerate(card[field]):
                add(field, f"{pid}-{field}-{index + 1}", item["text"], item["claim_ids"], dict(item))
        for index, item in enumerate(card["unknowns"]):
            add("unknown_question", f"{pid}-unknown-{index + 1}", item["question"])
            add("unknown_next_check", f"{pid}-next-check-{index + 1}", item["next_check"])
    for proceeding in predictions.get("proceedings", []):
        pid = proceeding["proceeding_id"]
        add("proceeding_title", pid, proceeding["title"])
        for index, person in enumerate(proceeding["defendants"]):
            add("defendant_identity", f"{pid}-person-{index + 1}", person)
        if proceeding.get("linkage_uncertainty"):
            add("linkage_uncertainty", pid, proceeding["linkage_uncertainty"])
        if proceeding["related_proceeding_ids"]:
            add("related_proceedings", pid, "Related proceedings kept separate", fields={"related_proceeding_ids": proceeding["related_proceeding_ids"]})
        add("proceeding_source_membership", pid, "Sources listed for proceeding", fields={"source_ids": proceeding["source_ids"]})
    if packet:
        for source in packet["sources"]:
            add("source_metadata", source["source_id"], source["title"], fields={key: value for key, value in source.items() if key != "body"})
    return rows


def check_predictions(predictions: dict, packet: dict) -> dict:
    errors, warnings = [], []
    sources = {s["source_id"]: s for s in packet["sources"]}
    early_ids = set(packet["early_source_ids"])
    stage = packet["stage"]
    if predictions.get("run_id") != packet["run_id"] or predictions.get("stage") != stage:
        errors.append("predictions: run_id or stage mismatch")
    decisions = index_unique(predictions.get("article_decisions"), "source_id", "article_decisions", errors)
    if set(decisions) != set(sources):
        errors.append(f"article_decisions: exact packet coverage required; missing={sorted(set(sources)-set(decisions))}, extra={sorted(set(decisions)-set(sources))}")
    for sid, decision in decisions.items():
        if decision.get("decision") not in DECISIONS or not nonblank(decision.get("reason")):
            errors.append(f"{sid}: valid decision and supported reason required")
    claims = index_unique(predictions.get("claims"), "claim_id", "claims", errors)
    proceedings = index_unique(predictions.get("proceedings"), "proceeding_id", "proceedings", errors)
    cards = index_unique(predictions.get("cards"), "proceeding_id", "cards", errors)
    for pid, proceeding in proceedings.items():
        for field in ("title",):
            if not nonblank(proceeding.get(field)):
                errors.append(f"{pid}.{field}: required")
        for field in ("defendants", "source_ids", "related_proceeding_ids"):
            if not isinstance(proceeding.get(field), list):
                errors.append(f"{pid}.{field}: array required")
        if not set(proceeding.get("source_ids", [])) <= set(sources):
            errors.append(f"{pid}: source outside permitted stage")
        if not set(proceeding.get("related_proceeding_ids", [])) <= set(proceedings):
            errors.append(f"{pid}: unresolved related proceeding")
        if pid in proceeding.get("related_proceeding_ids", []):
            errors.append(f"{pid}: cannot be its own related proceeding")
        if "linkage_uncertainty" not in proceeding:
            errors.append(f"{pid}: linkage_uncertainty required, null if none recorded")
    for cid, claim in claims.items():
        for field in ("text", "quote", "locator", "attribution"):
            if not nonblank(claim.get(field)):
                errors.append(f"{cid}.{field}: nonblank string required")
        if "event_date" not in claim or not is_date(claim.get("event_date")):
            errors.append(f"{cid}.event_date: explicit ISO date or null required")
        if claim.get("kind") not in KINDS:
            errors.append(f"{cid}.kind: invalid")
        pid, sid = claim.get("proceeding_id"), claim.get("source_id")
        if pid not in proceedings:
            errors.append(f"{cid}: unresolved proceeding")
        elif sid not in proceedings[pid].get("source_ids", []):
            errors.append(f"{cid}: source not listed for proceeding")
        if sid not in sources:
            errors.append(f"{cid}: source outside permitted stage")
            continue
        quote, locator = claim.get("quote"), claim.get("locator")
        match = LOCATOR.match(locator) if isinstance(locator, str) else None
        paras = paragraphs(sources[sid]["body"])
        if not match or not 1 <= int(match[1]) <= len(paras):
            errors.append(f"{cid}: invalid paragraph locator")
        elif not isinstance(quote, str) or not quote or quote not in paras[int(match[1]) - 1]:
            errors.append(f"{cid}: exact quote not present in cited paragraph")
        if claim.get("event_date") is None:
            warnings.append(f"{cid}: event date unknown (preserved as null)")
    def references(refs, pid, context):
        if not isinstance(refs, list) or not refs:
            errors.append(f"{context}: nonempty claim_ids required")
            return
        for cid in refs:
            if cid not in claims:
                errors.append(f"{context}: unresolved claim {cid}")
            elif claims[cid].get("proceeding_id") != pid:
                errors.append(f"{context}: wrong proceeding claim {cid}")
    for pid, card in cards.items():
        if pid not in proceedings:
            errors.append(f"card {pid}: unresolved proceeding")
        if not nonblank(card.get("title")):
            errors.append(f"card {pid}: title required")
        if card.get("human_review") not in {"pending", "needs_sources"}:
            errors.append(f"card {pid}: human review must remain pending or needs_sources")
        for field in ("earlier_claim_ids", "later_claim_ids", "changes", "review_reasons", "unknowns"):
            if not isinstance(card.get(field), list):
                errors.append(f"card {pid}.{field}: array required")
        for field in ("earlier_claim_ids", "later_claim_ids"):
            refs = card.get(field, [])
            if refs:
                references(refs, pid, f"{pid}.{field}")
            for cid in refs:
                if cid in claims:
                    sid = claims[cid]["source_id"]
                    if field == "earlier_claim_ids" and sid not in early_ids:
                        errors.append(f"{pid}.{field}: later source leaked into early view via {cid}")
                    if field == "later_claim_ids" and (stage == "early" or sid in early_ids):
                        errors.append(f"{pid}.{field}: claim does not use a newly added source: {cid}")
        for field in ("changes", "review_reasons"):
            for index, item in enumerate(card.get(field, [])):
                context = f"{pid}.{field}[{index}]"
                if not nonblank(item.get("text")):
                    errors.append(f"{context}: text required")
                references(item.get("claim_ids"), pid, context)
                if field == "changes" and item.get("category") not in CHANGES:
                    errors.append(f"{context}: invalid change category")
        for index, unknown in enumerate(card.get("unknowns", [])):
            if not nonblank(unknown.get("question")) or not nonblank(unknown.get("next_check")):
                errors.append(f"{pid}.unknowns[{index}]: question and next_check required")
    displayed = {cid for card in cards.values() for field in ("earlier_claim_ids", "later_claim_ids") for cid in card.get(field, [])}
    displayed |= {cid for card in cards.values() for field in ("changes", "review_reasons") for item in card.get(field, []) for cid in item.get("claim_ids", [])}
    return {"errors": errors, "warnings": warnings, "stage": stage, "source_count": len(sources),
            "claim_count": len(claims), "card_count": len(cards), "displayed_evidence_claim_count": len(displayed),
            "semantic_support": "incomplete: exact matching does not establish support, attribution, dates, identity or procedural stage",
            "human_review": "pending", "assertion_inventory": assertion_inventory(predictions, packet) if not errors else []}


def calculate_metrics(corpus: dict, predictions: dict, labels: dict, baseline: dict, config: dict, prediction_version="first_pass") -> dict:
    errors = []
    ids = {s["source_id"] for s in corpus["sources"]}
    reference = index_unique(labels.get("labels"), "source_id", "labels", errors)
    if labels.get("reference_type") != "ai_generated_provisional":
        errors.append("reference_type must be ai_generated_provisional")
    if labels.get("run_id") != corpus["run_id"]:
        errors.append("label run_id mismatch")
    if set(reference) != ids or any(row.get("label") not in DECISIONS for row in reference.values()):
        errors.append("labels must cover every unique corpus source exactly once with a valid label")
    methods = {}
    method_rows = {}
    ai_name = "ai_" + prediction_version
    for name, document in (("keyword_baseline", baseline), (ai_name, predictions)):
        rows = index_unique(document.get("article_decisions"), "source_id", name, errors)
        if set(rows) != ids or any(row.get("decision") not in DECISIONS for row in rows.values()):
            errors.append(f"{name}: final expanded corpus coverage required")
        method_rows[name] = rows
    if errors:
        raise ValueError("; ".join(errors))
    disagreements = []
    for name, rows in method_rows.items():
        counts = {key: 0 for key in ("tp", "fp", "fn", "tn")}
        uncertain_counts = {key: 0 for key in DECISIONS}
        decisions = Counter(row["decision"] for row in rows.values())
        for sid in sorted(ids):
            label, decision = reference[sid]["label"], rows[sid]["decision"]
            queued = decision in QUEUED
            if label == "uncertain":
                uncertain_counts[decision] += 1
            elif label == "relevant":
                counts["tp" if queued else "fn"] += 1
            else:
                counts["fp" if queued else "tn"] += 1
            if decision != label:
                disagreements.append({"source_id": sid, "method": name, "reference": label, "prediction": decision,
                                      "queued": queued, "binary_error": label != "uncertain" and queued != (label == "relevant")})
        precision_den = counts["tp"] + counts["fp"]
        retention_den = counts["tp"] + counts["fn"]
        negative_den = counts["fp"] + counts["tn"]
        ratio = lambda num, den: {"numerator": num, "denominator": den, "value": num / den if den else None}
        methods[name] = {"predictions": {key: decisions[key] for key in sorted(DECISIONS)},
                         "queue_count_all_sources": decisions["relevant"] + decisions["uncertain"],
                         "queue_confusion": counts,
                         "binary_reference_denominator": sum(counts.values()),
                         "queue_precision_agreement": ratio(counts["tp"], precision_den),
                         "relevant_retention_agreement": ratio(counts["tp"], retention_den),
                         "definite_negative_review_burden": ratio(counts["fp"], negative_den),
                         "reference_uncertain": {"total": sum(uncertain_counts.values()),
                                                 "queued": uncertain_counts["relevant"] + uncertain_counts["uncertain"],
                                                 "rejected": uncertain_counts["irrelevant"],
                                                 "predictions": dict(sorted(uncertain_counts.items()))}}
    ai = methods[ai_name]
    retention = ai["relevant_retention_agreement"]
    negatives = ai["definite_negative_review_burden"]
    acceptance = {
        "relevant_retention": {"status": "incomplete" if not retention["denominator"] else "pass" if retention["value"] >= config["evaluation"]["min_relevant_retention"] else "fail", "basis": retention},
        "negative_review_burden": {"status": "incomplete" if negatives["denominator"] < config["evaluation"]["min_definite_negatives_for_check"] else "pass" if negatives["numerator"] <= config["evaluation"]["max_definite_negative_promotions"] else "fail", "basis": negatives},
    }
    for key in ("semantic_support", "critical_errors", "lineage", "useful_histories", "uncertainty"):
        acceptance[key] = {"status": "incomplete", "basis": "Requires separate independent audit; deterministic checks cannot adjudicate this criterion."}
    return {"run_id": corpus["run_id"], "prediction_version": prediction_version,
            "reference_type": "AI-generated provisional reference labels, not human ground truth",
            "triage_unit": "one unique source ID in final expanded corpus", "unique_reports": len(ids),
            "reference_counts": dict(sorted(Counter(row["label"] for row in reference.values()).items())),
            "methods": methods, "disagreements": disagreements, "acceptance": acceptance,
            "limitations": ["Purposively selected small corpus; no population recall, coverage, detection-time or time-savings estimate.",
                            "Reference-uncertain items are excluded from binary denominators and reported separately.",
                            "Both relevant and uncertain predictions enter the human review queue.",
                            "AI-generated provisional labels and a pretrained extractor are not human ground truth or a historical foresight test."]}


def build_cases(predictions: dict, corpus: dict, synthetic: bool = False) -> dict:
    sources = {s["source_id"]: s for s in corpus["sources"]}
    cards = {c["proceeding_id"]: c for c in predictions["cards"]}
    cases = []
    for proceeding in predictions["proceedings"]:
        pid = proceeding["proceeding_id"]
        claims = []
        for claim in predictions["claims"]:
            if claim["proceeding_id"] != pid:
                continue
            claims.append({"claim_id": claim["claim_id"], "kind": claim["kind"], "text": claim["text"],
                           "event_date": claim["event_date"], "evidence": [{"source_id": claim["source_id"],
                           "quote": claim["quote"], "locator": claim["locator"], "translation": None}]})
        case_sources = [{"source_id": sid, "url": sources[sid]["url"], "publisher": sources[sid]["publisher"],
                         "published_date": sources[sid]["publication_date"], "retrieved_at": sources[sid]["retrieved_at"],
                         "language": sources[sid]["language"]} for sid in proceeding["source_ids"]]
        review_state = cards.get(pid, {}).get("human_review", "pending") if claims else "needs_sources"
        cases.append({"case_id": pid, "synthetic": synthetic, "title": proceeding["title"], "country_code": "PH",
                      "sources": case_sources, "claims": claims,
                      "review": {"status": review_state, "reviewer": None, "reviewed_at": None,
                                 "notes": "Exploratory AI-assisted preparation; human review pending. Source/translation metadata and AI audit are in experiment sidecars."}})
    result = {"schema_version": "1.0", "cases": cases}
    errors = validate_document(result)
    if errors:
        raise ValueError("Case export invalid: " + "; ".join(errors))
    return result


def h(value) -> str:
    return html.escape(str(value), quote=True)


def md(value) -> str:
    # Markdown remains safe when later interpreted as HTML; escape structural text.
    value = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value)


def safe_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or any(c.isspace() for c in value)
            or any(c in value for c in '<>"\'`\\')):
        raise ValueError("Unsafe citation URL")
    return value


def validate_audit(audit: dict, run_id: str, prediction_version: str, input_hashes: dict, validations: dict) -> None:
    """A semantic pass must identify the exact run and cover the full inventory."""
    if audit.get("run_id") != run_id or audit.get("prediction_version") != prediction_version:
        raise ValueError("Audit run_id or prediction_version mismatch")
    for stage in ("early", "later"):
        expected = input_hashes.get(stage + "_predictions")
        supplied = audit.get("prediction_hashes", {}).get(stage)
        if not expected or not isinstance(supplied, str) or supplied.lower() != expected.lower():
            raise ValueError(f"Audit {stage} prediction hash mismatch or missing")
    allowed = {"semantic_support", "critical_errors", "lineage", "useful_histories", "uncertainty"}
    checks = audit.get("checks")
    if not isinstance(checks, dict) or set(checks) - allowed:
        raise ValueError("Audit contains unknown check names or missing checks object")
    for key, check in checks.items():
        if check.get("status") not in {"pass", "fail", "incomplete"} or not nonblank(check.get("basis")):
            raise ValueError(f"Audit check {key} requires valid status and nonblank basis")
    if any(check["status"] == "pass" for check in checks.values()):
        for stage in ("early", "later"):
            coverage = audit.get("coverage", {}).get(stage, {})
            expected_ids = {row["assertion_id"] for row in validations[stage]["assertion_inventory"]}
            actual_ids = coverage.get("audited_assertion_ids")
            if (coverage.get("status") != "complete" or not expected_ids or not isinstance(actual_ids, list)
                    or not all(isinstance(value, str) for value in actual_ids)
                    or len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != expected_ids):
                raise ValueError(f"Audit pass requires complete {stage} assertion inventory coverage")
            if coverage.get("audited_assertions") != len(expected_ids) or coverage.get("total_assertions") != len(expected_ids):
                raise ValueError(f"Audit {stage} assertion coverage counts mismatch")


def display_quotes(predictions: list[dict], budget: int = 25) -> dict[str, str]:
    """One exact excerpt per unique evidence citation; total words/source <= budget.

    Remaining evidence citations display a locator instead of repeating quotations.
    Complete exact excerpts remain in the local machine-readable evidence file.
    """
    remaining = defaultdict(lambda: budget)
    selected = {}
    for document in predictions:
        for claim in document["claims"]:
            key = f"{document['stage']}:{claim['claim_id']}"
            sid = claim["source_id"]
            words = list(re.finditer(r"\S+", claim["quote"]))
            available = min(remaining[sid], len(words))
            if available:
                selected[key] = claim["quote"][:words[available - 1].end()]
                remaining[sid] -= available
            else:
                selected[key] = ""
    return selected


STYLE = """*{box-sizing:border-box}body{margin:0;background:#f2f5f6;color:#172c38;font:16px/1.65 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:38px 24px 64px}h1,h2,h3{line-height:1.22}h1{font-size:2.25rem;max-width:900px}h2{margin-top:34px}h3{margin-top:24px}a{color:#075d77;overflow-wrap:anywhere}p,li{max-width:100ch}header,.card,.panel{background:white;border:1px solid #d3dce1;border-radius:10px;padding:24px;margin:20px 0}header{border-top:6px solid #19778b}.badge{display:inline-block;background:#fff2cd;color:#604614;padding:3px 10px;border-radius:4px;font-size:.85rem}.muted{color:#49616e}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{text-align:left;padding:10px;border-bottom:1px solid #d3dce1;vertical-align:top}blockquote{border-left:3px solid #8ab4c2;padding-left:12px;margin-left:0}.evidence{font-size:.9rem}.source{padding:10px 0;border-bottom:1px solid #d3dce1}.scroll{overflow:auto}.pass{color:#175c31}.fail{color:#ab2222}.incomplete{color:#826007}details{margin:12px 0}summary{cursor:pointer;font-weight:600}@media(max-width:760px){.grid{grid-template-columns:1fr}main{padding:18px 12px}header,.card,.panel{padding:18px}h1{font-size:1.75rem}}@media print{body{background:white}main{padding:0}.card{break-inside:avoid}a{color:inherit}}"""


def render_report(corpus, early, later, metrics, validations, output: Path, input_hashes: dict, audit=None, audit_sha256=None):
    sources = {s["source_id"]: s for s in corpus["sources"]}
    quotes = display_quotes([later, early])
    acceptance = json.loads(json.dumps(metrics["acceptance"]))
    if audit is not None:
        validate_audit(audit, corpus["run_id"], metrics["prediction_version"], input_hashes, validations)
        for key, check in audit.get("checks", {}).items():
            if key in acceptance and key not in {"relevant_retention", "negative_review_burden"}:
                if check.get("status") not in {"pass", "fail", "incomplete"}:
                    raise ValueError("Audit status must be pass, fail, or incomplete")
                acceptance[key] = {"status": check["status"], "basis": check.get("basis"), "adjudicator": "separate AI audit; not human review"}
    bind_output_directory(output, corpus["run_id"], metrics.get("prediction_version", "first_pass"), input_hashes)
    output.mkdir(parents=True, exist_ok=True)
    save_text(output / "style.css", STYLE + "\n")
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
             '<title>Philippines pilot — exploratory evidence report</title><link rel="stylesheet" href="style.css"><main>',
             '<header><span class="badge">Exploratory preparation · Human review pending</span><h1>Philippines case timeline pilot</h1>',
             f'<p>Run <code>{h(corpus["run_id"])}</code>; prediction version {h(metrics.get("prediction_version", "first_pass"))}. Publication-ordered reconstruction of public reporting. Historical text availability is unverified unless stated. These cards do not establish current case status.</p>',
             '<p>AI claims and AI-generated provisional reference labels require human review. Organizer priorities, prework rules and submission eligibility remain unresolved.</p>',
             '<nav><a href="../RESULTS.md">Results and limits</a> · <a href="../AUDIT.md">Independent AI audit</a> · <a href="../REVIEW_QUEUE.md">Human review queue</a> · <a href="cards.md">Markdown cards</a> · <a href="COMMANDS.md">Rerun commands</a></nav></header>']
    parts.append(f'<section class="panel"><h2>Corpus and observations</h2><p>{len(sources)} unique reports; {len(later["proceedings"])} proceeding records; {len(later["cards"])} final cards. Early and later source snapshots are audited separately and counted once in final article triage. Different reports/publishers do not establish independent corroboration.</p></section>')
    parts.append('<section class="panel"><h2>Agreement with provisional reference labels</h2><div class="scroll"><table><thead><tr><th>Method</th><th>Decisions: relevant / uncertain / irrelevant</th><th>Queue TP / FP / FN / TN</th><th>Queue precision</th><th>Relevant retention</th><th>Negative burden</th></tr></thead><tbody>')
    def ratio(item):
        return f'{item["numerator"]}/{item["denominator"]}' + (f' ({item["value"]:.1%})' if item["value"] is not None else ' (undefined)')
    for name, measure in metrics["methods"].items():
        counts = measure["predictions"]
        confusion = measure["queue_confusion"]
        parts.append(f'<tr><th>{h(name.replace("_", " "))}</th><td>{counts["relevant"]} / {counts["uncertain"]} / {counts["irrelevant"]}</td><td>{confusion["tp"]} / {confusion["fp"]} / {confusion["fn"]} / {confusion["tn"]}</td><td>{ratio(measure["queue_precision_agreement"])}</td><td>{ratio(measure["relevant_retention_agreement"])}</td><td>{ratio(measure["definite_negative_review_burden"])}</td></tr>')
    parts.append('</tbody></table></div><p>Relevant and uncertain predictions both enter the queue. Reference-uncertain reports are excluded from binary denominators. These are agreement figures on a small selected corpus, not population recall.</p>')
    for name, measure in metrics["methods"].items():
        uncertain = measure["reference_uncertain"]
        parts.append(f'<p>{h(name)}: {measure["binary_reference_denominator"]} definite reference labels; {uncertain["total"]} uncertain reference items ({uncertain["queued"]} queued, {uncertain["rejected"]} rejected, {uncertain["predictions"]["uncertain"]} predicted uncertain).</p>')
    parts.append('<details><summary>Per-source disagreements</summary><table><tr><th>Source</th><th>Method</th><th>Reference</th><th>Prediction</th><th>Binary queue error</th></tr>')
    for row in metrics["disagreements"]:
        parts.append(f'<tr><td><a href="#source-{h(row["source_id"])}">{h(row["source_id"])}</a></td><td>{h(row["method"])}</td><td>{h(row["reference"])}</td><td>{h(row["prediction"])}</td><td>{h(row["binary_error"])}</td></tr>')
    parts.append('</table></details></section><section class="panel"><h2>Continuation checks</h2><ul>')
    for key, check in acceptance.items():
        basis = check["basis"] if isinstance(check["basis"], str) else json.dumps(check["basis"], ensure_ascii=False)
        parts.append(f'<li><strong>{h(key.replace("_", " "))}</strong>: <span class="{h(check["status"])}">{h(check["status"])}</span> — {h(basis)}</li>')
    parts.append('</ul><p>Exact quote and locator checks only establish text presence. Semantic support, dates, attribution, proceeding boundaries and procedural implications require the separate audit.</p>')
    for stage in ("early", "later"):
        v = validations[stage]
        coverage = (audit or {}).get("coverage", {}).get(stage)
        coverage_text = f'{coverage.get("audited_assertions", "unknown")}/{coverage.get("total_assertions", "unknown")} assertion entries; {coverage.get("status", "incomplete")}' if coverage else "incomplete"
        parts.append(f'<p>{stage.title()} audit inventory: {v["claim_count"]} extracted claims, {v["displayed_evidence_claim_count"]} evidence claims used by cards, {len(v["assertion_inventory"])} assertion and metadata entries. Separate audit coverage: {h(coverage_text)}.</p>')
    parts.append('</section>')
    markdown = ["# Philippines case timeline pilot", "", f"Run: {corpus['run_id']}", "", "Exploratory preparation. Human review pending. Publication-ordered reconstruction; historical/current status is not established.", "", "[Results](../RESULTS.md) · [Independent AI audit](../AUDIT.md) · [Human review queue](../REVIEW_QUEUE.md)", ""]
    for document in (later, early):
        stage = document["stage"]
        claim_map = {c["claim_id"]: c for c in document["claims"]}
        proc_map = {p["proceeding_id"]: p for p in document["proceedings"]}
        title = "Final expanded-source cards" if stage == "later" else "Frozen early-stage cards"
        parts.append(f'<h2>{title}</h2>')
        markdown.extend([f"## {title}", ""])
        if stage == "later":
            parts.append('<p>The earlier columns below are reconstructed by the later worker from early-source membership. The independent frozen early predictions are preserved in the following section; no automatic name-based matching has been applied.</p>')
        for card in document["cards"]:
            pid = card["proceeding_id"]
            proceeding = proc_map[pid]
            local_md = [f"### {md(card['title'])}", "", f"Proceeding: `{pid}` · Human review: {card['human_review']}", "", "People named: " + "; ".join(md(n) for n in proceeding["defendants"]), ""]
            parts.append(f'<article class="card" id="{stage}-{h(pid)}"><span class="badge">Human review: {h(card["human_review"])}</span><h3>{h(card["title"])}</h3><p>Proceeding: <code>{h(pid)}</code><br>People named: {h("; ".join(proceeding["defendants"]))}</p>')
            if proceeding.get("linkage_uncertainty"):
                parts.append(f'<p><strong>Linkage uncertainty:</strong> {h(proceeding["linkage_uncertainty"])}</p>')
                local_md.extend(["Linkage uncertainty: " + md(proceeding["linkage_uncertainty"]), ""])
            if proceeding["related_proceeding_ids"]:
                parts.append(f'<p>Related proceedings kept separate: {h(", ".join(proceeding["related_proceeding_ids"]))}</p>')
                local_md.extend(["Related proceedings kept separate: " + md(", ".join(proceeding["related_proceeding_ids"])), ""])
            def refs_html(refs):
                return " ".join(f'<a href="#{stage}-evidence-{h(cid)}">[{h(cid)}]</a>' for cid in refs)
            def refs_md(refs):
                return " ".join(f"[{md(cid)}](#{stage}-evidence-{cid})" for cid in refs)
            parts.append('<div class="grid">')
            for field, heading in (("earlier_claim_ids", "Earlier source view"), ("later_claim_ids", "Later source view")):
                parts.append(f'<section><h3>{heading}</h3><ul>')
                local_md.extend([f"#### {heading}", ""])
                if not card[field]:
                    parts.append('<li>No claims supplied for this view.</li>')
                    local_md.append("No claims supplied for this view.")
                for cid in card[field]:
                    claim = claim_map[cid]
                    event = claim["event_date"] or "unknown"
                    parts.append(f'<li>{h(claim["text"])} {refs_html([cid])}<br><span class="muted">Event date: {h(event)} · Attributed to: {h(claim["attribution"])}</span></li>')
                    local_md.append(f"- {md(claim['text'])} {refs_md([cid])} Event date: {event}. Attribution: {md(claim['attribution'])}.")
                parts.append('</ul></section>')
                local_md.append("")
            parts.append('</div>')
            for field, heading in (("changes", "What changed"), ("review_reasons", "Why review")):
                parts.append(f'<h3>{heading}</h3><ul>')
                local_md.extend([f"#### {heading}", ""])
                if not card[field]:
                    parts.append('<li>No change/review assertion supplied in this snapshot.</li>')
                    local_md.append("No change/review assertion supplied in this snapshot.")
                for item in card[field]:
                    prefix = item.get("category", "candidate review reason").replace("_", " ")
                    parts.append(f'<li><strong>{h(prefix)}:</strong> {h(item["text"])} {refs_html(item["claim_ids"])}</li>')
                    local_md.append(f"- **{md(prefix)}:** {md(item['text'])} {refs_md(item['claim_ids'])}")
                parts.append('</ul>')
                local_md.append("")
            parts.append('<h3>Still unknown</h3><p>Missing from the permitted source packet; these are not negative findings.</p><ul>')
            local_md.extend(["#### Still unknown", "", "Missing from the permitted source packet; these are not negative findings.", ""])
            for unknown in card["unknowns"]:
                parts.append(f'<li>{h(unknown["question"])} <strong>Next check:</strong> {h(unknown["next_check"])}</li>')
                local_md.append(f"- {md(unknown['question'])} Next check: {md(unknown['next_check'])}")
            evidence_file = "cases.json" if stage == "later" else "cases.early.json"
            parts.append(f'</ul><h3>Evidence and locators</h3><p class="muted">Displayed verbatim excerpts are capped at 25 words per source across this report. Other citations retain exact paragraph locators; full excerpts are in local {evidence_file}.</p>')
            local_md.extend(["", "#### Evidence and locators", "", f"Displayed excerpts share a report-wide limit of 25 quoted words per source. Full exact excerpts are in local {evidence_file}.", ""])
            cited = []
            for field in ("earlier_claim_ids", "later_claim_ids"):
                cited.extend(card[field])
            for field in ("changes", "review_reasons"):
                for item in card[field]:
                    cited.extend(item["claim_ids"])
            for cid in dict.fromkeys(cited):
                claim = claim_map[cid]
                sid = claim["source_id"]
                source = sources[sid]
                quote = quotes[f"{stage}:{cid}"]
                url = safe_url(source["url"])
                parts.append(f'<div class="evidence" id="{stage}-evidence-{h(cid)}"><p><strong>{h(cid)}</strong> · <a href="{h(url)}">{h(sid)}: {h(source["publisher"])}</a> · {h(claim["locator"])} · {h(claim["attribution"])}.</p>')
                if quote:
                    suffix = " [display excerpt shortened]" if quote != claim["quote"] else ""
                    parts.append(f'<blockquote>{h(quote)}</blockquote><p class="muted">{h(suffix)}</p>')
                else:
                    parts.append('<p class="muted">See cited paragraph; quotation omitted here to limit total verbatim display.</p>')
                parts.append(f'<p class="muted"><a href="{evidence_file}">Full exact excerpt and locator in {evidence_file}</a>, claim <code>{h(cid)}</code>.</p></div>')
                local_md.extend([f'<a id="{stage}-evidence-{cid}"></a>', f"- **{md(cid)}**: [{md(sid + ': ' + source['publisher'])}](<{url}>) · {md(claim['locator'])} · {md(claim['attribution'])}."])
                if quote:
                    local_md.extend(["", "> " + md(quote), ""])
                else:
                    local_md.extend(["", "Quotation omitted here to limit total verbatim display.", ""])
                local_md.extend([f"[Full exact excerpt and locator in {evidence_file}](<{evidence_file}>), claim `{cid}`.", ""])
            parts.append('<h3>Source-stage metadata</h3>')
            local_md.extend(["", "#### Source-stage metadata", ""])
            for sid in proceeding["source_ids"]:
                source = sources[sid]
                description = f"{sid} — {source['publisher']}; published {source['publication_date'] or 'unknown'}; updated {source['update_date'] or 'unknown'}; captured {source['retrieved_at']}; language {source['language']}; translation {source['translation_status']}; lineage {source['lineage_group'] or 'unknown'}; historical availability {source['historical_availability']}."
                parts.append(f'<p class="source">{h(description)}</p>')
                local_md.append("- " + md(description))
                if source["update_note"]:
                    parts.append(f'<p class="muted">Update note: {h(source["update_note"])}</p>')
                    local_md.append("  Update note: " + md(source["update_note"]))
            parts.append('</article>')
            local_md.append("")
            markdown.extend(local_md)
            individual_md = "\n".join(local_md).replace(f"](<{evidence_file}>)", f"](<../{evidence_file}>)")
            save_text(output / "cards" / f"{stage}-{pid}.md", individual_md + "\n")
    parts.append('<section class="panel"><h2>Source register</h2>')
    for sid, source in sources.items():
        parts.append(f'<div class="source" id="source-{h(sid)}"><a href="{h(safe_url(source["url"]))}"><strong>{h(sid)}</strong> · {h(source["title"])}</a><p>{h(source["publisher"])} · Published {h(source["publication_date"] or "unknown")} · Access: {h(source["access_status"])} · Lineage: {h(source["lineage_group"] or "unknown")}</p></div>')
    parts.append('</section><footer><p>Local static report. No live monitoring. Scripts consume saved AI predictions and do not perform semantic inference. Frozen input hashes are recorded in input_hashes.json.</p></footer></main></html>')
    save_text(output / "index.html", "\n".join(parts) + "\n")
    save_text(output / "cards.md", "\n".join(markdown) + "\n")
    save_json(output / "input_hashes.json", input_hashes)
    save_immutable_json(output / "metrics.json", metrics)
    save_json(output / "acceptance.json", acceptance)
    if audit is not None:
        save_json(output / "audit_provenance.json", {"run_id": corpus["run_id"], "prediction_version": metrics["prediction_version"],
                                                   "audit_file_sha256": audit_sha256, "prediction_hashes": audit["prediction_hashes"],
                                                   "coverage": audit["coverage"]})
    save_json(output / "validation.json", validations)
    save_json(output / "audit_inventory.json", {"early": validations["early"]["assertion_inventory"], "later": validations["later"]["assertion_inventory"]})


def run_pipeline(args) -> int:
    paths = {key: getattr(args, key) for key in ("corpus", "early_packet", "later_packet", "early_predictions", "later_predictions", "labels", "config", "contract", "protocol")}
    documents = {key: load_json(path) for key, path in paths.items()}
    hashes = {key: sha256(path) for key, path in paths.items()}
    frozen = load_json(args.frozen_hashes)
    for key in ("corpus", "early_packet", "later_packet", "early_predictions", "later_predictions", "labels"):
        if key not in frozen or hashes[key] != str(frozen[key]).lower():
            raise ValueError(f"Frozen hash mismatch or missing expected hash: {key}")
    for key in ("config", "contract"):
        if hashes[key] != str(documents["protocol"].get(key + "_sha256", "")).lower():
            raise ValueError(f"Protocol frozen hash mismatch: {key}")
    corpus, config = documents["corpus"], documents["config"]
    if corpus["run_id"] != documents["protocol"]["run_id"] or corpus["run_id"] != documents["contract"]["run_id"]:
        raise ValueError("Frozen run ID mismatch")
    bind_output_directory(args.output, corpus["run_id"], args.prediction_version, hashes)
    validations = {"corpus": check_corpus(corpus, config)}
    for stage in ("early", "later"):
        validations[stage + "_packet"] = check_packet(documents[stage + "_packet"], corpus, stage)
        validations[stage] = check_predictions(documents[stage + "_predictions"], documents[stage + "_packet"])
    if set(documents["later_packet"]["early_source_ids"]) != {s["source_id"] for s in documents["early_packet"]["sources"]}:
        raise ValueError("Expanded packet early membership differs from frozen early packet")
    if {s["source_id"] for s in documents["later_packet"]["sources"]} != {s["source_id"] for s in corpus["sources"]}:
        raise ValueError("Later packet must equal final expanded corpus")
    failures = [error for result in validations.values() for error in result["errors"]]
    # Write failures in the engineer's output area; never mutate saved predictions.
    if failures:
        save_json(args.output / "validation.json", validations)
        print("Validation failed:\n" + "\n".join(failures), file=sys.stderr)
        return 1
    baseline = run_baseline(corpus, config)
    metrics = calculate_metrics(corpus, documents["later_predictions"], documents["labels"], baseline, config, args.prediction_version)
    cases = build_cases(documents["later_predictions"], corpus, args.synthetic)
    early_cases = build_cases(documents["early_predictions"], corpus, args.synthetic)
    audit = load_json(args.audit_checks) if args.audit_checks else None
    if audit is not None:
        validate_audit(audit, corpus["run_id"], args.prediction_version, hashes, validations)
    # Fail before rendering if this directory belongs to different scored inputs.
    save_immutable_json(args.output / "metrics.json", metrics)
    render_report(corpus, documents["early_predictions"], documents["later_predictions"], metrics, validations, args.output, hashes, audit,
                  sha256(args.audit_checks) if args.audit_checks else None)
    save_json(args.output / "baseline.json", baseline)
    save_json(args.output / "cases.json", cases)
    save_json(args.output / "cases.early.json", early_cases)
    save_json(args.output / "source_metadata.json", {"run_id": corpus["run_id"], "sources": [{key: value for key, value in s.items() if key != "body"} for s in corpus["sources"]]})
    queue = [row for row in documents["later_predictions"]["article_decisions"] if row["decision"] in QUEUED]
    save_json(args.output / "article_review_queue.json", {"run_id": corpus["run_id"], "human_review": "pending", "articles": queue})
    def ps_quote(value):
        return "'" + str(value).replace("'", "''") + "'"
    command = ".\\.venv\\Scripts\\python.exe -m scripts.experiment_01 run " + " ".join("--" + key.replace("_", "-") + " " + ps_quote(value) for key, value in paths.items())
    command += " --frozen-hashes " + ps_quote(args.frozen_hashes) + " --output " + ps_quote(args.output)
    if args.audit_checks:
        command += " --audit-checks " + ps_quote(args.audit_checks)
    if args.synthetic:
        command += " --synthetic"
    command += " --prediction-version " + args.prediction_version
    save_text(args.output / "COMMANDS.md", "# Deterministic rerun\n\nFrom the workspace root in PowerShell:\n\n```powershell\n" + command + "\n.\\.venv\\Scripts\\python.exe scripts/validate_data.py " + ps_quote(args.output / "cases.json") + " " + ps_quote(args.output / "cases.early.json") + "\n.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v\n```\n\nThis loads frozen AI outputs. It does not invoke a model, browse, or regenerate predictions. No run-time timestamp is inserted into deterministic outputs.\n\nTo regenerate AI predictions, ask Codex to launch a fresh bounded extraction worker using the frozen contract and permitted stage packet, following the saved role prompt. Preserve the first-pass files and hashes; only the lead may authorize the one separate repair pass. A new prediction is not a deterministic rerun.\n")
    print(f"PASS deterministic processing: {len(corpus['sources'])} unique reports, {len(cases['cases'])} proceedings; human review pending. Output: {args.output}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-corpus", help="Check metadata, body hashes and duplicate URLs")
    check.add_argument("--corpus", type=Path, required=True)
    check.add_argument("--config", type=Path, required=True)
    baseline = commands.add_parser("baseline", help="Apply frozen role AND proceeding substring terms")
    for name in ("corpus", "config", "output"):
        baseline.add_argument("--" + name, type=Path, required=True)
    validate = commands.add_parser("check-predictions", help="Check saved AI output; no semantic inference")
    for name in ("predictions", "packet", "output"):
        validate.add_argument("--" + name, type=Path, required=True)
    run = commands.add_parser("run", help="Validate frozen saved inputs, calculate agreement, render local exports")
    for name in ("corpus", "early-packet", "later-packet", "early-predictions", "later-predictions", "labels", "config", "contract", "protocol", "frozen-hashes", "output"):
        run.add_argument("--" + name, type=Path, required=True)
    run.add_argument("--audit-checks", type=Path)
    run.add_argument("--prediction-version", choices=("first_pass", "repair_01"), default="first_pass")
    run.add_argument("--synthetic", action="store_true", help="Mark all exported case records synthetic; tests only")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return run_pipeline(args)
        if args.command == "check-corpus":
            result = check_corpus(load_json(args.corpus), load_json(args.config))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return bool(result["errors"])
        if args.command == "baseline":
            save_json(args.output, run_baseline(load_json(args.corpus), load_json(args.config)))
            return 0
        if args.command == "check-predictions":
            result = check_predictions(load_json(args.predictions), load_json(args.packet))
            save_json(args.output, result)
            print(json.dumps({key: value for key, value in result.items() if key != "assertion_inventory"}, ensure_ascii=False, indent=2))
            return bool(result["errors"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
