# A small evidence batch that teammates can exchange

October 9 update: this is a working protocol, not a completed study. The primary route is a bounded collection of permitted public documents, structured by the team and checked by humans. Do not wait for a TrialWatch sample or assume a database exists; a future permitted export is optional. The accepted first evidence drill concerns notice of charges, opportunities to respond and documented responses. The nine-observation v1 preparation snapshot is frozen; the later 20-observation v2 and its partial human-review status are described below. Continue from saved reviews, preserving their limited scope, and identify only decision-relevant gaps. Later CSV additions use a new seed and fresh state. There is no fixed two-history requirement or observation quota. Keep populated research separate from the synthetic demonstration. Use the [candidate-pattern worksheet](PATTERN_REVIEW_WORKSHEET.md) for relationships across records; the CSV importer and app still perform manual campaign comparison.

## Record one claim at a time

**Current review checkpoint:** the later v2 batch contains 20 observations. Lucas S completed a limited review of four C02 observations, saved Include review/analysis revision 1 and exported a cited memo. Original v1/v2 preparation files remain frozen; their pending labels describe preparation, not the latest app state. Read [current decisions](DECISIONS.md) before treating historical status text as current. Other observations/proposals remain outside the completed review; no full source/proceeding authentication is implied.

Copy this compact record for discussion, or use the header-only [CSV template](../examples/research_records.template.csv) for import. One narrow source-attributed claim per row; two reports about one event are two observations about that event, not two actions.

| Block | What to enter |
| --- | --- |
| Identity | Observation ID; event ID (shared across repeated accounts, or unknown); dossier ID/title; person(s); exact proceeding/charge/stage; country. Do not join records just because names match. |
| Evidence | Attributed summary; exact short excerpt in original language; paragraph/section locator; source ID/title/publisher/URL; source allegation, reported court finding, reported activity, analyst judgment or proposed advocacy. An organization's account of a court order remains a reported finding. |
| Dates and limits | Event date and its basis; publication date; actual retrieval timestamp when known; language/translation status; access and upstream-source limits; dossier unknowns. Preserve unknowns rather than inventing dates. |
| Review and coding | Proposed primary category; review status; checker and check timestamp; notes describing campaign actor/objective, recipient, action stage, policy stage, conflicting IDs and questions. AI feasibility review is separate from human checking and from an app Include decision. |

For `notes`, use a short convention: `actor=...; objective=...; recipient=...; action_status=planned/completed/reported/unknown; policy_stage=demand/proposal/adopted/in_force/implemented/unknown/not_applicable; conflicts_with=...; scope=within_window/context_only; question=...`. These notes are free text, not validated legal classifications. Retain conflicting accounts; never overwrite one to manufacture agreement.

## CSV field guide

The template has 30 columns, grouped by dossier, source and observation. Copy repeated dossier/source metadata exactly; the importer rejects inconsistent metadata for the same IDs. Fill shared metadata once and copy it down. Use UTF-8 CSV; preserve quoted commas/newlines. Spreadsheet software is optional. The importer reads CSV as text, never executes cells. When using a spreadsheet, import text as text and inspect cells beginning with formula characters.

- `dossier_id,dossier_title,person,proceeding,country,dossier_unknowns`: explicit grouping, not automatic identity resolution. State unresolved identities/stages in unknowns.
- `source_id,source_title,publisher,url,publication_date,retrieved_at,language,translation_status,access_note,lineage_note`: provenance. A distinct URL does not establish independent corroboration. Put article update dates in `access_note`; do not backdate additions.
- `observation_id,event_id,summary,excerpt,locator,event_date,date_note,attribution,attribution_type,observation_category`: evidence and proposed coding. A summary must not claim more than its excerpt. Put event-date support in the excerpt or locator/date note; a publication date alone is insufficient.
- `review_status,checked_by,checked_at,notes`: audit trail. Status choices: `unreviewed`, `ai_feasibility_only`, `human_checked`. The latter two require a checker and timestamp. `human_checked` means the named person performed the described check, not that the whole dossier is true.

