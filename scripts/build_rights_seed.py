"""Rebuild shareable fictional rights workflow fixtures, never historical research."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewdesk.rights import blank_dimensions, RUBRIC_VERSION


def source(sid, title, lineage):
    return {"id": sid, "title": title, "publisher": "Fictional fixture publisher", "url": "https://example.invalid/rights/" + sid,
            "publication_date": "2026-09-12", "retrieved_at": None, "language": "en", "translation_status": "Synthetic English text; no translation",
            "access_note": "Software fixture only. No document was retrieved and URL is intentionally non-resolving.", "lineage_note": lineage}


def claim(cid, sid, text, kind, date="2026-09-10"):
    return {"id": cid, "source_id": sid, "text": text, "excerpt": text, "locator": "Fictional fixture paragraph " + cid,
            "event_date": date, "date_note": "Fictional event date; not a real proceeding", "attribution": "Fictional " + kind.replace("_", " ") + "; unauthenticated demonstration text", "attribution_kind": kind}


def candidate(cid, title, country, claims, sources):
    return {"id": cid, "title": title, "person": "Fictional person " + cid, "proceeding": "Fictional criminal proceeding; demonstration only", "country": country,
            "material_type": "synthetic", "as_of": "2026-09-12", "summary": "Entirely fictional evidence for rights-assessment software mechanics.", "suggested_decision": "uncertain",
            "review_reasons": ["Preparation-time status: human review pending; this note records fixture provenance and does not describe subsequent saved review."],
            "unknowns": ["No real case or legal assessment is represented. All citations in this fictional dossier are fixture locations."], "notes": ["Synthetic preparation; no fresh AI extraction. Human review pending at preparation; current reviews appear separately."],
            "claims": claims, "sources": sources, "related_candidate_ids": [],
            "rights_metadata": {"region": "Fictional demonstration region", "case_unit": "One fictional case, one defendant; arrest-event count not established.", "identity_uncertainty": "Fixture IDs identify fictional dossiers only; no identity matching was performed.", "related_cases": [], "country_context": [], "pattern_hypotheses": [], "published_expert_assessments": []}}


def set_dimension(items, did, **values):
    item = next(value for value in items if value["dimension_id"] == did)
    item.update(values)


def main():
    a = candidate("rights_demo_1", "Synthetic A: contested charge notice", "Philippines", [
        claim("a_notice", "a_report", "The fictional defence says the defendant first received the charge details at the hearing, leaving no preparation time.", "source_allegation"),
        claim("a_repeat", "a_repeat_report", "The fictional defence says the defendant first received the charge details at the hearing, leaving no preparation time.", "source_allegation"),
        claim("a_reply", "a_reply_source", "The fictional prosecution says charge papers were delivered two weeks earlier; no receipt is supplied.", "government_position"),
        claim("a_minutes", "a_minutes_source", "Fictional hearing minutes record a request for adjournment to inspect the charge papers; the decision on that request is absent.", "documented_procedure"),
    ], [source("a_report", "Synthetic defence report", "Fictional defence statement; independence unestablished."), source("a_repeat_report", "Synthetic repetition of defence report", "Repeats a_report verbatim; same upstream allegation, not independent corroboration."), source("a_reply_source", "Synthetic prosecution position", "Contrary position; authenticity not established."), source("a_minutes_source", "Synthetic partial hearing minutes", "Fictional procedural text; incomplete minutes.")])
    b = candidate("rights_demo_2", "Synthetic B: documented counsel safeguards", "Philippines", [
        claim("b_notice", "b_record", "The fictional signed record states the charge was explained in the defendant's language fourteen days before the hearing.", "documented_procedure"),
        claim("b_counsel", "b_record", "The fictional hearing record states counsel met the defendant privately and obtained a preparation adjournment requested by the defence.", "documented_procedure"),
        claim("b_unknown", "b_news", "The fictional news note reports an adverse verdict but supplies no witness-examination record or reasons for judgment.", "source_allegation"),
    ], [source("b_record", "Synthetic signed procedural record", "One fictional record, not independent verification."), source("b_news", "Synthetic news summary", "Underlying judgment not supplied.")])
    c = candidate("rights_demo_3", "Synthetic C: expression restriction and disputed justification", "Thailand", [
        claim("c_speech", "c_report", "The fictional case report says the defendant was prosecuted after publishing peaceful criticism of a local policy.", "source_allegation"),
        claim("c_penalty", "c_report", "The fictional case report states a custodial penalty was sought; no specific harm or less restrictive alternative is described.", "source_allegation"),
        claim("c_reply", "c_reply_source", "The fictional government response asserts public order as the aim and says a specific threat existed, without explaining the connection to the publication.", "government_position"),
        claim("c_notice", "c_record", "The fictional record states detailed charge notice was provided promptly in a language the defendant understood.", "documented_procedure"),
    ], [source("c_report", "Synthetic expression case report", "One fictional reporting source; allegations unverified."), source("c_reply_source", "Synthetic government reply", "Attributed contrary position; incomplete justification."), source("c_record", "Synthetic charge-notice record", "One fictional record, not independently verified.")])
    a["related_candidate_ids"] = [b["id"]]
    b["related_candidate_ids"] = [a["id"]]
    a["rights_metadata"]["related_cases"] = [{"candidate_id": b["id"], "basis": "Both fictional Philippine criminal proceedings contain charge-notice evidence in September 2026.", "material_differences": "A contains conflicting delivery claims; B contains affirmative notice/counsel records. Shared geography does not establish a movement.", "identity_status": "Separate fictional defendants/cases; no merged identity."}]
    a["rights_metadata"]["pattern_hypotheses"] = [{"hypothesis": "A charge-notice comparison may merit investigation within this selected fictional corpus.", "supporting_candidate_ids": [a["id"], b["id"]], "alternative_explanations": "Different documentation completeness or procedural circumstances may explain the contrast; this is not a recurrence finding.", "further_evidence": "Obtain original delivery receipts and full hearing records; expand a defined sample before estimating frequency."}]
    prepared = {}
    for case in (a, b, c):
        dims = blank_dimensions()
        for did in ("challenge_evidence", "presumption_innocence"):
            set_dimension(dims, did, status="insufficient_evidence", explanation="Selected fictional documents do not resolve the facts needed for this standard.", missing_facts=["Full relevant procedural record and competing accounts."], next_verification="Inspect the original hearing/judgment record; absence from reporting is unknown.")
        prepared[case["id"]] = dims
    set_dimension(prepared[a["id"]], "notice_charges", status="scored", concern_level="substantial", support_claim_ids=["a_notice", "a_minutes"], contrary_claim_ids=["a_reply"], confidence="low", completeness="partial", explanation="If accurate, notice first at a hearing with no preparation time strongly raises Article 14(3)(a) concern. The prosecution's earlier-delivery account could materially change this assessment; a receipt is missing. Repeated reporting adds no independent support.", missing_facts=["Delivery receipt, full charge text, language and full hearing decision."], next_verification="Compare original delivery record with the defendant's account and hearing ruling.")
    set_dimension(prepared[a["id"]], "preparation_facilities", status="insufficient_evidence", support_claim_ids=["a_minutes"], explanation="A request for preparation time is documented, but its disposition and facilities are unknown; no numerical concern is inferred.", missing_facts=["Preparation time, facilities and adjournment ruling."], next_verification="Inspect disclosure and adjournment records.")
    for did in ("expression_scope", "expression_legal_basis", "expression_legitimate_aim", "expression_necessity"):
        set_dimension(prepared[a["id"]], did, status="insufficient_evidence", explanation="These fixture documents do not identify expression or the alleged offence; expression relevance cannot be assumed.", missing_facts=["Expression, offence and restriction nexus."], next_verification="Inspect the charge and underlying conduct.")
    for did, cid in (("notice_charges", "b_notice"), ("preparation_facilities", "b_counsel"), ("legal_assistance", "b_counsel")):
        set_dimension(prepared[b["id"]], did, status="scored", concern_level="none_documented", support_claim_ids=[cid], confidence="moderate", completeness="partial", explanation="This affirmative fictional procedural record documents the relevant safeguard. Zero applies only to this mapped proposition and dimension; record authenticity and broader compliance remain unchecked.", missing_facts=["Original record authenticity and the defendant's competing account."], next_verification="Check the original record and invite comparison with the defendant's account.")
    set_dimension(prepared[c["id"]], "notice_charges", status="scored", concern_level="none_documented", support_claim_ids=["c_notice"], confidence="moderate", completeness="partial", explanation="Affirmative fictional notice evidence documents the safeguard on this dimension; a prosecution alone does not indicate notice failure.", missing_facts=["Original notice and delivery record."], next_verification="Check original notice and delivery record.")
    set_dimension(prepared[c["id"]], "expression_scope", status="scored", concern_level="limited", support_claim_ids=["c_speech"], contrary_claim_ids=["c_reply"], confidence="low", completeness="partial", explanation="The report identifies apparently peaceful policy criticism and prosecution. The government alleges a threat. The full expression and charge are needed to resolve the Article 19 nexus and competing account.", missing_facts=["Full expression, charge, harm evidence and original government reply."], next_verification="Read the publication, charge and government justification together.")
    for did in ("expression_legal_basis", "expression_legitimate_aim"):
        set_dimension(prepared[c["id"]], did, status="insufficient_evidence", support_claim_ids=["c_reply"], explanation="An aim is asserted, but the text and application of the law and particular justification are incomplete. Missing evidence produces no numerical score.", missing_facts=["Charge statute, accessibility/precision and particularized justification."], next_verification="Obtain the actual charge provision and reasoned government/court account.")
    set_dimension(prepared[c["id"]], "expression_necessity", status="scored", concern_level="substantial", support_claim_ids=["c_speech", "c_penalty"], contrary_claim_ids=["c_reply"], confidence="low", completeness="partial", explanation="If the report is accurate, seeking custody for peaceful policy criticism without identified harm or alternatives strongly raises necessity/proportionality concern. The government's asserted specific threat may change the assessment and requires scrutiny; absence from this report is not proof no justification exists.", missing_facts=["Actual threatened harm, full reasons, penalty and less intrusive alternatives."], next_verification="Inspect original reasons and specific harm evidence before a legal conclusion.")
    seed = {"schema_version": 1, "rights_rubric_version": RUBRIC_VERSION, "dataset": {"id": "rights-index-synthetic-v2", "label": "Rights and intervention index — entirely fictional demo", "kind": "synthetic", "description": "Three fictional rights dossiers; twenty dimension definitions with explicit pending coverage. Software fixtures only, not real case research or measured legal accuracy."}, "candidates": [a, b, c], "rights_prepared_mappings": prepared}
    (ROOT / "reviewdesk/rights.synthetic.v2.json").write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    intake_case = deepcopy(b)
    intake_case["id"] = "rights_intake_demo"
    intake_case["title"] = "Synthetic intake: notice and counsel records"
    intake_case["related_candidate_ids"] = []
    template = {"schema_version": "rights-intake/2", "candidate": intake_case,
                "source_texts": {source["id"]: "\n\n".join(claim["excerpt"] for claim in intake_case["claims"] if claim["source_id"] == source["id"]) for source in intake_case["sources"]}, "prepared_mappings": prepared[b["id"]]}
    (ROOT / "examples/rights-intake.synthetic.v2.json").write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Rebuilt rights.synthetic.v2.json and rights-intake.synthetic.v2.json; original v1 fixtures unchanged.")


if __name__ == "__main__":
    main()
