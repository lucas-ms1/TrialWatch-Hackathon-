# Versioned data contracts

## Pending AI draft — separate preparation contract

`ai-draft.schema.json` and runtime `reviewdesk/draft_contract.py` define the bounded pending-draft structure. The clean input carries supplied passages, exact passage-to-intake-claim bridges, current rubric, retained standards and unresolved review state. `examples/ai-draft.synthetic.json` is an entirely fictional, provider-free app-import example. It is neither rights intake nor a saved assessment and must not be passed to `validate_rights.py` as either.

Saved real imports retain raw draft/input/schema/receipt hashes and validate citations, contrary accounts, null dates, scope and twenty unassigned mappings. App records add immutable revisions, provenance, evidence/rubric dependencies and separately attributed addenda. Source-summary reviews are separate from rights reviews. An explicit worksheet bridge saves all-not-assessed rights preparation and a pending deterministic intervention proposal, with exact AI-draft dependencies. See [API and setup](../docs/AI_DRAFTING.md). Runtime checks establish integrity, not substantive accuracy or legal approval.

The legacy evidence contract below retains its score-free semantics. The October 9 rights pivot adds a separate, explicit assessment contract; it is an original prototype method, not an official TrialWatch grading methodology. Own preparation is assumed permitted at the user's direction.

Run from the workspace root with Python 3.11 or newer; no installation or external packages are needed:

```powershell
python scripts/validate_data.py examples/cases.synthetic.json
python -m unittest discover -s tests -v
```

The JSON Schema defines the record structure. The standard-library validator implements only its used subset of keywords and adds the semantic rules below. It does not implement the entire JSON Schema specification, fetch source pages, verify quotations, or assess guilt or legality. It rejects unknown schema keywords so unsupported future schema additions fail visibly. Exit codes are 0 for valid files, 1 for input failures, and 2 for CLI or schema-loading errors.

- Each case is a review candidate with a document-unique `case_id`, an explicit `synthetic` flag, and one Southeast Asian country code. Country codes are scope metadata; they imply no comparative assessment of countries.
- Sources need an ID, HTTP(S) URL, publisher, publication date (or `null`), retrieval timestamp with timezone, and a language tag. Source IDs and claim IDs must be unique within a case. Evidence references are local to their case.
- Every claim needs at least one source-linked quote and a locator such as a page, paragraph, or timestamp. Record attributed reports and allegations as such. A citation alone does not prove that a claim is supported: a person must compare the source, quote, and claim.
- Preserve the original source-language text in `quote`. Set `translation` to `null` when no translation exists; otherwise record its text, target language, human/machine method, and reviewer (or `null` if unreviewed). Source `language` describes the original. An unreviewed machine translation is not verified evidence.
- `event_date` belongs to the reported event. `published_date` belongs to its source. Never substitute one for the other. Use ISO dates (`YYYY-MM-DD`) or `null` if unknown; use timestamps with timezone for retrieval and review. Do not invent dates or silently translate quotations.
- `pending`, `in_review`, `needs_sources`, and `ready_for_expert_review` are human workflow states. The last requires a named reviewer and review timestamp; it is not a legal finding. Cases with no claims must have `needs_sources` status.
- Descriptive labels, country selections, and source metadata also need human verification. The contract contains no subjective numeric guilt, risk, or fairness score.

`examples/cases.synthetic.json` contains only invented cases, invented evidence text, and nonresolving `example.invalid` URLs. Countries are illustrative routing labels. No example represents a real person, prosecution, event, publisher, or legal rule. The third fixture shows an intake shell with no asserted facts. Keep synthetic examples distinct from any future real source collection, and do not present them as research findings.

## Rights assessment v1 — separate extension

`rights-assessment.schema.json` describes saved `rights-assessment/1` records under `rights-rubric/1.0`. It does not change `cases.schema.json`, legacy dossier fields, campaign coding or historical review meaning. Runtime semantic validation in `reviewdesk/rights.py` enforces all nine dimensions once, valid states/rule names, resolving support/contrary references, separate confidence/completeness, scope and revision dependencies. The JSON Schema is a saved-assessment specification; the CLI uses runtime validation and does not claim to implement all JSON Schema features.

```powershell
python scripts/validate_rights.py reviewdesk/rights.synthetic.json examples/rights-intake.synthetic.json
python -m unittest discover -s tests -v
```

