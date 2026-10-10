"""Bounded draft integrity checks. Software integrity is not legal validation."""
from datetime import date, datetime
import json
import math
from pathlib import Path
import re

from .server import APIError, identifier, public_url, string
from .rights import DIMENSIONS as RIGHTS_DIMENSIONS, RUBRIC, RUBRIC_VERSION

KEYWORDS = {"$schema", "$id", "$defs", "$ref", "title", "description", "type", "const", "enum", "required", "properties", "additionalProperties", "items", "minItems", "maxItems", "uniqueItems", "minLength", "maxLength", "pattern", "format", "minimum", "maximum", "allOf", "anyOf", "oneOf", "if", "then", "else"}

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("Non-finite JSON value: " + value)


def finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Non-finite JSON number: " + value)
    return parsed


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object,
                      parse_constant=invalid_constant, parse_float=finite_float)


def check_schema(rule):
    if not isinstance(rule, dict):
        raise ValueError("Schema rules must be objects.")
    unknown = rule.keys() - KEYWORDS
    if unknown:
        raise ValueError("Unsupported schema keywords: " + str(sorted(unknown)))
    for group in ("$defs", "properties"):
        for child in rule.get(group, {}).values():
            check_schema(child)
    for key in ("items", "if", "then", "else"):
        if key in rule:
            check_schema(rule[key])
    if isinstance(rule.get("additionalProperties"), dict):
        check_schema(rule["additionalProperties"])
    for key in ("allOf", "anyOf", "oneOf"):
        for child in rule.get(key, []):
            check_schema(child)
    if rule.get("format") not in {None, "date", "date-time", "uri"}:
        raise ValueError("Unsupported schema format.")


def json_equal(left, right):
    return not (isinstance(left, bool) != isinstance(right, bool)) and left == right


def type_matches(value, kind):
    return {"null": value is None, "object": isinstance(value, dict), "array": isinstance(value, list),
            "string": isinstance(value, str), "boolean": type(value) is bool, "integer": type(value) is int,
            "number": type(value) in {int, float}}.get(kind, False)


def valid_format(value, kind):
    try:
        if kind == "date":
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) and bool(date.fromisoformat(value))
        if kind == "date-time":
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return "T" in value and parsed.utcoffset() is not None
        if kind == "uri":
            from urllib.parse import urlsplit
            parsed = urlsplit(value)
            return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not any(c.isspace() for c in value)
    except ValueError:
        return False
    return True


