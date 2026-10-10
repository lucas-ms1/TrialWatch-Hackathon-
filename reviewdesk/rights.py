"""Versioned, deterministic rights assessments over the preserved evidence store.

Mappings and factual/legal explanations are supplied by an analyst. No model,
source collection, country-score adjustment, or claim-volume heuristic runs here.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import quote

from .server import (APIError, encoded, identifier, iso_date, markdown_text,
                     now, public_url, require_fields, string, validate_candidate)

CONTRACT_VERSION = "rights-assessment/2"
RUBRIC_VERSION = "rights-rubric/2.0"
LEVELS = {"none_documented": 0, "limited": 1, "substantial": 2, "serious": 3}
STATES = {"scored", "insufficient_evidence", "not_assessed", "not_applicable"}
ANCHORS = {
    "0": "Affirmative relevant evidence documents a safeguard/no specific concern on this assessed dimension. Missing documents cannot produce zero; this is not certification of full compliance.",
    "1": "Specific possible concern; a material factual or legal explanation remains unresolved.",
    "2": "Substantial documented concern: cited propositions strongly indicate a departure from the standard; competing accounts and unresolved justification remain visible.",
    "3": "Severe documented concern: explanation explicitly addresses gravity, duration or centrality and strongest available support; this remains provisional, not a legal finding.",
}
ICCPR = "https://2covenants.ohchr.org/About-ICCPR.html"
GC32 = "https://cambodia.ohchr.org/sites/default/files/Softlaw/GC%2032-A5-En.pdf"
GC34 = "https://www.ohchr.org/sites/default/files/english/bodies/hrc/docs/GC34.pdf"
PH_CONSTITUTION = "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/3/353"
PH_RULES = "https://elibrary.judiciary.gov.ph/thebookshelf/showdocs/11/369"
TH_CONSTITUTION = "https://www.ect.go.th/web-upload/1xff0d34e409a13ef56eea54c52a291126/202307/m_document/2046/13538/file_download/231044cc2539cec6ac4c1a0cb09d8a53.pdf"


def standard(label, url, locator):
    return {"label": label, "url": url, "locator": locator}


_ORIGINAL_DIMENSIONS = [
    {"id": "notice_charges", "group": "fair_trial", "label": "Notice of charges", "standard": "In a criminal charge, prompt detailed notice in a language understood of the nature and cause of the charge.",
     "citations": [standard("ICCPR", ICCPR, "Article 14(3)(a)"), standard("HRC General Comment 32", GC32, "paragraph 31")], "applicability": "Criminal charges; distinguish formal charge notice from arrest reasons under Article 9. Language, detail and timing require case evidence."},
    {"id": "counsel_preparation", "group": "fair_trial", "label": "Counsel and preparation", "standard": "Adequate time and facilities to prepare a defence and communicate with counsel; defence in person or through legal assistance, with assigned assistance when justice requires and conditions are met.",
     "citations": [standard("ICCPR", ICCPR, "Article 14(3)(b), (d)"), standard("HRC General Comment 32", GC32, "paragraphs 32–34, 37–38")], "applicability": "Criminal charges; adequacy depends on complexity, access, timing and circumstances. Assigned counsel is subject to the treaty's conditions."},
    {"id": "challenge_evidence", "group": "fair_trial", "label": "Challenge evidence and witnesses", "standard": "Equal opportunity to examine adverse witnesses and obtain and examine defence witnesses under the same conditions; meaningful opportunity to address evidence.",
     "citations": [standard("ICCPR", ICCPR, "Article 14(3)(e)"), standard("HRC General Comment 32", GC32, "paragraphs 33, 39")], "applicability": "Criminal charges; assess relevant requests, access, refusals and procedural reasons. This does not guarantee unlimited admission of every proposed witness."},
    {"id": "independent_impartial", "group": "fair_trial", "label": "Independent and impartial hearing", "standard": "A fair and public hearing by a competent, independent and impartial tribunal established by law.",
     "citations": [standard("ICCPR", ICCPR, "Article 14(1)"), standard("HRC General Comment 32", GC32, "paragraphs 18–22, 28–29")], "applicability": "Criminal charges and rights/obligations in a suit at law; lawful exceptions to public access require specific assessment. An adverse decision does not establish bias."},
    {"id": "presumption_innocence", "group": "fair_trial", "label": "Presumption of innocence", "standard": "A person charged with a criminal offence is presumed innocent until proved guilty according to law.",
     "citations": [standard("ICCPR", ICCPR, "Article 14(2)"), standard("HRC General Comment 32", GC32, "paragraph 30")], "applicability": "Criminal charges; evaluate burden, presentation and statements by public authorities. Prosecution or conviction alone is not evidence of a departure."},
    {"id": "expression_scope", "group": "expression", "label": "Expression and restrictive interference", "standard": "Identify the expression, whether Article 19 protects it and the specific restriction. Freedom to hold opinions without interference is distinct from expression restrictions.",
     "citations": [standard("ICCPR", ICCPR, "Article 19(1)–(2)"), standard("HRC General Comment 34", GC34, "paragraphs 5, 9–13")], "applicability": "Do not presume expression was involved in every prosecution. Identify conduct and restriction; Article 20 duties and other rights may also require analysis."},
    {"id": "expression_legal_basis", "group": "expression", "label": "Restriction's legal basis", "standard": "Any restriction of protected expression must be provided by law with sufficient precision and accessible guidance; discretion must be bounded.",
     "citations": [standard("ICCPR", ICCPR, "Article 19(3)"), standard("HRC General Comment 34", GC34, "paragraphs 24–25")], "applicability": "First establish expression and restriction. Citation of a statute alone does not settle foreseeability or its application."},
    {"id": "expression_legitimate_aim", "group": "expression", "label": "Asserted legitimate aim", "standard": "Expression restrictions must serve the rights or reputations of others, national security, public order, public health or morals; asserted reasons require attribution and scrutiny.",
     "citations": [standard("ICCPR", ICCPR, "Article 19(3)(a)–(b)"), standard("HRC General Comment 34", GC34, "paragraphs 21–23, 28–32")], "applicability": "An asserted aim is a government position, not proof of necessity or legitimacy in the particular application. Missing government reasons remain unknown."},
    {"id": "expression_necessity", "group": "expression", "label": "Necessity and proportionality", "standard": "A restriction must be necessary and proportionate to a permitted aim, with a specific direct connection between the expression and the threat; examine less intrusive measures.",
     "citations": [standard("ICCPR", ICCPR, "Article 19(3)"), standard("HRC General Comment 34", GC34, "paragraphs 22, 33–35")], "applicability": "Assess actual expression, aim, harm, penalty and alternatives. A restriction is not automatically unlawful; a legal basis and aim do not automatically establish necessity."},
]
RUBRIC_V1 = json.loads((Path(__file__).parent / "rights-rubric.v1.json").read_text(encoding="utf-8"))


def fair_dimension(did, label, provision, paragraphs, standard_text, stage, exceptions, questions, components, conditional=False):
    return {"id": did, "group": "fair_trial", "label": label, "standard": standard_text,
            "citations": [standard("ICCPR", ICCPR, provision), standard("HRC General Comment 32", GC32, paragraphs)],
            "jurisdiction": "ICCPR framework; assess treaty/domestic law and version applicable to the event date.",
            "stage": stage, "exceptions": exceptions, "questions": questions, "components": components,
            "conditional": conditional, "applicability": stage + " " + exceptions}


DIMENSIONS = [
    fair_dimension("tribunal_law", "Competent, independent, impartial tribunal established by law", "Article 14(1)", "paragraphs 18–22",
                   "The adjudicating tribunal must be competent, independent, impartial and established by law.",
                   "Determination of a criminal charge or rights/obligations in a suit at law.", "An adverse ruling alone does not establish bias. Assess special/military proceedings and law establishing jurisdiction; core independence/impartiality cannot be displaced by convenience.",
                   ["What law establishes the tribunal's authority?", "What evidence addresses competence, interference, conflicts or objective appearance of bias?"],
                   ["Lawful establishment and jurisdiction", "Competence", "Institutional independence", "Actual/objective impartiality", "Challenges and rulings"]),
    fair_dimension("equality_arms", "Equality before courts and equality of arms", "Article 14(1)", "paragraphs 7–14",
                   "Equality before courts and tribunals requires equal access and procedural opportunities; distinctions require objective, reasonable justification without actual disadvantage or unfairness.",
                   "Court/tribunal access and relevant proceedings, including criminal charges and suits at law.", "Different treatment is not automatically unlawful; examine objective reasons, actual disadvantage and access barriers. Do not equate equal arms with identical roles.",
                   ["Could the parties access the tribunal and make submissions?", "Did disclosure, resources or procedure put one party at material disadvantage, with what justification?"],
                   ["Access without discriminatory barriers", "Comparable opportunity to present case", "Material procedural disadvantage", "Objective justification"]),
    fair_dimension("publicity", "Public hearings and public judgments", "Article 14(1)", "paragraphs 28–29",
                   "Hearings and judgments must ordinarily be public; permitted exclusions and judgment exceptions require case-specific justification.",
                   "Hearing and judgment in determination of a criminal charge or suit at law; determine hearing type, as not every pretrial/appeal step requires a public hearing.", "Press/public may be excluded for morals, public order, national security in a democratic society, private lives, or strictly necessary special circumstances where publicity prejudices justice. Judgment exceptions include juvenile interests or matrimonial/child guardianship disputes.",
                   ["Was the hearing open to the public, and were any exclusions justified?", "Was the judgment made public, subject to applicable exceptions?"],
                   ["Public hearing access", "Recorded exclusion ground and scope", "Public judgment", "Exception justification; missing web copies are evidence gaps, not proof"]),
    fair_dimension("presumption_innocence", "Presumption of innocence", "Article 14(2)", "paragraph 30",
                   "Everyone charged with a criminal offence is presumed innocent until proved guilty according to law; the prosecution bears the burden and authorities must refrain from prejudging guilt.",
                   "Criminal charge through adjudication.", "Prosecution, detention or an adverse verdict alone does not establish failure; distinguish official statements and presentation from a properly reached finding.",
                   ["Who bore the burden and what proof standard was used?", "Did authorities prejudge guilt or present the accused as guilty?"],
                   ["Burden and proof standard", "Benefit of doubt", "Official prejudgment", "Presentation of accused"]),
    fair_dimension("notice_charges", "Notice of charges", "Article 14(3)(a)", "paragraph 31",
                   "Prompt, detailed notice in a language understood of the nature and cause of the criminal charge.",
                   "Criminal charge, rather than only preliminary investigation before charges.", "Arrest reasons under Article 9 are a distinct related guarantee; formal notice must address law and alleged general facts, orally or in writing as appropriate.",
                   ["When did the person learn the charge and alleged acts?", "What details and language were provided?"],
                   ["Prompt timing", "Nature/legal basis", "Cause/alleged facts", "Understandable language"]),
    fair_dimension("preparation_facilities", "Adequate time and facilities for defence", "Article 14(3)(b)", "paragraphs 32–33",
                   "Adequate time and facilities to prepare the defence, including access to relevant documents and other evidence needed for defence.",
                   "Preparation for a criminal charge, hearings and relevant defence steps.", "Adequacy depends on complexity, access and circumstances. Requests for additional time and reasoned rulings matter; document volume alone is not adequacy.",
                   ["What preparation time, case complexity and disclosure were available?", "Were necessary adjournments/access requested and how were requests decided?"],
                   ["Preparation time", "Access to relevant/incriminating/exculpatory material", "Facilities", "Adjournment requests and rulings"]),
    fair_dimension("legal_assistance", "Access to effective legal assistance", "Article 14(3)(b), (d)", "paragraphs 34, 37–38",
                   "Defence in person or through legal assistance of choice, confidential access to counsel, and assigned effective assistance where justice requires subject to means conditions.",
                   "Criminal defence; distinguish custodial/investigation guarantees under Article 9 and applicable domestic law.", "Assigned assistance depends on interests of justice and lack of means for free assistance. Self-representation restrictions require objective sufficiently serious reasons; attributed counsel errors require case-specific responsibility analysis.",
                   ["Was counsel chosen/assigned, accessible and confidential?", "Were required assistance and effective representation available, with what restrictions?"],
                   ["Choice/information about counsel", "Access and confidentiality", "Assignment/means/interests of justice", "Effective assistance", "Self-representation and justified restrictions"]),
    fair_dimension("participation", "Presence and meaningful participation", "Article 14(3)(d)", "paragraphs 36–37",
                   "An accused ordinarily has a right to be tried in their presence and meaningfully defend the case.",
                   "Criminal trial and defence participation.", "Proceedings in absence can be permissible in specific circumstances after sufficient notice and opportunity; verify steps informing the accused and justification, not absence alone.",
                   ["Was the accused present, informed and able to follow/respond?", "If absent or restricted, what notice/opportunity and reasons existed?"],
                   ["Presence", "Notice/opportunity", "Understanding and ability to participate", "Reasoned absence/restriction justification"]),
    fair_dimension("challenge_evidence", "Examine witnesses and present defence evidence", "Article 14(3)(e)", "paragraph 39",
                   "Examine prosecution witnesses and obtain/examine defence witnesses under the same conditions; meaningful opportunity to challenge material evidence.",
                   "Criminal trial and material defence evidence requests.", "This is not an unlimited right to call every witness. Identify relevance, requests, refusals, reasons and disadvantage.",
                   ["Could material prosecution witnesses/evidence be challenged?", "Could relevant defence witnesses/evidence be presented under comparable conditions?"],
                   ["Prosecution witness examination", "Defence witness presentation", "Relevant evidence access", "Requests, refusals and justification"]),
    fair_dimension("interpretation", "Interpretation where required", "Article 14(3)(f)", "paragraph 40",
                   "Free assistance of an interpreter where the accused cannot understand or speak the language used in court.",
                   "Criminal proceedings when courtroom language cannot be understood/spoken.", "Nationality or multilingual setting alone does not prove need or adequacy. This right does not require proceedings in the preferred language where the court language is sufficiently understood.",
                   ["What language ability and proceedings language are documented?", "Was free, adequate interpretation provided throughout relevant proceedings?"],
                   ["Demonstrated language need", "Free interpreter", "Adequacy/coverage", "Requests and response"]),
    fair_dimension("self_incrimination", "Protection against compelled self-incrimination", "Article 14(3)(g)", "paragraph 41",
                   "No compulsion to testify against oneself or confess guilt; exclude prohibited coercion and examine allegations of involuntary statements.",
                   "Obtaining/use of statements in a criminal process, including earlier investigation where relevant to trial.", "Voluntary admission is not automatically prohibited. Distinguish Article 7 coercion and Article 9 detention guarantees; evaluate burden and exclusion of alleged coerced statements.",
                   ["How was the statement obtained and was compulsion alleged?", "How did the court handle coercion allegations and use/exclusion?"],
                   ["Compulsion/coercion evidence", "Voluntariness safeguards", "Use of statements", "Investigation/exclusion of coercion"]),
    fair_dimension("undue_delay", "Trial without undue delay", "Article 14(3)(c)", "paragraph 35",
                   "Criminal proceedings must proceed without undue delay, assessed from formal charge through final judgment including appeal.",
                   "Criminal charge through final adjudication/appeal.", "Assess complexity, accused conduct and administrative/judicial handling. Elapsed time or a procedural deadline alone does not establish undue delay; custody increases need for expedition.",
                   ["What intervals, procedural steps and reasons for delay are documented?", "How do complexity, party conduct, court conduct and detention affect adequacy?"],
                   ["Charge-to-final chronology", "Complexity", "Party/court conduct", "Reasons and detention urgency"]),
    fair_dimension("appeal_review", "Review of conviction and sentence", "Article 14(5)", "paragraphs 45–51",
                   "Conviction and sentence must be reviewed by a higher tribunal according to law, including sufficient substantive review of facts and law.",
                   "After criminal conviction/sentence and relevant higher review.", "Guarantee is substantive, not merely a formal check. Civil review is not automatically within Article 14(5); examine applicable special procedures and access to reasoned judgment/record.",
                   ["Was higher review available and effective for both conviction and sentence?", "What facts/law, judgment and record were reviewed and what barriers existed?"],
                   ["Higher tribunal access", "Conviction and sentence coverage", "Substantive review", "Reasons/record access", "Timing and barriers"]),
    fair_dimension("juvenile_safeguards", "Conditional juvenile safeguards", "Article 14(4)", "paragraphs 42–44",
                   "Proceedings for juveniles must take account of age and the desirability of promoting rehabilitation.",
                   "Criminal proceedings involving a juvenile at the relevant event date.", "Age and domestic juvenile status require verification. Juvenile-specific procedure/rehabilitation and diversion where appropriate are distinct from assuming identical adult procedure.",
                   ["What age/status applies at the event date?", "What age-appropriate procedure, assistance and rehabilitation/diversion protections were used?"],
                   ["Age/status", "Age-appropriate participation", "Assistance/procedure", "Rehabilitation and appropriate diversion"], True),
    fair_dimension("double_jeopardy", "Conditional protection from double jeopardy", "Article 14(7)", "paragraphs 54–57",
                   "No repeated trial or punishment for an offence after final conviction/acquittal under the law and penal procedure of the same country.",
                   "Later criminal proceedings following a potentially final conviction/acquittal for the same offence.", "Verify finality/same offence/same jurisdiction. Higher review and narrowly justified resumption on exceptional grounds are distinct; the Covenant does not automatically prohibit prosecutions in different national jurisdictions.",
                   ["Was a prior decision final, for the same offence in the same country?", "Is this a new prosecution or permitted review/resumption, on what grounds?"],
                   ["Prior final decision", "Same offence/jurisdiction", "New prosecution/punishment", "Review/resumption distinction"], True),
    fair_dimension("miscarriage_compensation", "Conditional miscarriage-of-justice compensation", "Article 14(6)", "paragraphs 52–53",
                   "Compensation according to law where a final conviction is reversed or a pardon granted because a new/newly discovered fact conclusively shows miscarriage of justice, subject to non-disclosure conditions.",
                   "After qualifying reversal/pardon and punishment following final criminal conviction.", "Ordinary acquittal, dismissal or reversal alone is insufficient. Examine final conviction, punishment, newly discovered fact, conclusive miscarriage and whether non-disclosure was wholly/partly attributable to the person.",
                   ["Do final conviction, punishment, qualifying reversal/pardon and new fact meet the conditions?", "What compensation route and non-disclosure exception apply?"],
                   ["Final conviction and punishment", "Qualifying reversal/pardon", "New conclusive fact", "Non-disclosure responsibility", "Compensation procedure"], True),
] + deepcopy([item for item in RUBRIC_V1["dimensions"] if item["group"] == "expression"])
for item in DIMENSIONS:
    if item["group"] == "expression":
        item.update({"jurisdiction": "ICCPR Article 19 and relevant domestic law at the event date.", "stage": "Identified expression and interference/restriction, including prosecution where linked.",
                     "exceptions": item["applicability"], "questions": ["What expression, restriction, law, asserted aim and particular justification are documented?", "What competing account or missing facts would change this dimension's assessment?"],
                     "components": ["Specific expression/restriction nexus", "Dimension-specific facts and competing justification"], "conditional": False})
DIMENSION_IDS = {item["id"] for item in DIMENSIONS}
RUBRIC = {"version": RUBRIC_VERSION, "contract_version": CONTRACT_VERSION,
          "scale": ANCHORS, "levels": LEVELS, "non_numeric_states": sorted(STATES - {"scored"}),
          "dimensions": DIMENSIONS,
          "jurisdiction_standards": {
              "Philippines": [standard("1987 Philippine Constitution", PH_CONSTITUTION, "Article III sections 4 and 14; applicability must be assessed in the case"), standard("Philippine Rules of Criminal Procedure", PH_RULES, "Rules 110 sections 6/8; 115 section 1; 116 sections 1/6; determine procedural applicability")],
              "Thailand": [standard("2017 Thai Constitution, Council of State English translation hosted by ECT", TH_CONSTITUTION, "Sections 29, 34, 188; translation is unofficial, Thai text alone authoritative. Section 68 is a directive-policy legal-aid provision under section 64.")]},
          "scoring_method": "Analyst selects an anchored concern level and supplies supported propositions and reasoning. The server maps its name to 0–3, validates references and snapshots evidence. It does not infer legal facts or automatically select severity.",
          "confidence_method": "Analyst judgment of reliability and support for this dimension, separately recorded. Distinct reports are not automatically independent corroboration.",
          "completeness_method": "Analyst judgment of relevant factual/legal coverage for this dimension; missing information is unknown.",
          "limits": "No combined percentage, calibrated probability, official TrialWatch grade or definitive violation finding. Country indicators cannot change individual scores. This is a partial rubric, not an exhaustive legal checklist."}
RUBRIC["related_detention_guarantees"] = [standard("ICCPR Article 9 (related, separately identifiable; no Article 14 score)", ICCPR, "Article 9(1)–(5): liberty, arrest reasons, judicial control and detention challenge/compensation")]
RUBRIC["migration_policy"] = "V1 stays defined/exported under its original rubric. Split counsel/preparation and expanded tribunal dimensions never inherit combined scores. All new dimensions begin not_assessed; unchanged explicit mappings may be carried into a new draft requiring fresh review. No umbrella or Article 9 score is added."
RUBRICS = {RUBRIC_V1["version"]: RUBRIC_V1, RUBRIC_VERSION: RUBRIC}


def rubric_for(version):
    if not isinstance(version, str) or version not in RUBRICS:
        raise APIError("Unsupported rubric version.")
    return RUBRICS[version]


def infer_prepared_version(items):
    if not isinstance(items, list):
        raise APIError("Prepared mappings must be an array.")
    if len(items) == len(RUBRIC_V1["dimensions"]):
        return RUBRIC_V1["version"]
    if len(items) == len(DIMENSIONS):
        return RUBRIC_VERSION
    raise APIError("Prepared mapping dimensions do not identify a supported rubric version.")


def upgrade_dimensions(items):
    """Make a draft, never rescale/split an old assessed score or review."""
    result = blank_dimensions()
    current = {item["dimension_id"]: item for item in items}
    for index, item in enumerate(result):
        if item["dimension_id"] in current:
            copied = {key: deepcopy(value) for key, value in current[item["dimension_id"]].items() if key != "score"}
            result[index] = copied
    return result
DISCLAIMER = ("Provisional concern assessment for advocacy prioritization; not an official TrialWatch assessment, "
              "legal finding, current-status certification or calibrated probability. Source allegations, government "
              "positions, reported court findings, published expert assessments and analyst reasoning remain distinct. "
              "Software checks validate behavior, not legal accuracy. Missing evidence is unknown.")
DIMENSION_FIELDS = {"dimension_id", "status", "concern_level", "support_claim_ids", "contrary_claim_ids", "explanation", "confidence", "completeness", "missing_facts", "next_verification", "applicability"}
ASSESSMENT_FIELDS = {"expected_revision", "expected_evidence_revision", "rubric_version", "analyst", "preparation", "dimensions"}
ATTRIBUTION_KINDS = {"source_allegation", "government_position", "reported_court_finding", "published_expert_assessment", "documented_procedure", "analyst_proposition"}


def blank_dimensions(version=RUBRIC_VERSION):
    return [{"dimension_id": item["id"], "status": "not_assessed", "concern_level": None,
             "support_claim_ids": [], "contrary_claim_ids": [], "explanation": "Not assessed.",
             "confidence": "unknown", "completeness": "unknown", "missing_facts": ["Dimension has not been assessed."],
             "next_verification": "Inspect the relevant evidence and applicable standard.", "applicability": item["applicability"]} for item in rubric_for(version)["dimensions"]]


def revisions(payload, fields):
    for field in fields:
        if type(payload[field]) is not int or payload[field] < 0:
            raise APIError(field + " must be a nonnegative integer.")


def id_list(value, field):
    if not isinstance(value, list) or len(value) > 500:
        raise APIError(field + " must be an array of at most 500 IDs.")
    result = [identifier(item, field) for item in value]
    if len(set(result)) != len(result):
        raise APIError(field + " must contain unique IDs.")
    return result


def text_list(value, field):
    if not isinstance(value, list) or len(value) > 100:
        raise APIError(field + " must be an array of at most 100 strings.")
    return [string(item, field, 8000) for item in value]


def validate_dimensions(items, snapshot, version=RUBRIC_VERSION):
    definitions = rubric_for(version)["dimensions"]
    dimension_ids = {item["id"] for item in definitions}
    if not isinstance(items, list) or len(items) != len(definitions):
        raise APIError("Supply every rubric dimension exactly once; unassessed dimensions retain not_assessed.")
    claims = {item["id"]: item for item in snapshot["claims"]}
    sources = {item["id"]: item for item in snapshot["sources"]}
    seen, result = set(), []
    for item in items:
        require_fields(item, DIMENSION_FIELDS)
        did = identifier(item["dimension_id"], "dimension_id")
        if did not in dimension_ids or did in seen:
            raise APIError("Unknown or repeated rubric dimension.")
        seen.add(did)
        status = item["status"]
        if not isinstance(status, str) or status not in STATES:
            raise APIError("Invalid dimension status.")
        level = item["concern_level"]
        if status == "scored":
            if not isinstance(level, str) or level not in LEVELS:
                raise APIError("Scored dimensions require an anchored concern_level.")
        elif level is not None:
            raise APIError("Non-numeric states must have a null concern_level.")
        support = id_list(item["support_claim_ids"], "support_claim_ids")
        contrary = id_list(item["contrary_claim_ids"], "contrary_claim_ids")
        if set(support) & set(contrary):
            raise APIError("A passage cannot simultaneously be supporting and contrary evidence in one dimension; explain ambiguity separately.")
        if status == "scored" and not support:
            raise APIError("Every numerical score, including zero, requires affirmative relevant evidence and reasoning.")
        cited = set(support + contrary)
        if not cited <= claims.keys():
            raise APIError("An assessment citation does not resolve to this candidate's evidence.")
        for claim_id in cited:
            claim = claims[claim_id]
            if claim["source_id"] not in sources or not claim.get("excerpt") or not claim.get("locator"):
                raise APIError("Every cited claim requires a resolving source, excerpt and locator.")
        confidence, completeness = item["confidence"], item["completeness"]
        if not isinstance(confidence, str) or confidence not in {"unknown", "low", "moderate", "high"}:
            raise APIError("Invalid evidence confidence.")
        if not isinstance(completeness, str) or completeness not in {"unknown", "limited", "partial", "substantial"}:
            raise APIError("Invalid evidence completeness.")
        if status == "scored" and (confidence == "unknown" or completeness == "unknown"):
            raise APIError("Scored dimensions require separate confidence and completeness judgments.")
        values = {key: string(item[key], key, 8000) for key in ("explanation", "next_verification", "applicability")}
        gaps = text_list(item["missing_facts"], "missing_facts")
        if status == "insufficient_evidence" and not gaps:
            raise APIError("Insufficient evidence requires explicit missing facts.")
        result.append({"dimension_id": did, "status": status, "concern_level": level,
                       "score": LEVELS[level] if status == "scored" else None, "support_claim_ids": support,
                       "contrary_claim_ids": contrary, "confidence": confidence, "completeness": completeness,
                       "missing_facts": gaps, **values})
    return result


class RightsService:
    def __init__(self, store, document):
        self.store = store
        self.prepared = document.get("rights_prepared_mappings", {})
        if not isinstance(self.prepared, dict):
            raise APIError("rights_prepared_mappings must be an object.")
        self.seed_rubric_version = document.get("rights_rubric_version", RUBRIC_V1["version"])
        rubric_for(self.seed_rubric_version)
        with store.connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS rights_assessments (
                    candidate_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(candidate_id, revision));
                CREATE TABLE IF NOT EXISTS rights_reviews (
                    candidate_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(candidate_id, revision));
                CREATE TABLE IF NOT EXISTS rights_preparations (
                    candidate_id TEXT PRIMARY KEY, record TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rights_source_texts (
                    candidate_id TEXT NOT NULL, source_id TEXT NOT NULL, source_text TEXT NOT NULL,
                    PRIMARY KEY(candidate_id, source_id));
            """)
            for cid, mappings in self.prepared.items():
                if cid not in store.originals:
                    raise APIError("Prepared rights mapping has an unresolved candidate.")
                validate_dimensions(mappings, self.snapshot(store.originals[cid], None), self.seed_rubric_version)
            for candidate in store.originals.values():
                self.validate_context(candidate.get("rights_metadata", {}))
                self.validate_context_references(candidate.get("rights_metadata", {}), set(store.originals))

    def snapshot(self, candidate, review):
        all_review = deepcopy(review)
        if all_review:
            all_review["included_claim_ids"] = [claim["id"] for claim in candidate["claims"]]
        snapshot = self.store.evidence_export(candidate, all_review)
        snapshot["review"] = deepcopy(review)
        snapshot["rights_metadata"] = deepcopy(candidate.get("rights_metadata", {}))
        snapshot["claim_scope"] = "All candidate observations retained, including contrary evidence and observations outside the separate legacy triage review."
        return snapshot

    @staticmethod
    def history(connection, table):
        result = {}
        for cid, record in connection.execute("SELECT candidate_id,record FROM " + table + " ORDER BY candidate_id,revision"):
            result.setdefault(cid, []).append(json.loads(record))
        return result

    def _read_candidate(self, connection, cid):
        identifier(cid)
        candidate = self.store.candidates(connection).get(cid)
        if not candidate:
            raise APIError("Candidate not found.", 404, "not_found")
        row = connection.execute("SELECT record FROM reviews WHERE candidate_id=? ORDER BY revision DESC LIMIT 1", (cid,)).fetchone()
        return candidate, json.loads(row[0]) if row else None

    def _assessment(self, connection, cid, payload):
        require_fields(payload, ASSESSMENT_FIELDS)
        revisions(payload, {"expected_revision", "expected_evidence_revision"})
        rubric = rubric_for(payload["rubric_version"])
        if not isinstance(payload["preparation"], str) or payload["preparation"] not in {"manual", "ai_prepared", "synthetic_prepared"}:
            raise APIError("Invalid assessment preparation provenance.")
        analyst = string(payload["analyst"], "analyst", 200)
        candidate, review = self._read_candidate(connection, cid)
        if payload["preparation"] == "synthetic_prepared" and candidate["material_type"] != "synthetic":
            raise APIError("Synthetic preparation cannot be attached to real material.")
        row = connection.execute("SELECT revision FROM rights_assessments WHERE candidate_id=? ORDER BY revision DESC LIMIT 1", (cid,)).fetchone()
        current = row[0] if row else 0
        if current != payload["expected_revision"]:
            raise APIError("The assessment changed. Reload before saving.", 409, "revision_conflict")
        evidence_revision = self.store.evidence_revision(connection, cid)
        if payload["expected_evidence_revision"] != evidence_revision:
            raise APIError("The evidence changed. Reinspect before assessment.", 409, "evidence_revision_conflict")
        snapshot = self.snapshot(candidate, review)
        dimensions = validate_dimensions(payload["dimensions"], snapshot, rubric["version"])
        return {"schema_version": rubric["contract_version"], "rubric_version": rubric["version"], "candidate_id": cid,
                "revision": current + 1, "evidence_revision": evidence_revision, "assessment_date": now(),
                "analyst": analyst, "preparation": payload["preparation"], "dimensions": dimensions,
                "evidence_snapshot": snapshot, "review_status": "pending_human_review", "disclaimer": DISCLAIMER}

    def draft(self, cid, payload):
        with self.store.connection() as connection:
            connection.execute("BEGIN")
            record = self._assessment(connection, cid, payload)
        return {**record, "persisted": False, "review_status": "unsaved_draft"}

    def save(self, cid, payload):
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            record = self._assessment(connection, cid, payload)
            connection.execute("INSERT INTO rights_assessments VALUES (?,?,?)", (cid, record["revision"], encoded(record)))
        return record

    def review(self, cid, payload):
        require_fields(payload, {"expected_assessment_revision", "expected_review_revision", "expected_evidence_revision", "reviewer", "reason", "decision", "dimension_ids", "claim_ids"})
        revisions(payload, {"expected_assessment_revision", "expected_review_revision", "expected_evidence_revision"})
        dimension_ids = id_list(payload["dimension_ids"], "dimension_ids")
        claim_ids = id_list(payload["claim_ids"], "claim_ids")
        if not dimension_ids:
            raise APIError("Review one or more exact rubric dimensions.")
        if not isinstance(payload["decision"], str) or payload["decision"] not in {"approve", "request_changes"}:
            raise APIError("Invalid rights review decision.")
        reviewer = string(payload["reviewer"], "reviewer", 200)
        reason = string(payload["reason"], "reason", 8000)
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            _, evidence_review = self._read_candidate(connection, cid)
            row = connection.execute("SELECT record FROM rights_assessments WHERE candidate_id=? ORDER BY revision DESC LIMIT 1", (cid,)).fetchone()
            if not row:
                raise APIError("Save an assessment before reviewing its dimensions.", 409, "assessment_required")
            assessment = json.loads(row[0])
            rubric = rubric_for(assessment["rubric_version"])
            if not set(dimension_ids) <= {item["id"] for item in rubric["dimensions"]}:
                raise APIError("Review scope must use the saved assessment's original rubric dimensions.")
            evidence_revision = self.store.evidence_revision(connection, cid)
            if assessment["evidence_revision"] != evidence_revision or payload["expected_evidence_revision"] != evidence_revision:
                raise APIError("The assessment evidence is stale. Reassess before approval.", 409, "stale_evidence")
            if assessment["revision"] != payload["expected_assessment_revision"]:
                raise APIError("The assessment changed. Review the current revision.", 409, "revision_conflict")
            row = connection.execute("SELECT revision FROM rights_reviews WHERE candidate_id=? ORDER BY revision DESC LIMIT 1", (cid,)).fetchone()
            current = row[0] if row else 0
            if current != payload["expected_review_revision"]:
                raise APIError("Another rights review was saved. Reload.", 409, "review_revision_conflict")
            selected = [item for item in assessment["dimensions"] if item["dimension_id"] in dimension_ids]
            expected_claims = {cid for item in selected for cid in item["support_claim_ids"] + item["contrary_claim_ids"]}
            if set(claim_ids) != expected_claims:
                raise APIError("Review scope must include exactly all support and contrary claim IDs for the selected dimensions.")
            if payload["decision"] == "approve" and any(item["status"] == "not_assessed" for item in selected):
                raise APIError("An unassessed dimension cannot be approved; assess it or review another dimension.")
            record = {"schema_version": "rights-review/2" if rubric["version"] == RUBRIC_VERSION else "rights-review/1", "candidate_id": cid, "revision": current + 1,
                      "rubric_version": rubric["version"],
                      "assessment_revision": assessment["revision"], "evidence_revision": evidence_revision,
                      "reviewer": reviewer, "reason": reason, "decision": payload["decision"],
                      "dimension_ids": dimension_ids, "claim_ids": claim_ids, "reviewed_at": now(),
                      "scope": "Human decision only on the listed dimensions and their exact cited observations at this assessment/evidence revision; no whole-case authentication."}
            connection.execute("INSERT INTO rights_reviews VALUES (?,?,?)", (cid, record["revision"], encoded(record)))
        return record

    def state(self):
        with self.store.connection() as connection:
            connection.execute("BEGIN")
            candidates = self.store.candidates(connection)
            evidence_history = self.store.histories(connection)
            additions = self.history(connection, "evidence_additions")
            evidence_revisions = {cid: self.store.evidence_revision(connection, cid) for cid in candidates}
            history = self.history(connection, "rights_assessments")
            reviews = self.history(connection, "rights_reviews")
            prepared = deepcopy(self.prepared)
            prepared.update({row[0]: json.loads(row[1]) for row in connection.execute("SELECT candidate_id,record FROM rights_preparations")})
        profiles, latest = {}, {}
        prepared_versions = {cid: infer_prepared_version(items) for cid, items in prepared.items()}
        current_prepared = {cid: upgrade_dimensions(items) for cid, items in prepared.items()}
        for cid, candidate in candidates.items():
            assessment = history.get(cid, [None])[-1]
            rubric = rubric_for(assessment["rubric_version"]) if assessment else RUBRIC
            definitions = rubric["dimensions"]
            evidence_review = evidence_history.get(cid, [None])[-1]
            evidence_revision = evidence_revisions[cid]
            stale = bool(assessment and assessment["evidence_revision"] != evidence_revision)
            scope = {}
            if assessment:
                for record in reviews.get(cid, []):
                    if record["assessment_revision"] == assessment["revision"]:
                        for did in record["dimension_ids"]:
                            scope[did] = record
            dimensions = assessment["dimensions"] if assessment else []
            assessed = [item["dimension_id"] for item in dimensions if item["status"] != "not_assessed"]
            approved = [did for did in assessed if scope.get(did, {}).get("decision") == "approve"]
            status = ("unassessed" if not assessment else "stale" if stale else
                      "changes_requested" if any(row["decision"] == "request_changes" for row in scope.values()) else
                      "approved" if len(approved) == len(definitions) else "partially_approved" if approved else "pending_human_review")
            profile = {"candidate_id": cid, "assessment": assessment, "assessment_revision": assessment["revision"] if assessment else 0,
                       "evidence_revision": evidence_revision, "stale_evidence": stale, "review_status": status,
                       "rubric": rubric, "upgrade_dimensions": upgrade_dimensions(dimensions),
                       "dimension_reviews": scope, "coverage": {"total_dimensions": len(definitions), "assessed_dimensions": len(assessed), "scored_dimensions": sum(item["score"] is not None for item in dimensions), "approved_dimensions": len(approved)},
                       "profiles": {group: [item for item in dimensions if next(d["group"] for d in definitions if d["id"] == item["dimension_id"]) == group] for group in ("fair_trial", "expression")},
                       "context": deepcopy(candidate.get("rights_metadata", {})),
                       "current_evidence_review": evidence_review,
                       "evidence_additions": additions.get(cid, []),
                       "preparation_provenance": candidate["notes"],
                       "review_scope_note": "Preparation notes retain historical status. Evidence triage and rights-dimension decisions are separate; only listed observations/dimensions were reviewed."}
            profiles[cid] = profile
            if assessment:
                latest[cid] = assessment
        return {"rubric": RUBRIC, "rubric_registry": RUBRICS, "latest": latest, "history": history, "review_history": reviews,
                "evidence_review_history": evidence_history,
                "evidence_addition_history": additions,
                "case_profiles": profiles, "prepared_mappings": current_prepared,
                "original_prepared_mappings": prepared, "prepared_rubric_versions": prepared_versions, "blank_dimensions": blank_dimensions(),
                "mode": "deterministic_analyst_mappings_no_fresh_ai_extraction", "disclaimer": DISCLAIMER,
                "corpus_scope": "Selected local dossiers are not a population sample; document counts are not case incidence. Identity links remain provisional, and country context never changes a dimension's score."}

    def export(self, cid):
        identifier(cid)
        state = self.state()
        profile = state["case_profiles"].get(cid)
        if not profile:
            raise APIError("Candidate not found.", 404, "not_found")
        if not profile["assessment"]:
            raise APIError("Save an assessment before exporting.", 409, "assessment_required")
        return {"schema_version": profile["assessment"]["schema_version"], "document_type": "rights_case_profile", "exported_at": now(),
                "rubric": profile["rubric"], "rubric_registry": RUBRICS, "case_profile": profile, "assessment_history": state["history"].get(cid, []),
                "rights_review_history": state["review_history"].get(cid, []),
                "evidence_review_history": state["evidence_review_history"].get(cid, []), "disclaimer": DISCLAIMER,
                "evidence_addition_history": state["evidence_addition_history"].get(cid, []),
                "snapshot_policy": "Saved assessment evidence is immutable. Later corrections flag the saved assessment stale; a new assessment revision requires fresh review. Current evidence-review state is separately shown."}

    def add_evidence(self, cid, payload):
        """Append supplied quotations from retained structured-intake sources only."""
        identifier(cid)
        require_fields(payload, {"expected_revision", "author", "origin", "claims"})
        revisions(payload, {"expected_revision"})
        author = string(payload["author"], "author", 200)
        origin = payload["origin"]
        if not isinstance(origin, str) or origin not in {"manual", "ai_prepared", "synthetic_prepared"}:
            raise APIError("Invalid evidence-addition preparation origin.")
        supplied = payload["claims"]
        if not isinstance(supplied, list) or not 1 <= len(supplied) <= 100:
            raise APIError("Append 1-100 new source-backed observations.")
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidate, _ = self._read_candidate(connection, cid)
            current = self.store.evidence_revision(connection, cid)
            if current != payload["expected_revision"]:
                raise APIError("The evidence changed. Reload before adding observations.", 409, "evidence_revision_conflict")
            if origin == "synthetic_prepared" and candidate["material_type"] != "synthetic":
                raise APIError("Synthetic additions cannot be attached to real material.")
            captures = dict(connection.execute("SELECT source_id,source_text FROM rights_source_texts WHERE candidate_id=?", (cid,)))
            if not captures:
                raise APIError("Evidence additions require this candidate's retained structured-intake source texts.", 409, "source_text_required")
            existing = {claim["id"] for claim in candidate["claims"]}
            sources = {source["id"] for source in candidate["sources"]}
            claims, new_ids = deepcopy(supplied), set()
            fields = {"id", "source_id", "text", "excerpt", "locator", "event_date", "date_note", "attribution"}
            for claim in claims:
                if not isinstance(claim, dict) or not fields <= claim.keys() or claim.keys() - (fields | {"attribution_kind"}):
                    raise APIError("Evidence-addition observation fields differ from the structured claim contract.")
                claim_id = identifier(claim["id"], "claim id")
                if claim_id in existing or claim_id in new_ids:
                    raise APIError("Append only distinct new observation IDs; original observations cannot be overwritten.", 409, "duplicate_claim_id")
                sid = claim["source_id"]
                if not isinstance(sid, str) or sid not in sources or sid not in captures:
                    raise APIError("Each new observation must cite its own already retained candidate source.")
                excerpt = claim["excerpt"]
                string(excerpt, "excerpt")
                if excerpt not in captures[sid]:
                    raise APIError("Each exact excerpt must appear in its own retained source text.", 400, "excerpt_not_found")
                if "attribution_kind" in claim and (not isinstance(claim["attribution_kind"], str) or claim["attribution_kind"] not in ATTRIBUTION_KINDS):
                    raise APIError("Invalid attribution_kind.")
                new_ids.add(claim_id)
            validate_candidate({**candidate, "claims": candidate["claims"] + claims})
            addition_revision = connection.execute("SELECT MAX(revision) FROM evidence_additions WHERE candidate_id=?", (cid,)).fetchone()[0] or 0
            record = {"schema_version": "evidence-addition/1", "candidate_id": cid, "revision": addition_revision + 1,
                      "evidence_revision": current + 1, "author": author, "origin": origin, "created_at": now(), "claims": claims,
                      "scope": "Additional source-attributed observations; no human inspection, rights approval or source authentication recorded."}
            connection.execute("INSERT INTO evidence_additions VALUES (?,?,?)", (cid, record["revision"], encoded(record)))
        return record

    def retained_source(self, cid, source_id):
        """Read a case's supplied source text without collecting or changing it."""
        identifier(cid, "candidate id")
        identifier(source_id, "source id")
        with self.store.connection() as connection:
            candidate = self.store.candidates(connection).get(cid)
            if candidate is None:
                raise APIError("Case not found.", 404, "not_found")
            source = next((s for s in candidate["sources"] if s["id"] == source_id), None)
            if source is None:
                raise APIError("Source not found in this case.", 404, "not_found")
            row = connection.execute("SELECT source_text FROM rights_source_texts WHERE candidate_id=? AND source_id=?",
                                     (cid, source_id)).fetchone()
            if row is None:
                raise APIError("No full supplied text is retained for this source.", 404, "source_text_required")
            return {"candidate_id": cid, "source": deepcopy(source), "text": row[0]}

    def intake(self, payload):
        require_fields(payload, {"schema_version", "candidate", "source_texts", "prepared_mappings"})
        if not isinstance(payload["schema_version"], str) or payload["schema_version"] not in {"rights-intake/1", "rights-intake/2"}:
            raise APIError("Unsupported rights intake schema.")
        candidate = deepcopy(payload["candidate"])
        validate_candidate(candidate)
        candidate_fields = {"id", "title", "person", "proceeding", "country", "material_type", "as_of", "summary", "suggested_decision", "review_reasons", "unknowns", "related_candidate_ids", "notes", "sources", "claims"}
        if candidate.keys() - (candidate_fields | {"rights_metadata"}):
            raise APIError("Unexpected structured candidate fields; rights assessments use their separate versioned contract.")
        if candidate["material_type"] not in {"manual_intake", "synthetic"}:
            raise APIError("New structured intake must declare manual_intake or synthetic provenance.")
        texts = payload["source_texts"]
        if not isinstance(texts, dict) or set(texts) != {item["id"] for item in candidate["sources"]}:
            raise APIError("source_texts must contain exactly one supplied text per source ID.")
        checked_texts = {sid: string(value, "source_text", 500000) for sid, value in texts.items()}
        for claim in candidate["claims"]:
            fields = {"id", "source_id", "text", "excerpt", "locator", "event_date", "date_note", "attribution"}
            if claim.keys() - (fields | {"attribution_kind"}):
                raise APIError("Unexpected structured claim fields.")
            if claim["excerpt"] not in checked_texts[claim["source_id"]]:
                raise APIError("Each exact excerpt must appear in its own supplied source text.")
            if "attribution_kind" in claim and (not isinstance(claim["attribution_kind"], str) or claim["attribution_kind"] not in ATTRIBUTION_KINDS):
                raise APIError("Invalid attribution_kind.")
        for source in candidate["sources"]:
            require_fields(source, {"id", "title", "publisher", "url", "publication_date", "retrieved_at", "language", "translation_status", "access_note", "lineage_note"})
        metadata = candidate.get("rights_metadata", {})
        self.validate_context(metadata)
        mappings = payload["prepared_mappings"]
        if mappings is not None:
            version = RUBRIC_VERSION if payload["schema_version"] == "rights-intake/2" else RUBRIC_V1["version"]
            validate_dimensions(mappings, self.snapshot(candidate, None), version)
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if candidate["id"] in self.store.candidates(connection):
                raise APIError("Candidate ID already exists. Keep duplicate reports separate and link them for review.", 409, "duplicate_id")
            candidates = self.store.candidates(connection)
            if not set(candidate["related_candidate_ids"]) <= candidates.keys():
                raise APIError("Related candidate ID does not resolve.")
            self.validate_context_references(metadata, set(candidates) | {candidate["id"]})
            connection.execute("INSERT INTO intakes VALUES (?,?,?)", (candidate["id"], encoded(candidate), "\n\n".join(checked_texts.values())))
            for sid, source_text in checked_texts.items():
                connection.execute("INSERT INTO rights_source_texts VALUES (?,?,?)", (candidate["id"], sid, source_text))
            if mappings is not None:
                connection.execute("INSERT INTO rights_preparations VALUES (?,?)", (candidate["id"], encoded(mappings)))
        return candidate

    @staticmethod
    def validate_context_references(metadata, candidates):
        for item in metadata.get("related_cases", []):
            if item["candidate_id"] not in candidates:
                raise APIError("A contextual related-case reference does not resolve.")
        for item in metadata.get("pattern_hypotheses", []):
            if not set(item["supporting_candidate_ids"]) <= candidates:
                raise APIError("A pattern-hypothesis case reference does not resolve.")

    @staticmethod
    def validate_context(metadata):
        if not isinstance(metadata, dict):
            raise APIError("rights_metadata must be an object.")
        allowed = {"region", "case_unit", "identity_uncertainty", "related_cases", "country_context", "pattern_hypotheses", "published_expert_assessments"}
        if metadata.keys() - allowed:
            raise APIError("Unexpected rights metadata fields; country context cannot specify score adjustments.")
        for field in ("region", "case_unit", "identity_uncertainty"):
            if field in metadata:
                string(metadata[field], field, 8000)
        for field in ("related_cases", "country_context", "pattern_hypotheses", "published_expert_assessments"):
            if field in metadata and (not isinstance(metadata[field], list) or len(metadata[field]) > 100):
                raise APIError(field + " must be an array of at most 100 items.")
        for item in metadata.get("related_cases", []):
            require_fields(item, {"candidate_id", "basis", "material_differences", "identity_status"})
            identifier(item["candidate_id"])
            for field in ("basis", "material_differences", "identity_status"):
                string(item[field], field, 8000)
        for item in metadata.get("country_context", []):
            require_fields(item, {"label", "value", "year", "methodology", "url", "reuse_note"})
            if type(item["year"]) is not int or not 1900 <= item["year"] <= 2100:
                raise APIError("Context year is invalid.")
            public_url(item["url"])
            for field in ("label", "value", "methodology", "reuse_note"):
                string(item[field], field, 8000)
        for item in metadata.get("pattern_hypotheses", []):
            require_fields(item, {"hypothesis", "supporting_candidate_ids", "alternative_explanations", "further_evidence"})
            id_list(item["supporting_candidate_ids"], "supporting_candidate_ids")
            for field in ("hypothesis", "alternative_explanations", "further_evidence"):
                string(item[field], field, 8000)
        for item in metadata.get("published_expert_assessments", []):
            require_fields(item, {"publisher", "assessment", "url", "excerpt", "locator", "date"})
            public_url(item["url"])
            iso_date(item["date"], "date")
            for field in ("publisher", "assessment", "excerpt", "locator"):
                string(item[field], field, 12000)