`reviewdesk/rights.synthetic.json` is the reproducible synthetic seed; `scripts/build_rights_seed.py` builds it. `examples/rights-intake.synthetic.json` is a complete fictional structured-intake document. All fixture passages are invented, with `example.invalid` source URLs. Real evidence belongs in ignored storage, never a copied fixture labelled synthetic.

Structured intake `rights-intake/1` has exactly `schema_version`, `candidate`, `source_texts` (one supplied text for each source ID) and `prepared_mappings` (all nine explicit mappings or null). Candidate/source/claim provenance follows the runtime dossier contract. Each claim's excerpt must occur in its own source text. Unknown dates remain null and no translation is invented. Optional rights metadata contains case/identity units, region, related reasons/differences, separate country-year context, pattern hypotheses and separately attributed expert assessments. Context cannot specify score adjustments.

Assessment input requires `expected_revision`, `expected_evidence_revision`, `rubric_version`, `analyst`, `preparation` and nine `dimensions`. Each dimension contains `dimension_id`, `status`, `concern_level`, supporting/contrary claim ID lists, `explanation`, `confidence`, `completeness`, `missing_facts`, `next_verification` and `applicability`. The server computes `score` from the anchor and rejects a client-supplied score. Non-numeric states have null concern/score. Zero requires affirmative cited support; no missingness default. Saved records add assessment date/revisions and immutable evidence snapshot. Standards/citations travel in the export rubric.

A `rights-review/1` human record references exact assessment/evidence revisions, reviewer/reason, approve/request-changes decision and exact dimensions/claim IDs, including all contrary references. Unassessed dimensions cannot be approved. Gap/applicability judgments can be reviewed without inventing numerical values. New assessment revisions need new review. Evidence corrections preserve originals and make previous assessments stale; stale approvals remain historical, without current approval.

Routes: GET `/api/rights/state`, `/api/rights/rubric`, `/api/rights/export/<id>?format=md|json`; POST `/api/rights/intake`, `/api/rights/draft/<id>`, `/api/rights/assessments/<id>`, `/api/rights/reviews/<id>`. Legacy `/api/reviews/<id>` stores reasoned evidence corrections; prepared mappings are not an approval. Invalid fields/references/excerpts/revisions fail visibly. No URL fetching, PDF parser or fresh model call occurs. Legal support/authenticity/applicability are human checks beyond schema integrity.

## Rights assessment v2 and connected intervention

`rights-assessment.v2.schema.json` specifies `rights-assessment/2`, `rights-rubric/2.0`: thirteen core fair-trial, three conditional and four expression dimensions. Original schema/seed/intake and `reviewdesk/rights-rubric.v1.json` retain v1. Runtime validation uses the matching dimension set. New/split/changed dimensions never inherit combined scores; reviews identify exact revisions.

```powershell
python scripts/validate_rights.py reviewdesk/rights.synthetic.v2.json examples/rights-intake.synthetic.v2.json
python scripts/rehearse_intervention.py
```

`rights-intake/2` selects the v2 rubric through its schema version; the supplied-text/candidate/prepared-mapping structure remains. It does not add a rubric_version input field. The builder reproduces current v2 fixtures; original v1 fixtures stay immutable. Exports use saved rubric definitions.

`intervention.schema.json` describes saved context/proposal/review/follow-up records. Runtime services enforce excerpt/reference/cutoff/dependency/scope/alternative/prerequisite rules; this is not factual validation or a general JSON Schema engine. `examples/intervention.synthetic.json` supplies invented context, two options and a conditional scenario.

GET `/api/interventions/state/<case_id>`, `/api/interventions/export/<recommendation_id>?format=md|json`; POST `/api/interventions/contexts/<case_id>`, `/proposals/<case_id>`, `/reviews/<recommendation_id>`, `/followups/<recommendation_id>`. [INTERVENTION_API](../docs/INTERVENTION_API.md) specifies precise requests and semantics.

Proposals snapshot linked rights/context versions and review scope. Changed dependencies make them stale, retaining decisions. Revised human disposition is separately attributed against the immutable proposal. Follow-up kinds: observed_action, observed_outcome, conditional_scenario, unknown_outcome; plans reside in options/next steps. No AI discovery, weighted opportunity score, likelihood model, outreach or monitoring.