Use `YYYY-MM-DD` for event/publication dates and timezone-aware ISO timestamps for retrieval/checks, for example `2026-10-09T14:00:00-04:00`. Empty or `unknown` dates remain null. If only a month/range is known, leave the date empty and preserve that precision in `date_note`. `retrieved_at` records actual source access, not when a note was written. Use `und` when language is unknown and record translation status; never silently replace original-language evidence with an AI translation.

Attribution types: `source_allegation`, `reported_court_finding`, `reported_activity`, `analyst_judgment`, `proposed_advocacy`. Categories: `social_media`, `international_attention`, `campaign_action`, `legal_outcome`, `policy_outcome`, `context`. Proposed advocacy and analyst judgment must remain labeled and must not be presented as completed actions. CSV coding is guidance only; no analysis is automatically saved.

## Build a dossier from several reports

Work in an ignored local research folder. Keep the header-only template unchanged. These commands are examples to run after filling a working copy:

```powershell
New-Item -ItemType Directory -Force data/processed/research
Copy-Item examples/research_records.template.csv data/processed/research/records.v1.csv
# Fill the working CSV with the agreed records, then:
python scripts/build_research_seed.py data/processed/research/records.v1.csv --output data/processed/research/campaigns.v1.json
python -m reviewdesk --seed data/processed/research/campaigns.v1.json --state-dir data/processed/research/review.v1 --port 8770
```

The importer groups observations by explicit dossier ID and sources by source ID. It validates structure, dates and metadata consistency, and refuses to overwrite an output. It does not fetch URLs, authenticate quotations, check substantive support or create a human review. Open each dossier, inspect its provenance, save an Include review, and explicitly classify/save its analysis. Even `human_checked` CSV records enter the app without a saved review.

**Add a report** still creates an individual dossier. The importer is the batch workaround; in-app append-to-dossier and shared-database synchronization are not implemented. A changed CSV produces a new seed version and requires a fresh state directory. It does not merge into existing SQLite reviews. Export the previous memo first, retain its seed/state/history, and reassess the new version. Within one version, evidence corrections preserve originals and flag affected saved analyses as stale.

## Exchange and completion

1. Assign one consolidator and one authoritative versioned CSV. Collectors work in separate copies and return their records plus a short search log. Use an already approved team channel; this document does not send files or change sharing permissions.
2. Allocate observation prefixes, such as `collector_a_001`. Agree dossier/source/event IDs before merging. Repeated accounts share an event ID; disagreements keep separate observation IDs and cross-reference one another.
3. Record a search log alongside the CSV: query/source, language, covered dates, access result, included/excluded IDs and reason. Use the same effort cap per history. No result means unknown coverage, not no activity.
4. A second human checks every retained row in this small batch for identity, excerpt, attribution, date roles and outcome/action stage. Record disagreements and unresolved items; do not promote AI checks to human checks.
5. The consolidator creates `records.v1.csv` and `campaigns.v1.json`, then hands them and the search log to the analyst. The analyst returns a candidate-pattern worksheet, unresolved questions and saved analysis revisions, trying a brief, evidence table or timeline according to the user task. The presenter uses explicitly fictional material for the public workflow demonstration; copying or relabeling real records does not make them synthetic.

Batch done means the agreed small slice is documented (or its shortfall recorded), all retained rows are checked or visibly unresolved, source dependence and uncertain case/event links are visible, and an editable result identifies what an advocate should verify next. Seek a second separately sourced account when feasible; two URLs are not a corroboration threshold. No unsupported current-status, trend, causal or forecasting claims. A target count or successful import does not establish research quality.

Filled CSVs, research seeds, source captures, feedback, real comparison exports and runtime databases stay outside the public allowlist. GitHub shares code and the empty template, not review state. Do not exchange full subscription documents. Git ignore rules neither encrypt files nor change Dropbox sharing.