def shape(value, rule, root, path="$", errors=None):
    errors = [] if errors is None else errors
    if "$ref" in rule:
        ref = rule["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise ValueError("Only local JSON schema references are supported.")
        resolved = root
        for segment in ref[2:].split("/"):
            resolved = resolved[segment.replace("~1", "/").replace("~0", "~")]
        return shape(value, resolved, root, path, errors)
    for child in rule.get("allOf", []):
        shape(value, child, root, path, errors)
    for combiner in ("anyOf", "oneOf"):
        if combiner in rule:
            passes = sum(not shape(value, child, root, path) for child in rule[combiner])
            if (combiner == "anyOf" and passes == 0) or (combiner == "oneOf" and passes != 1):
                errors.append(path + ": failed " + combiner)
    if "if" in rule:
        branch = "else" if shape(value, rule["if"], root, path) else "then"
        if branch in rule:
            shape(value, rule[branch], root, path, errors)
    if "type" in rule:
        kinds = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
        if not any(type_matches(value, kind) for kind in kinds):
            errors.append(path + ": invalid type")
            return errors
    if "const" in rule and not json_equal(value, rule["const"]):
        errors.append(path + ": unexpected constant")
    if "enum" in rule and not any(json_equal(value, choice) for choice in rule["enum"]):
        errors.append(path + ": unexpected enum value")
    if isinstance(value, dict):
        for key in rule.get("required", []):
            if key not in value:
                errors.append(path + "." + key + ": required field missing")
        properties = rule.get("properties", {})
        for key, child in value.items():
            if key in properties:
                shape(child, properties[key], root, path + "." + key, errors)
            elif rule.get("additionalProperties") is False:
                errors.append(path + "." + key + ": unexpected field")
            elif isinstance(rule.get("additionalProperties"), dict):
                shape(child, rule["additionalProperties"], root, path + "." + key, errors)
    elif isinstance(value, list):
        if len(value) < rule.get("minItems", 0) or len(value) > rule.get("maxItems", len(value)):
            errors.append(path + ": array length outside bounds")
        if rule.get("uniqueItems") and len({json.dumps(item, sort_keys=True, allow_nan=False) for item in value}) != len(value):
            errors.append(path + ": repeated array item")
        if "items" in rule:
            for index, child in enumerate(value):
                shape(child, rule["items"], root, path + "[" + str(index) + "]", errors)
    elif isinstance(value, str):
        if len(value) < rule.get("minLength", 0) or len(value) > rule.get("maxLength", len(value)):
            errors.append(path + ": string length outside bounds")
        if "pattern" in rule and re.search(rule["pattern"], value) is None:
            errors.append(path + ": string pattern mismatch")
        if "format" in rule and not valid_format(value, rule["format"]):
            errors.append(path + ": invalid " + rule["format"])
    elif type(value) in {int, float}:
        if value < rule.get("minimum", value) or value > rule.get("maximum", value):
            errors.append(path + ": number outside bounds")
    return errors


def parse_json(raw, field):
    """Parse exact original bytes/text without accepting duplicate or nonfinite JSON."""
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > 750000:
        raise APIError(field + ' must be raw UTF-8 JSON text of at most 750000 bytes.')
    try:
        return json.loads(raw.lstrip('\ufeff'), object_pairs_hook=unique_object,
                          parse_constant=invalid_constant, parse_float=finite_float)
    except (ValueError, RecursionError) as exc:
        raise APIError(field + ': malformed JSON (' + str(exc)[:200] + ').', 400, 'draft_schema_error') from exc


def schema_for(cid, supplied):
    schema = json.loads((Path(__file__).resolve().parents[1] / 'schemas/ai-draft.schema.json').read_text(encoding='utf-8'))
    schema.pop('title', None)
    properties = schema['properties']
    properties['dossier_id'] = {'type': 'string', 'enum': [cid]}
    aps = [p['passage_id'] for p in supplied['factual_passages']]
    acs = [p['proposition_id'] for p in supplied['identifier_links']]
    sources = [s['source_id'] for s in supplied['source_metadata']]
    standards = [s['passage_id'] for s in supplied['standards']['passages']]
    enum = lambda values: {'type': 'string', 'enum': values}
    def visit(value):
        if isinstance(value, dict):
            for key, child in list(value.get('properties', {}).items()):
                if key in {'passage_ids', 'factual_passage_ids', 'support_passage_ids', 'contrary_passage_ids'}:
                    child['items'] = enum(aps)
                elif key == 'proposition_ids':
                    child['items'] = enum(acs)
                elif key == 'standard_passage_ids':
                    child['items'] = enum(standards)
                elif key == 'source_review_ids':
                    child['items'] = enum(acs + aps)
                elif key == 'passage_id':
                    value['properties'][key] = enum(aps)
                elif key == 'source_id':
                    value['properties'][key] = enum(sources)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(schema)
    return schema


def validate_input(cid, supplied, candidate):
    """Only the frozen clean-input shape, matched to this case's actual intake."""
    required = {'format', 'task', 'output_request', 'cutoff', 'units', 'source_metadata', 'factual_passages',
                'identifier_links', 'standards', 'rubric', 'constraints', 'review_status', 'prior_exposure_limit'}
    if not isinstance(supplied, dict) or set(supplied) != required or supplied.get('format') != 'part2-clean-input/1':
        raise APIError('Expected the bounded part2-clean-input/1 contract, with no extra inputs.', 400, 'draft_input_error')
    if supplied['review_status'] != 'human_review_pending' or supplied['rubric'] != RUBRIC:
        raise APIError('Input must retain the exact current rubric and pending status.', 400, 'draft_input_error')
    allowed_nested = {
        'cutoff': {'latest_selected_document_date', 'date_role', 'current_status_as_of_2026_10_10', 'current_status_verified', 'current_status'},
        'units': {'dossier', 'case_reference', 'case_identity', 'persons', 'individual_arrest_notice', 'reports', 'arrest_event', 'name_variations', 'identity_resolution'},
        'standards': {'rubric_version', 'stage_guards', 'source_metadata', 'passages', 'version_limits', 'qualified_legal_review'},
    }
    for field, allowed in allowed_nested.items():
        if not isinstance(supplied[field], dict) or set(supplied[field]) - allowed:
            raise APIError('Unexpected clean-input ' + field + ' metadata; extra files/instructions/credentials are outside this route.', 400, 'draft_input_error')
    if not isinstance(supplied['constraints'], list) or any(not isinstance(c, str) for c in supplied['constraints']):
        raise APIError('Clean-input constraints must be a list of bounded text rules.')
    if not isinstance(supplied['factual_passages'], list) or not 1 <= len(supplied['factual_passages']) <= 20:
        raise APIError('Bounded input needs 1-20 supplied passages.')
    if not isinstance(supplied['identifier_links'], list) or not 1 <= len(supplied['identifier_links']) <= 20:
        raise APIError('Bounded input needs 1-20 claim/passage bridge links.')
    if not isinstance(supplied['source_metadata'], list) or not 1 <= len(supplied['source_metadata']) <= 10:
        raise APIError('Bounded input needs 1-10 supplied source metadata rows.')
    passages, sources, links = {}, {}, {}
    for source in supplied['source_metadata']:
        if set(source) - {'source_id', 'title', 'publisher', 'url', 'publication_date', 'document_date', 'document_date_role', 'enclosure_date', 'original_retrieved_at', 'language', 'translation_status', 'source_dependence', 'transcription_status'}:
            raise APIError('Unexpected factual-source metadata; use only the clean evidence contract.', 400, 'draft_input_error')
        sid = identifier(source.get('source_id'), 'source ID')
        if sid in sources:
            raise APIError('Repeated clean-input source ID.')
        public_url(source.get('url'))
        sources[sid] = source
    candidate_sources = {s['id']: s for s in candidate['sources']}
    if set(sources) != set(candidate_sources):
        raise APIError('Draft sources must match exactly this case intake.', 400, 'draft_citation_error')
    for sid, source in sources.items():
        if source['url'] != candidate_sources[sid]['url'] or source.get('title') != candidate_sources[sid]['title']:
            raise APIError('Draft source URL/title differs from this case intake.', 400, 'draft_citation_error')
    for passage in supplied['factual_passages']:
        if set(passage) - {'passage_id', 'source_id', 'quote', 'locator', 'transcription_method', 'surrounding_context_note', 'date_roles', 'uncertainty'}:
            raise APIError('Unexpected factual-passage fields.', 400, 'draft_input_error')
        pid = identifier(passage.get('passage_id'), 'passage ID')
        if pid in passages or passage.get('source_id') not in sources:
            raise APIError('Repeated/unresolved passage or source.', 400, 'draft_citation_error')
        string(passage.get('quote'), 'passage quote', 24000)
        locator = passage.get('locator')
        if not isinstance(locator, dict) or set(locator) != {'pdf_page', 'printed_page', 'paragraph_or_heading'}:
            raise APIError('Passage needs exact PDF/printed page roles and paragraph heading.')
        if type(locator['pdf_page']) is not int or locator['pdf_page'] < 1 or (locator['printed_page'] is not None and (type(locator['printed_page']) is not int or locator['printed_page'] < 1)):
            raise APIError('Invalid passage PDF/printed page.')
        string(locator['paragraph_or_heading'], 'passage heading', 2000)
        if not isinstance(passage.get('date_roles'), dict):
            raise APIError('Passage must preserve explicit date roles.')
        for role, value in passage['date_roles'].items():
            if value is not None and (not isinstance(value, str) or (not role.endswith('_note') and not valid_format(value, 'date'))):
                raise APIError('Passage date roles must contain valid dates/null; qualified notes stay text.')
        passages[pid] = passage
    for row in supplied['identifier_links']:
        if not isinstance(row, dict) or set(row) != {'proposition_id', 'support_passage_ids'}:
            raise APIError('Invalid AC/AP bridge shape.')
        ac = identifier(row['proposition_id'], 'claim ID')
        pids = row['support_passage_ids']
        if ac in links or not isinstance(pids, list) or not pids or len(pids) != len(set(pids)) or not set(pids) <= set(passages):
            raise APIError('Repeated/unresolved AC/AP bridge.', 400, 'draft_citation_error')
        links[ac] = set(pids)
    claims = {c['id']: c for c in candidate['claims']}
    if set(links) != set(claims):
        raise APIError('Draft bridge must contain exactly the actual intake claim IDs.', 400, 'draft_citation_error')
    for cid, pids in links.items():
        claim = claims[cid]
        if not any(claim['source_id'] == passages[p]['source_id'] and claim['excerpt'] in passages[p]['quote'] for p in pids):
            raise APIError(cid + ': source/excerpt does not match supplied AP bridge.', 400, 'draft_citation_error')
    standards = supplied['standards']
    if not isinstance(standards, dict) or standards.get('rubric_version') != RUBRIC_VERSION or standards.get('qualified_legal_review') != 'pending':
        raise APIError('Standards must retain pending qualified review and matching rubric.')
    ids = [p.get('passage_id') for p in standards.get('passages', [])]
    if not ids or len(ids) != len(set(ids)) or any(not isinstance(p, str) for p in ids):
        raise APIError('Standard passage IDs must be unique and supplied.')
    return passages, links


def validate_draft(cid, draft, supplied, candidate, supplied_schema=None):
    passages, links = validate_input(cid, supplied, candidate)
    expected_schema = schema_for(cid, supplied)
    if supplied_schema is not None and supplied_schema != expected_schema:
        raise APIError('Draft schema does not match the bounded runtime contract.', 400, 'draft_schema_error')
    errors = shape(draft, expected_schema, expected_schema)
    if errors:
        raise APIError('Draft schema: ' + '; '.join(errors[:8]), 400, 'draft_schema_error')
    mappings = draft['assessment_mappings']
    if len(mappings) != 20 or {m['dimension_id'] for m in mappings} != {d['id'] for d in RIGHTS_DIMENSIONS} or any(m['mapping'] is not None for m in mappings):
        errors.append('All twenty rights mappings must occur exactly once and remain null.')
    if not 1 <= len(draft['summary']) <= 6 or not draft['limitations']:
        errors.append('A bounded summary and explicit limitations are required.')
    stage_guards = supplied['standards'].get('stage_guards', [])
    groups = {'preliminary_investigation', 'criminal_charge_notice', 'arrest_information'}
    if len(draft['stage_questions']) != 3 or {q['stage'] for q in draft['stage_questions']} != groups:
        errors.append('Keep three distinct unresolved stage/question groups.')
    for row in draft['stage_questions']:
        if not row['questions'] or not row['missing_facts']:
            errors.append('Stage questions/missing facts must remain explicit.')
    options = draft['options']
    if len(options) != 2 or {(o['option_id'], o['proposed_disposition']) for o in options} != {('verify_records', 'prepare_verify'), ('defer_public_route', 'defer')}:
        errors.append('Compare the bounded verification and specified deferral alternatives.')
    contrary = set()
    for claim in candidate['claims']:
        if claim.get('attribution_kind') == 'government_position':
            contrary.update(links[claim['id']])
    used_ap, used_ac = set(), set()
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {'passage_ids', 'factual_passage_ids', 'support_passage_ids', 'contrary_passage_ids'}:
                    if len(child) != len(set(child)):
                        errors.append('Repeated passage reference.')
                    used_ap.update(child)
                if key == 'proposition_ids':
                    used_ac.update(child)
                    if len(child) != len(set(child)):
                        errors.append('Repeated proposition reference.')
                    for ac in child:
                        if not links[ac] <= set(value.get('passage_ids', [])):
                            errors.append(ac + ' lost its exact AP support bridge.')
                if key == 'source_review_ids':
                    used_ap.update(p for p in child if p in passages)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(draft)
    if used_ac != set(links):
        errors.append('Account for every intake claim in summary/chronology.')
    if contrary and not any(contrary <= set(row['passage_ids']) for row in draft['summary']):
        errors.append('Summary must retain the competing government account.')
    for option in options:
        if not contrary <= set(option['contrary_passage_ids']):
            errors.append('Each alternative must retain competing passages as contrary evidence.')
        if not option['unknowns'] or not option['prerequisites']:
            errors.append('Each alternative needs unknowns and prerequisites.')
    citations = {c['passage_id']: c for c in draft['citations']}
    if len(citations) != len(draft['citations']) or not used_ap <= set(citations):
        errors.append('Exactly one source-linked citation is required for each used AP passage.')
    for pid, citation in citations.items():
        passage = passages[pid]
        if citation['source_id'] != passage['source_id'] or not citation['quote'].strip() or citation['quote'] not in passage['quote']:
            errors.append(pid + ': exact citation/source does not match supplied passage.')
        if not locator_matches(citation['locator'], passage['locator']) or not citation['attribution'].strip():
            errors.append(pid + ': preserve locator roles and explicit attribution.')
    for row in draft['chronology']:
        dates = {v for pid in row['passage_ids'] for v in passages[pid]['date_roles'].values() if isinstance(v, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', v)}
        if row['date'] is not None and (not valid_format(row['date'], 'date') or row['date'] not in dates):
            errors.append('Chronology date is unavailable from its cited passage/date role.')
    if cid == 'saturday_abra_notice_20261010':
        errors.extend(abra_semantic_errors(draft, supplied))
    if errors:
        raise APIError('Draft integrity: ' + '; '.join(errors[:10]), 400, 'draft_citation_error')
    return expected_schema


DIMENSIONS = {
    "tribunal_law", "equality_arms", "publicity", "presumption_innocence", "notice_charges",
    "preparation_facilities", "legal_assistance", "participation", "challenge_evidence",
    "interpretation", "self_incrimination", "undue_delay", "appeal_review", "juvenile_safeguards",
    "double_jeopardy", "miscarriage_compensation", "expression_scope", "expression_legal_basis",
    "expression_legitimate_aim", "expression_necessity",
}
STAGE_STANDARDS = {
    "preliminary_investigation": {"STD-PH-112-1", "STD-PH-112-3b", "STD-PH-112-3c", "STD-PH-112-3d", "STD-PH-112-3e", "STD-PH-112-4", "STD-PH-112-7"},
    "criminal_charge_notice": {"STD-ICCPR-14-3a", "STD-GC32-31", "STD-PH-CONST-III-14"},
    "arrest_information": {"STD-ICCPR-9-2"},
}


def locator_matches(rendered, locator):
    """Accept serialization or a lossless page-role/heading string rendering."""
    try:
        if json.loads(rendered) == locator:
            return True
    except (ValueError, TypeError):
        pass
    if locator["paragraph_or_heading"] not in rendered:
        return False
    # Page labels must preserve the distinction between PDF and printed page.
    page = str(locator["pdf_page"])
    if not re.search(r"\bPDF(?:[_ -]page|\s+p(?:age)?\.?)?\s*[:=]?\s*" + re.escape(page) + r"\b", rendered, re.I):
        return False
    printed = locator["printed_page"]
    expected = re.escape(str(printed)) + r"\b" if printed is not None else r"(?:null|none|unknown|not\s+(?:shown|given|numbered|available)|un(?:numbered|available))\b"
    return bool(re.search(r"\bprinted(?:[_ -]page|\s+p(?:age)?\.?)?\s*[:=]?\s*" + expected, rendered, re.I))


def strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)
    elif isinstance(value, str):
        yield value


def abra_semantic_errors(draft, supplied):
    """Deterministic bounded references and dated-claim guards, not legal judgment."""
    errors = []
    if supplied.get("format") != "part2-clean-input/1":
        return ["Input format is not the agreed bounded part2-clean-input/1 contract."]
    passages = {p["passage_id"]: p for p in supplied["factual_passages"]}
    sources = {s["source_id"] for s in supplied["source_metadata"]}
    links = {p["proposition_id"]: set(p["support_passage_ids"]) for p in supplied["identifier_links"]}
    standards = {p["passage_id"] for p in supplied["standards"]["passages"]}
    if set(passages) != {"AP%02d" % i for i in range(1, 11)} or sources != {"S1", "S2"}:
        return ["Clean input must contain exactly AP01-AP10 and the two supplied factual sources S1/S2."]
    if len(links) != 9 or not all(p <= set(passages) for p in links.values()):
        return ["Clean input proposition links do not resolve uniquely to supplied passages."]

    mappings = draft["assessment_mappings"]
    if len(mappings) != 20 or {m["dimension_id"] for m in mappings} != DIMENSIONS or any(m["mapping"] is not None for m in mappings):
        errors.append("assessment_mappings: require each of the twenty v2 dimensions exactly once, with mapping null.")
    if draft["human_checkpoint"]["approval"] is not None:
        errors.append("human_checkpoint: approval must remain null.")
    if len(draft["summary"]) not in {4, 5, 6}:
        errors.append("summary: require the requested 4-6 bounded entries.")
    stages = draft["stage_questions"]
    if len(stages) != 3 or {s["stage"] for s in stages} != set(STAGE_STANDARDS):
        errors.append("stage_questions: require exactly the three distinct unresolved stage groups.")
    for row in stages:
        required = STAGE_STANDARDS.get(row["stage"], set())
        if not required <= set(row["standard_passage_ids"]):
            errors.append("stage_questions." + row["stage"] + ": required stage-specific standard IDs missing.")
        if row["applicability_status"] != "unresolved" or not row["questions"] or not row["missing_facts"]:
            errors.append("stage_questions." + row["stage"] + ": unresolved questions and missing facts required.")
    options = draft["options"]
    pairs = {(o["option_id"], o["proposed_disposition"]) for o in options}
    if len(options) != 2 or pairs != {("verify_records", "prepare_verify"), ("defer_public_route", "defer")}:
        errors.append("options: require exactly verify_records/prepare_verify and defer_public_route/defer.")
    for option in options:
        if "AP08" not in option["contrary_passage_ids"]:
            errors.append("options." + option["option_id"] + ": the competing AP08 Government account must be retained as contrary context.")
        if option["execution_status"] != "proposal_only":
            errors.append("options." + option["option_id"] + ": execution must remain proposal_only.")
        if not option["unknowns"] or not option["prerequisites"]:
            errors.append("options." + option["option_id"] + ": unknowns and prerequisites are required.")

    used_ap, used_ac = set(), set()
    # Check every typed reference field, including the human checkpoint.
    def references(value, path="$"):
        if isinstance(value, dict):
            for key, child in value.items():
                current = path + "." + key
                if key in {"passage_ids", "factual_passage_ids", "support_passage_ids", "contrary_passage_ids"}:
                    if len(child) != len(set(child)):
                        errors.append(current + ": repeated passage reference.")
                    for pid in child:
                        if pid not in passages:
                            errors.append(current + ": unresolved factual passage " + pid)
                        used_ap.add(pid)
                elif key == "standard_passage_ids":
                    if len(child) != len(set(child)) or any(pid not in standards for pid in child):
                        errors.append(current + ": unresolved or repeated standard reference.")
                elif key == "proposition_ids":
                    if len(child) != len(set(child)):
                        errors.append(current + ": repeated proposition reference.")
                    used_ac.update(child)
                    support = set(value.get("passage_ids", []))
                    for cid in child:
                        if cid not in links or not links[cid] <= support:
                            errors.append(current + ": " + cid + " does not retain its supplied support passage link.")
                elif key == "source_review_ids":
                    if len(child) != len(set(child)) or any(pid not in passages and pid not in links for pid in child):
                        errors.append(current + ": unresolved or repeated review-scope ID.")
                    used_ap.update(pid for pid in child if pid in passages)
                references(child, current)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                references(child, path + "[" + str(i) + "]")
    references(draft)
    if used_ac != set(links):
        errors.append("summary/chronology: all nine stable AC identifiers must be accounted for.")
    if not any("AP08" in entry["passage_ids"] and "AC04" in entry["proposition_ids"] for entry in draft["summary"]):
        errors.append("summary: require the competing AP08/AC04 Government account.")

    citations = draft["citations"]
    citation_ids = [c["passage_id"] for c in citations]
    if len(citation_ids) != len(set(citation_ids)):
        errors.append("citations: one exact excerpt per referenced AP is required; repeated citation ID.")
    if not used_ap <= set(citation_ids):
        errors.append("citations: missing citations for " + ", ".join(sorted(used_ap - set(citation_ids))))
    for citation in citations:
        pid = citation["passage_id"]
        passage = passages.get(pid)
        if not passage:
            errors.append("citations: unresolved factual passage " + pid)
            continue
        if citation["source_id"] not in sources or citation["source_id"] != passage["source_id"]:
            errors.append("citations." + pid + ": source does not match supplied passage.")
        if not citation["quote"].strip() or citation["quote"] not in passage["quote"]:
            errors.append("citations." + pid + ": quote is not an exact contiguous excerpt of the supplied passage.")
        if not locator_matches(citation["locator"], passage["locator"]):
            errors.append("citations." + pid + ": locator must preserve exact heading and PDF/printed page roles.")
        if not citation["attribution"].strip():
            errors.append("citations." + pid + ": explicit attribution is required.")

    chrono = draft["chronology"]
    grant, dismissal = [], []
    for i, row in enumerate(chrono):
        where = "chronology[" + str(i) + "]"
        event = row["event"].lower()
        role = row["date_role"].lower()
        pids = set(row["passage_ids"])
        value = row["date"]
        available = {v for pid in pids if pid in passages for v in passages[pid]["date_roles"].values() if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)}
        if value is not None and (not valid_format(value, "date") or value not in available):
            errors.append(where + ": date is not an available exact event/document date from its cited passages.")
        dated_roles = {"2023-01-03": r"resolution", "2023-01-24": r"warrant", "2023-01-30": r"arrest|first.*inform", "2023-02-02": r"motion|submission"}
        if value in dated_roles and not re.search(dated_roles[value], event + " " + role):
            errors.append(where + ": the supplied date's event role is not preserved.")
        if value == "2023-01-30" and "AP02" in pids and "jennifer" not in event:
            errors.append(where + ": January30 arrest/first-information is Jennifer's individual account only.")
        if value is not None and re.search(r"complaint.{0,20}filing|information.{0,20}filing|subpoena.{0,20}service|notice service|government enclosure", event):
            errors.append(where + ": filing, service and enclosure dates remain unknown/null.")
        if "AP07" in pids:
            if "dismiss" in event and not re.search(r"(?:date unknown|undated|date not|separat|distinct)", event):
                dismissal.append(row)
                if value is not None:
                    errors.append(where + ": AP07 dismissal date is null; May11 is only the reported motion grant.")
            elif "dismiss" in role:
                dismissal.append(row)
                if value is not None:
                    errors.append(where + ": AP07 dismissal date must remain null.")
            if "grant" in event or "grant" in role:
                grant.append(row)
                if value != "2023-05-11":
                    errors.append(where + ": AP07 reported motion grant date must be 2023-05-11.")
            if "grant" in event and "dismiss" in event and value is not None and not re.search(r"dismiss[^.;]*(?:unknown|undated|not (?:dated|given|specified))", event):
                errors.append(where + ": grant and undated dismissal must have separate chronology entries.")
        if value == "2023-09-18" and not re.search(r"cover|transmi", role + " " + event):
            errors.append(where + ": September18 is only the S2 cover/transmission date, not an enclosure/event date.")
        if value == "2023-09-18" and re.search(r"dismiss|grant|prosecut(?:or|ion).*act|service (?:occur|date)", event) and not re.search(r"cover|transmi", event):
            errors.append(where + ": the Government cover date cannot date a substantive event.")
        if value == "2023-05-08" and "AP04" in pids and not re.search(r"communication|letter|document", role + " " + event):
            errors.append(where + ": May8 is the communication date; exact pending-status writing date remains unknown.")
    if not grant or not dismissal or any(row in dismissal for row in grant):
        errors.append("chronology: require distinct AP07 May11 grant and separately undated/null dismissal entries.")
    expected = [("AP01", "2023-01-03", "resolution"), ("AP03", "2023-01-24", "warrant"),
                ("AP02", "2023-01-30", "arrest"), ("AP02", "2023-02-02", "motion"),
                ("AP04", "2023-05-08", "communication"), ("AP10", "2023-09-18", "cover")]
    for pid, value, description in expected:
        if not any(pid in row["passage_ids"] and row["date"] == value for row in chrono):
            errors.append("chronology: missing explicitly cited " + description + " date " + value + " / " + pid)
    # Identifier-looking tokens in prose also must resolve. S5/O10 may be named
    # solely as excluded provenance in limitations; they cannot become citations.
    permitted = set(passages) | set(links) | sources | standards
    for area in ("summary", "chronology", "citations", "stage_questions", "gaps", "options", "human_checkpoint"):
        for content in strings(draft[area]):
            for token in re.findall(r"\b(?:AP\d{2}|AC\d{2}|S\d+|STD-[A-Za-z0-9-]+)\b", content):
                if token not in permitted:
                    errors.append(area + ": prose contains unresolved supplied-evidence ID " + token)
    return errors


