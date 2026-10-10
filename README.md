# TrialWatch Rights and Intervention Desk — local prototype

Start with [TEAM_START_HERE](docs/TEAM_START_HERE.md). The product connects an evidence-backed fair-trial/expression case index to dated context, alternative advocacy strategies, an inspectable intervention proposal, human disposition and later outcome follow-up. **Track 3: Advocacy and Impact** remains the framing. Legal evaluation overlaps Track 2; this is not an organizer-approved track change or an official TrialWatch assessment.

The latest October 9 clarification connects advocacy/intervention decision support to the index. [The previous rights-only checkpoint](docs/history/README.before-connected-intervention-2026-10-09.md) and earlier planning/research remain preserved.

## Run and preserve the previous state

Python 3.11+; standard library and buildless frontend. Synthetic demonstration needs no credentials, packages, paid service, model runtime or internet.

```powershell
cd "C:\Users\freew\Dropbox\School\TrialWatch Hackathon"
python -m reviewdesk --port 8768 --state-dir data/processed/connecteddesk-v2
```

Open [the connected desk](http://127.0.0.1:8768/rights.html). Keep the terminal running; Ctrl+C stops it. Each machine has separate SQLite state. Use a fresh directory for a different seed. The new default is synthetic; it is separate from real evidence and earlier state. To reopen the previous rights baseline use `--seed reviewdesk/rights.synthetic.json --state-dir data/processed/rightsdesk-v1` with a free port. Historical comparison remains at `/index.html`, or explicitly start its original seed/state pair. Never load a changed seed into an existing state directory.

The completed local walkthrough is available at [fictional corrected notice case](http://127.0.0.1:8768/rights.html?case=connected_browser_intake). Its earlier simulated acceptance is deliberately stale after a fictional correction. Synthetic A also holds separate insufficient-basis and specified-deferral examples, pending human review. These local records are excluded from the package; a fresh clone starts with unsaved fixtures. Run `python scripts/rehearse_intervention.py` to create a fresh isolated completed software rehearsal and cited before/after exports.

To reopen the preserved previous rights state separately:

```powershell
python -m reviewdesk --port 8769 --seed reviewdesk/rights.synthetic.json --state-dir data/processed/rightsdesk-v1
```

## Fictional strategy generator

To add the illustrative Mara Vale case to a fresh synthetic starter, run this before starting the server with the same state directory:

```powershell
python scripts/load_synthetic_strategy_case.py --state-dir data/processed/connecteddesk-v2
```

Open **Mara Vale → Advocacy / intervention → Generate advocacy options**. The original packet generates preparation and deferred-publicity options. The scenario selector adds clearly marked fictional passages demonstrating a counsel-action proposal, private clinic coordination, or advice against a named public campaign. Exact supporting and competing quotations open in the page; cited Markdown and JSON previews are downloadable. These browser-generated previews do not save a proposal or change review status. Existing saved proposals and tools remain expandable below. The loader refuses to replace an existing Mara case.

The same generator works in the [published demo](https://lucas-ms1.github.io/TrialWatch-Hackathon-/demo/rights.html?case=synthetic_mara_vale_20261010&tab=advocacy). Other editing and saving require the local app. Generation uses original route templates and the existing prerequisite rules; no model request is made. Run `node scripts/check_synthetic_strategy.cjs` for the focused strategy and cited-export checks (Node.js is needed only for that optional check).

The [public Melayu Raya example](https://lucas-ms1.github.io/TrialWatch-Hackathon-/demo/rights.html?case=organizer_melayu_raya_20261010&tab=assessment) publishes selected redacted passages and the prepared twenty-criterion analysis. Its source links open the published excerpt edition with original derived locators and disclosed name substitutions. Original supplied documents and full captures remain private; assessment and proposal review remain pending.

## Connected walkthrough

1. **Evidence intake:** supply UTF-8 source text and exact excerpts, or import structured fictional evidence. **Import judgments** previews a local LawPhil judgment bundle, lets you select quoted passages and saves an unassessed case. Sources retain attribution, locators, date roles, language, translation status and upstream dependence. No URL fetching or binary PDF/OCR parsing is integrated. See [judgment import and source terms](docs/JUDGMENT_IMPORT.md).
2. **Rights profile:** inspect a compact tile grid for thirteen core fair-trial dimensions, three conditional safeguards and four expression dimensions. Hover or focus for a summary; select a tile for the standard, rationale, support/contrary passages, gaps and next check. Scored tiles fill upward in thirds for ordinal concern 0–3; missing/unassessed/not-applicable states are distinct. Revise assessment opens the existing explicit editor for applicability, concern, explanation and separate confidence/completeness. No due-process umbrella score or combined percentage exists.
3. **Scoped review:** review the exact dimensions and cited observations with a name and reason. A whole-case approval is unnecessary for a useful verification proposal. Pending/unassessed material remains visible.
4. **Advocacy / intervention:** supply dated source-backed case or reviewed candidate-cluster context. Compare at least two options and inspect opportunity, authority, timing, feasibility, potential harm and unknown preferences separately. Generate a deterministic worksheet proposal; legal concern alone never selects an action.
5. **Human disposition:** accept, revise, reject or defer the exact recommendation with reasons and exact reviewed rights/context scope. This saves a decision proposal, never executes advocacy or creates organizational authority.
6. **Index, export and follow-up:** inspect status/dependencies, reopen state and download cited Markdown/JSON. Corrections, new assessment revisions and material context revisions make dependent recommendations stale while retaining earlier snapshots/decisions. Plans remain in options and next steps. Follow-up supports observed actions, observed outcomes, conditional scenarios and explicitly unknown outcomes; chronology does not prove contribution.

Prepared historical examples can populate the complete rights profile through the existing assessment contract. The **AI-prepared assessment** badge identifies that origin; approval is recorded separately. Additional quotations from an existing retained source are append-only, with their own closed revision history. See [retained passages and prepared analysis](docs/JUDGMENT_IMPORT.md#retained-passages-and-prepared-analysis).

Supplied document text can use a local source link at `/api/rights/source-text/<case-id>/<source-id>`. It opens the retained text and provenance without fetching a public source or changing review status. DOCX preparation happens outside the app; original layout, comments and page numbers require the supplied document copy. Any omitted personal details or uncertain translation provenance must be recorded with the prepared text.

The six proposal dispositions distinguish intervene now, preparation/targeted verification, referral/coordination, deferral of a specified route, advice against a specified route, and insufficient basis. Deferral of public advocacy can coexist with useful verification. Unknown information is not a recommendation to do nothing.

**AI drafting:** the Pending AI draft view imports a saved bounded model run with raw hashes, source links, competing evidence, gaps and alternatives. It keeps twenty mappings unassigned and creates no approval. An optional `--allow-live-draft` route uses an existing authenticated local Codex CLI for one bounded attempt; its displayed receipt distinguishes a prior saved run, a successful integrated request, a manual draft and an invented fixture. Default operation needs no model access. See [setup, contracts and boundaries](docs/AI_DRAFTING.md). Recommendations remain pending human-review proposals, with no calibrated probability or weighted opportunity score.

## Method, evidence and delivery

- [Rights rubric and version migration](docs/RIGHTS_RUBRIC.md), [intervention method](docs/INTERVENTION_METHOD.md), [source inventory](docs/DATA_SOURCE_INVENTORY.md)
- [Contracts](schemas/README.md), [API](docs/INTERVENTION_API.md), [implementation](docs/TECHNICAL_PLAN.md)
- [Demo](docs/DEMO_SCRIPT.md), [verification actually performed](docs/VERIFICATION.md), [team checkpoint](docs/SPRINT_PLAN.md), [intended use](docs/TOOL_DESCRIPTION.md)

Historical rights assessments retain their original dimension definitions. Old combined counsel/preparation or tribunal assessments are not redistributed into new scores. New dimensions start not assessed. The legacy evidence contract remains score-free.

Real pilot files/captures remain in ignored `outputs/rights_pivot_20261009/research/`; current seed is `rights.pilot.v2.json` with its own resume guide. The earlier source pass is already bounded at twelve additional case-document leads; this continuation reuses it and does not reset collection. Thai dimensions remain insufficient/unassessed pending fuller passage review. New real context/recommendations also belong in ignored local storage. Lucas S reviewed only O03/O04/O05/O10 for C02 as a source-reported sequence; that does not approve any new legal or intervention judgment.

## Verify and package locally

```powershell
python scripts/validate_data.py examples/cases.synthetic.json
python scripts/validate_rights.py reviewdesk/rights.synthetic.json examples/rights-intake.synthetic.json
python scripts/validate_rights.py reviewdesk/rights.synthetic.v2.json examples/rights-intake.synthetic.v2.json
python -m unittest discover -s tests -v
python scripts/rehearse_intervention.py
python scripts/package_submission.py
```

The package uses an explicit file allowlist and synthetic fixtures. It excludes populated research, runtime databases, organizer PDFs, notebooks, correspondence and credentials. [MIT](LICENSE) covers original code/docs/synthetic material only; [third-party notices](THIRD_PARTY_NOTICES.md) preserve other rights. Git ignore does not change Dropbox access.

On the clean fictional starter, open **Synthetic A → Pending AI draft → Save invented pending-draft example** for a provider-free illustration. Saving context and a pending proposal uses the existing deterministic worksheet; it does not record human acceptance or execute an option. Real intake/drafts belong in a new isolated local seed/state and are excluded from the package.

Software tests do not establish legal accuracy, advocate usefulness, effectiveness, probability calibration or national incidence. Published expert conclusions read during preparation are attributed extraction, not independent evaluation labels. Counts describe the selected corpus; reports/cases/defendants/arrest events and candidate clusters remain distinct.

The user authorized updating the existing repository and Pages site with the reviewed code/demo and selected redacted Melayu Raya analysis. Outreach, monitoring, purchase, advocacy execution and final submission remain outside this update. The **6 p.m. ET October 9** departure checkpoint is historical. Today's internal ready target is **2:30 p.m.**, official deadline **3:30 p.m. October 10**, demo **10–15 minutes**. Names, legal approvals and delivery channel remain team decisions.
