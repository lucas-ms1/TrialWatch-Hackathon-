# TrialWatch Rights Index — local hackathon prototype

**Start with [TEAM_START_HERE](docs/TEAM_START_HERE.md).** An evidence-backed case index focused exclusively on **fair-trial rights and freedom of expression**, for **Track 3: Advocacy and Impact**. It helps advocates prioritize investigation and compare cases by inspecting per-right concerns, supporting and contrary evidence, uncertainty and exact human-review scope. The legal-analysis workflow overlaps Track 2; no organizer-approved track change or official TrialWatch assessment is claimed.

The October 9 explicit pivot supersedes advocacy strategy, movement detection and advocacy-outcome forecasting as the main build. Related cases, legal analogues, public-source context and possible recurring issues are smaller supporting capabilities. Historical decisions and earlier demonstrations remain in [history](docs/history/README.before-rights-pivot-2026-10-09.md); the frozen experiment and v1/v2 research are preserved.

## Run

Python 3.11+; standard library only. The synthetic demo needs no packages, account, credentials, paid service, model calls or internet.

```powershell
cd "C:\Users\freew\Dropbox\School\TrialWatch Hackathon"
python -m reviewdesk --port 8768 --state-dir data/processed/rightsdesk-v1
```

Open [http://127.0.0.1:8768/rights.html](http://127.0.0.1:8768/rights.html). Keep the terminal running; Ctrl+C stops it. SQLite state persists locally. For a fresh rehearsal use another `--state-dir`. A different seed requires a fresh state directory. The new default seed is fictional and separate from historical research. Every teammate has separate local review state.

The preserved comparison interface remains at `/index.html`. To reopen the earlier comparison default, explicitly pass `--seed reviewdesk/demo.synthetic.json --state-dir data/processed/campaigndesk --port 8767`. Reopen the real v2 state only with its original seed and exact original directory; do not substitute the pivot seed.

## Complete walkthrough

1. **Intake:** enter a source URL, supplied UTF-8 text, exact supporting excerpt and attributed proposition, or import the supported structured JSON example. The app accepts supplied material; it does not fetch a URL or parse binary PDFs. Convert a permitted document to text externally before intake. Excerpt-presence validation checks the supplied text, not source authenticity.
2. **Assessment:** open a case profile. Inspect source cards, original wording, dates, locators, language/translation and source dependence. Select the relevant rights dimension and supporting/contrary observations, applicability, anchored rule, rationale, confidence/completeness, missing facts and next check. Save a provisional assessment. Numeric values are deterministic consequences of explicitly chosen rules; they are not legal inference from uploaded text.
3. **Human review:** enter the actual reviewer name, exact dimensions and reason, then approve or request changes. Review scope carries the supporting/contrary claim IDs. This is a dimension-specific judgment, not whole-case authentication. Synthetic rehearsal names denote software demonstrations only.
4. **Index:** return to search/filter profiles and inspect separate fair-trial/expression scores, assessed coverage, review state and stale evidence. Related-case/context suggestions explain similarities, material differences and investigative limits. Counts describe only the selected corpus.
5. **Export:** download cited Markdown or JSON. Scores/state, legal standards, cited excerpts, counter-evidence, gaps, rubric/evidence versions and review scope travel with the export. Correct an observation with a reason: old snapshots/history remain, and saved assessments become stale. Reassess and review the new revision explicitly.

The concern scale is 0–3 with explicit anchors. `insufficient_evidence`, `not_assessed` and `not_applicable` have no numeric value. Zero needs affirmative safeguard evidence. Confidence and completeness are separate; duplicated articles and country context do not automatically change any score. There is no combined percentage, causal estimate or calibrated probability. See [rubric and legal applicability](docs/RIGHTS_RUBRIC.md).

**AI boundary:** AI assisted implementation and local research preparation. No usable extraction model runtime is integrated into this application. Fresh extraction, automatic fact-to-right mapping, source discovery and monitoring are not running. The working route is structured import/manual evidence mapping plus deterministic scoring, followed by named-human review. Prepared examples are not live inference.

## Data, contract and source route

- [Versioned rubric](docs/RIGHTS_RUBRIC.md), [source inventory](docs/DATA_SOURCE_INVENTORY.md), [technical implementation](docs/TECHNICAL_PLAN.md)
- [New rights contract](schemas/README.md), synthetic rights fixtures and structured import; legacy `cases.schema.json` still excludes numerical scores
- [Team checkpoint and tomorrow](docs/SPRINT_PLAN.md), [demo script](docs/DEMO_SCRIPT.md), [verification](docs/VERIFICATION.md)
- [Intended use](docs/TOOL_DESCRIPTION.md), [event requirements](docs/EVENT_BRIEF.md), [submission checklist](docs/SUBMISSION_CHECKLIST.md)

The current real pilot `research/rights.pilot.v2.json` and its `PIVOT_PILOT_README.v2.md` resume guide, plus search/access ledger, live only in ignored `outputs/rights_pivot_20261009/`; original source captures and populated notes are local. They are a selected evidence drill, not an effectiveness/forecasting dataset or independent legal-accuracy evaluation. Public expert conclusions/grades remain attributed separately from prototype scores. The previous v2 batch retains 20 observations/three histories/eight sources. Lucas S reviewed **only O03/O04/O05/O10 for C02**, accepting a source-reported sequence. That review is not a rights assessment, original-order authentication or proof of advocacy impact; it does not transfer into approval in the new pivot state.

## Verify and package locally

```powershell
python scripts/validate_data.py examples/cases.synthetic.json
python scripts/validate_rights.py reviewdesk/rights.synthetic.json examples/rights-intake.synthetic.json
python -m unittest discover -s tests -v
python scripts/package_submission.py
```

The explicit package allowlist includes original code/docs, blank templates and synthetic examples. The script checks synthetic data, archive contents and hashes and writes under ignored `outputs/submission/`. It does not publish or submit. No raw research, runtime database, organizer PDF, notebook bundle or private correspondence belongs in the package. Tests establish software behavior; they do not establish legal correctness, calibration, representativeness or advocacy usefulness. See the receipt for checks actually run.

[MIT](LICENSE) covers original code/docs/synthetic fixtures only. [Third-party notices](THIRD_PARTY_NOTICES.md) preserve other rights. Country-year context needs source, year, methodology and license; it is never an automatic input to case scores. Missing evidence is unknown, chronology is not causation, and reports/cases/people/arrest events are distinct units.

This run prepares local reviewable changes only: no push, publication, messages, purchase, monitoring or final submission. The official deadline is **October 10 at 3:30 p.m. ET**, with a **10–15-minute demo**. Internal checkpoints are team targets. Final delivery channel and team lead/details remain to be confirmed.