def render_rights_markdown(document):
    m = markdown_text
    profile, rubric = document["case_profile"], document["rubric"]
    assessment = profile["assessment"]
    snapshot = assessment["evidence_snapshot"]
    claims = {item["id"]: item for item in snapshot["claims"]}
    sources = {item["id"]: item for item in snapshot["sources"]}
    rows = ["# " + m(snapshot["title"]) + " — provisional rights profile", "", document["disclaimer"], "",
            "Material: **" + m(snapshot["material_type"]) + "** · Country: " + m(snapshot["country"]), "",
            "Assessment revision: " + str(assessment["revision"]) + " · Evidence revision: " + str(assessment["evidence_revision"]) + " · Rubric: " + m(assessment["rubric_version"]), "",
            "Analyst: " + m(assessment["analyst"]) + " · Assessment date: " + m(assessment["assessment_date"]) + " · Preparation: " + m(assessment["preparation"]), "",
            "Current review status: **" + m(profile["review_status"]) + "** · Current evidence revision: " + str(profile["evidence_revision"]), ""]
    if profile["stale_evidence"]:
        rows += ["**STALE EVIDENCE: later evidence reviews/corrections do not rewrite this saved assessment. Reassess and review before relying on it.**", ""]
    rows += ["## Methodology", "", rubric["scoring_method"], "", rubric["limits"], ""]
    rows += ["- " + level + ": " + text for level, text in rubric["scale"].items()] + ["", "Non-numeric states: insufficient_evidence, not_assessed and not_applicable are distinct from zero.", "", "Confidence: " + rubric["confidence_method"], "", "Completeness: " + rubric["completeness_method"], ""]
    for group, label in (("fair_trial", "Fair-trial dimensions"), ("expression", "Expression dimensions")):
        rows += ["## " + label, ""]
        for item in profile["profiles"][group]:
            definition = next(value for value in rubric["dimensions"] if value["id"] == item["dimension_id"])
            score = str(item["score"]) if item["score"] is not None else item["status"]
            rows += ["### " + definition["label"] + " — " + score, "", "Standard: " + definition["standard"], ""]
            if "questions" in definition:
                rows += ["Stage: " + definition["stage"], "", "Exceptions/applicability: " + definition["exceptions"], "",
                         "Observable components: " + "; ".join(definition["components"]), "", "Factual questions: " + "; ".join(definition["questions"]), ""]
            rows += ["- [" + m(c["label"]) + "](" + c["url"] + "), " + m(c["locator"]) for c in definition["citations"]] + [""]
            if snapshot["country"] in rubric["jurisdiction_standards"]:
                rows += ["Jurisdiction provisions to assess: " + "; ".join("[" + m(c["label"]) + "](" + c["url"] + "), " + m(c["locator"]) for c in rubric["jurisdiction_standards"][snapshot["country"]]), ""]
            rows += ["Applicability: " + m(item["applicability"]), "", "Provisional analyst explanation: " + m(item["explanation"]), "",
                     "Evidence confidence: " + m(item["confidence"]) + " · Completeness: " + m(item["completeness"]), "",
                     "Missing facts: " + m("; ".join(item["missing_facts"]) or "None recorded; completeness is not certified."), "",
                     "Next verification: " + m(item["next_verification"]), ""]
            review = profile["dimension_reviews"].get(item["dimension_id"])
            rows += ["Human dimension review: " + (m(review["decision"]) + " by " + m(review["reviewer"]) + " · Reason: " + m(review["reason"]) + " · Exact claims: " + m(", ".join(review["claim_ids"]) or "none") + " · " + m(review["scope"]) if review else "pending; no human approval"), ""]
            for ids, evidence_label in ((item["support_claim_ids"], "Supporting evidence"), (item["contrary_claim_ids"], "Contrary evidence / competing account")):
                rows += ["#### " + evidence_label, ""]
                for claim_id in ids:
                    claim = claims[claim_id]
                    source = sources[claim["source_id"]]
                    rows += ["**" + m(claim_id) + "** · " + m(claim.get("attribution_kind", "source_attributed_claim")) + ": " + m(claim["text"]), "",
                             "Attribution: " + m(claim["attribution"]), "", "Exact excerpt: " + m(claim["excerpt"]), "",
                             "Source: [" + m(source["title"]) + "](" + quote(source["url"], safe=":/?#[]@!$&'*+,;=%") + ") · Locator: " + m(claim["locator"]), "",
                             "Event date: " + m(claim["event_date"] or "unknown") + " · Published: " + m(source["publication_date"] or "unknown") + " · Retrieved: " + m(source["retrieved_at"] or "unknown"), "",
                             "Language / translation: " + m(source["language"] + " / " + source["translation_status"]), "",
                             "Source lineage / access: " + m(source["lineage_note"] + " / " + source["access_note"]), ""]
                    if "original" in claim:
                        rows += ["Original statement preserved: " + m(claim["original"]["text"]), "", "Original exact excerpt: " + m(claim["original"]["excerpt"]), ""]
                if not ids:
                    rows += ["None mapped. Missing evidence does not establish absence.", ""]
    rows += ["## Context and related-case hypotheses", "", "Context has no score adjustment. Similarity is not identity, case frequency or a movement; selected corpus coverage and reporting bias limit patterns.", "",
             "```json", json.dumps(profile["context"], ensure_ascii=False, indent=2).replace("<", "\\u003c").replace(">", "\\u003e"), "```", "",
             "## Review and revision history", "", "Separate evidence triage: " + m(json.dumps(profile["current_evidence_review"], ensure_ascii=False)), "",
             "Preparation provenance: " + m("; ".join(profile["preparation_provenance"])), "", profile["review_scope_note"], ""]
    rows += ["- Assessment revision " + str(row["revision"]) + ", evidence revision " + str(row["evidence_revision"]) + ", " + m(row["assessment_date"]) for row in document["assessment_history"]]
    rows += ["- Rights review revision " + str(row["revision"]) + ": " + m(row["decision"]) + " by " + m(row["reviewer"]) + " for " + m(", ".join(row["dimension_ids"])) + "; exact claims " + m(", ".join(row["claim_ids"]) or "none") + "; " + m(row["reason"]) for row in document["rights_review_history"]]
    rows += ["- Evidence triage/correction revision " + str(row["revision"]) + ": " + m(row["decision"]) + " by " + m(row["reviewer"]) + "; selected observations " + m(", ".join(row["included_claim_ids"]) or "none") + "; corrected observations " + m(", ".join(item["claim_id"] for item in row["corrections"]) or "none") + "; " + m(row["reason"]) for row in document.get("evidence_review_history", [])]
    rows += ["- Evidence addition revision " + str(row["revision"]) + ", unified evidence revision " + str(row["evidence_revision"]) + ": " + m(row["origin"]) + " by " + m(row["author"]) + " at " + m(row["created_at"]) + "; added observations " + m(", ".join(claim["id"] for claim in row["claims"])) + "; " + m(row["scope"]) for row in document.get("evidence_addition_history", [])]
    return "\n".join(rows + ["", document["snapshot_policy"], ""])
