> Historical document: superseded for active scope by the latest entries in [DECISIONS.md](../DECISIONS.md). Original prose retained; relative links adjusted for this archive folder.

# Implementation notes, separate from the team plan

October 9, 2026. Preparation only; the application remains a manual, deterministic campaign-comparison prototype. No fresh model calls or data collection have been added.

## Reuse and missing work

| Component | Available now | Missing for the broader idea |
| --- | --- | --- |
| Evidence intake | Manual text/URL intake; 30-field CSV bridge groups reports under explicit dossier IDs | Automatic extraction, in-app append to existing dossier, synchronized editing |
| Review and provenance | Selected claims with excerpts, attribution, date roles, language/translation notes, originals and correction history | Substantive fact authentication and human review of a new batch |
| Connections | Manual duplicate links; supplied event IDs and source-lineage notes survive import | Suggested identity/event matches, merge adjudication, independent-source assessment |
| Comparison | Any number of saved dossier analyses, six manual observation roles, dated/undated timelines, Markdown/JSON exports | Cross-case features, emergent themes, candidate-pattern records and support/challenge relationships |
| Revisions | Saved analyses snapshot evidence; later review revisions flag stale analyses | Automatic dependency tracking for the external worksheet; check it manually |
| Advocacy handoff | Editable comparison; retained per-dossier briefing backend | Agreement on user task/output and a usefulness check |

Implementation locations: reviewdesk/server.py (evidence_export, campaign, campaign_export, advocacy), reviewdesk/static/app.js and scripts/build_research_seed.py. A dossier is an analyst grouping, not a verified unique case. Event IDs and distinct URLs do not produce deduplicated case/event counts or prove corroboration. The legacy case validator and runtime dossier format are separate structures.

## Smallest useful next improvement

Prepared now: a blank [pattern-review worksheet](../PATTERN_REVIEW_WORKSHEET.md) and [proposal prompt](../PATTERN_PROPOSAL_PROMPT.md). Use a copy beside an evidence export. Carry stable observation IDs, source references and evidence versions through to the interpretation. Manually recheck dependencies after corrections. This establishes needed information without choosing the first dataset or extending the database prematurely.

If the trial proves useful, add a saved candidate-pattern object referencing existing selected claims and their snapshots. Store supporting/challenging/context roles, fixed/emergent features, identity and source-lineage uncertainty, human disposition and next verification action. Flag it when evidence changes or is excluded. This is the recommended first software extension, not an implemented feature or agreed milestone.

## An AI demonstration without training

An existing general-purpose model can be tested as a proposal assistant: provide permitted excerpts and a few checked examples of acceptable versus unsupported links; ask for structured observations, tentative matches and candidate patterns with exact evidence IDs. A human accepts, revises or rejects each proposal. Model-generated reviews are labeled AI, never human. Restricted records require verified permission for the chosen processing environment before any upload.

Separate extraction, identity matching, source-dependence assessment and pattern suggestions so a plausible final paragraph cannot conceal a bad intermediate link. Human checks should deliberately include repeated reports of one event, uncertain identities, a contrary record, missing dates and an unsupported causal inference. Ask whether the model abstains and keeps citations attached. Freeze proposals before independent checking; save errors as well as successes. A small trial exposes failure modes, not general accuracy.

Training/fine-tuning becomes an option after we have a stable task, enough permitted examples with reliable labels, an independent evaluation set and an error that simpler instructions/examples do not address. It cannot cure missing evidence, shared upstream sources or an unrepresentative sample. Testing an existing model plus examples and human review is the recommended first route. Provider/model choice and paid/API execution remain undecided.

Change detection needs a declared sampling frame, stable coverage and adjudicated event units before comparing periods. Forecasting additionally needs prospective or strictly time-held-out outcomes, leakage controls, meaningful baselines and false-alert/calibration checks. The frozen historical AI-reference triage experiment supplies none of these results and stays unchanged.
