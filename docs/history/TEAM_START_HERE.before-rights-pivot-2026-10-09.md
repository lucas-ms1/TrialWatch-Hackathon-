# Start here: TrialWatch team handoff

**October 9, 2026 · Track 3: Advocacy and Impact · Philippines first.** The intended product connects advocacy strategy with collective-action signals. We have a working manual app and a separate fictional interface concept; the integrated product remains to be built.

## Try the current work

From the repository root, with Python 3.11 or newer:

```powershell
python -m reviewdesk --port 8767
```

Open `http://127.0.0.1:8767` and keep the terminal running. No extra packages, API keys or internet access are needed. The default is **three fictional dossiers and 14 observations**, not real cases or evaluation results. Review evidence, save an Include decision, classify observations in Analysis, save the analysis, then compare and export. See the [README](../README.md) for the full walkthrough.

State persists locally under `data/processed/campaigndesk/`. To start a fresh rehearsal, add `--state-dir data/processed/my-rehearsal`. Each teammate has a separate database; GitHub does not synchronize reviews.

Open either file directly in a browser for an offline walkthrough:

| File | What it demonstrates |
| --- | --- |
| [Current-app fallback](demo/fallback.html) | A generated comparison from the working backend, using scripted fictional reviews and coding. |
| [Strategy-and-signals concept](demo/signals-and-strategy.html) | A clickable fictional protest-arrest scenario: candidate cluster → public response → strategy. It is a standalone concept, not a connected backend or detector. |

The app currently provides manual intake/import, attributed excerpts, review/corrections, comparisons, timelines, cited exports and warnings when saved analyses refer to older evidence. Automatic collection, cluster discovery, analogue retrieval, movement detection and outcome forecasting are not implemented. The concept does not persist decisions or make model calls.

## Read these next

| Need | Start with |
| --- | --- |
| Current priorities, gaps and timing | [Sprint plan](SPRINT_PLAN.md) and [latest decisions](DECISIONS.md) |
| Product vision and implementation boundary | [Project brief](PROJECT_BRIEF.md) and [technical plan](TECHNICAL_PLAN.md) |
| Evidence and comparison rules | [Analysis method](ANALYSIS_METHOD.md) and [pattern-review worksheet](PATTERN_REVIEW_WORKSHEET.md) |
| Prepare a permitted evidence batch | [Import/handoff guide](RESEARCH_HANDOFF.md) and [empty CSV template](../examples/research_records.template.csv) |
| Demo and final delivery | [Demo script](DEMO_SCRIPT.md), [submission checklist](SUBMISSION_CHECKLIST.md) and [event requirements](EVENT_BRIEF.md) |

Older dated decision entries and files under `history/` preserve previous scope. Use the latest decision entries and sprint plan for current work. The existing app demo script describes the implemented comparison baseline, not the complete intended product.

## Decisions and work to assign

**Before leaving Friday at 6 p.m.:** aim for one runnable evidence-to-decision walkthrough and a clear restart/handoff for tomorrow. Assign building, evidence-checking and demo/handoff owners; use the 4:45 p.m. checkpoint to choose a stable build or the documented app/worksheet fallback. Test together after 5:20 and save the exact working version and next tasks before leaving. The [sprint plan](SPRINT_PLAN.md) has the schedule; the [plain-language group update](TEAM_MESSAGE.md) is ready to share.

1. **Data and evidence — owner unassigned.** Use permitted public documents as the primary route, starting with the existing local sample. Scope the missing evidence and assign extraction, human checking and consolidation. A TrialWatch sample request is not a dependency; a future permitted export is optional and its existence/access remains unconfirmed. Case facts, advocacy actions, outcomes and collective-action signals each need supporting evidence.
2. **Product and implementation — owner unassigned.** Choose a practitioner, one useful task and the final demo slice. A proposed minimum is saved evidence → explained candidate connection → conflicting/repeated-source evidence → documented public response → objective → cited strategy draft. Connect it to the existing review, persistence and export features.
3. **AI and evaluation — owner unassigned.** Choose one bounded contribution, such as excerpt-backed extraction or explained candidate links, and define its inputs, baseline and errors. Define an outcome and time horizon before attempting forecasts; credible likelihoods and effectiveness rankings are not available today.
4. **Demo and delivery — owner unassigned.** Check usefulness with a person, rehearse the actual flow, align the script/fallback and rebuild the allowlisted package. Confirm team details, delivery channel and final handoff. Deadline: **October 10 at 3:30 p.m. ET**, with a **10–15-minute demo**.

The accepted first real evidence drill concerns notice of charges, opportunities to respond and subsequent legal/public responses. The local v2 batch has 20 observations across three provisional histories/eight sources. Lucas S completed a limited C02 review covering O03/O04/O05/O10, with saved review/analysis revision 1 and a cited export. Acceptance is a source-reported sequence recorded in the review reason; a structured candidate-decision workflow is still absent. The original order and identity matching remain unresolved, and other observations/proposals remain outside the review. The populated batch, database and memo are excluded from GitHub. This does not establish advocacy usefulness/effectiveness or forecasting accuracy. The fictional protest-arrest concept remains separate.

## Source and sharing boundaries

Share original code/docs, empty templates and fictional fixtures through this repository. Keep filled real research records, third-party captures, correspondence, credentials, restricted documents and runtime databases outside the public file set. Ignore rules do not encrypt files or control Dropbox access. MIT covers original code/docs and synthetic fixtures, not third-party source material.

Every real claim needs attribution and a supporting passage, with event dates separate from publication/retrieval dates. Retain contradictions, unknowns and source dependence. Reports, cases, people and arrest events are different counts; a cluster does not establish a coordinated movement, and NGO reporting alone does not prove independent corroboration. Plans, reported ongoing activity, observed outcomes and forecasts are separate claims. AI preparation is not human review.

This GitHub handoff does not start source monitoring, external model calls or outreach, and it does not submit the project to organizers. Public organization/event context is in scope; private participant tracking is not.
