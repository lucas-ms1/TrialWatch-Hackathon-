# TrialWatch: Advocacy Strategy and Collective Action

**Groupmates: start with [TEAM_START_HERE](docs/TEAM_START_HERE.md)** for setup, the working app, the clickable concept, current decisions and work to assign.

An intended interface connecting advocacy strategy with evidence of collective action and emerging case clusters. Help advocates find comparable cases and movements, compare approaches across contexts and jurisdictions, investigate actors and moments associated with outcomes, and estimate likely advocacy outcomes with explicit uncertainty. Public news, NGO/civil-society reporting and permitted public social-media material would help surface documented plans, activity underway and signals worth investigating. Initially focused on the Philippines, for **Track 3: Advocacy and Impact**, October 9–10, 2026.

**Latest product direction:** collective-action signals and advocacy strategy form one connected workflow. For example, several reports of protest-related arrests in a similar area could prompt review of a candidate case cluster, inspection of public reporting and collective-action evidence, comparison with earlier advocacy responses, and selection of a next step that supports case advocacy, issue visibility and community agency. Reports, cases and arrest events must be distinguished; shared geography alone does not establish a coordinated movement. Similarity, observed outcomes, evidence of advocacy contribution and conditional forecasts are separate outputs. The current sample supports an evidence walkthrough; it does not establish which tactic works best, a causal effect or a reliable outcome estimate. See the [updated project brief](docs/PROJECT_BRIEF.md) and [technical scope](docs/TECHNICAL_PLAN.md) for proposed capabilities versus the implemented baseline. No monitoring has been started.

**October 9 mentorship checkpoint:** the accepted first exploratory question is: **What do the records say about notice of charges and opportunities to respond in proceedings involving human-rights defenders, and what legal or public responses followed?** This tests the broader idea; it does not restrict the product to notice of charges. The final product format is an interface; the three initial histories, specific practitioner, first operational task and forecast outcome/horizon remain provisional. A small AI-prepared real sample and mentor pack are local, ignored research artifacts; the shared default stays synthetic. See [current decisions](docs/DECISIONS.md). The [team plan](docs/SPRINT_PLAN.md), [material inventory](docs/MATERIALS_AND_DEMO_OPTIONS.md) and [project brief](docs/PROJECT_BRIEF.md) retain earlier preparation; statements that no exploratory question is agreed are superseded. Possible-pattern review, change detection and forecasting are different tasks; no forecasting ability is established.

**Implemented baseline:** the local app is still Campaign Evidence Comparison. An analyst reviews evidence, codes observations, compares several campaign timelines and exports a cited editable memo with unknowns and alternative explanations. It is manual and deterministic: no AI extraction, pattern discovery or live monitoring. A [blank pattern worksheet](docs/PATTERN_REVIEW_WORKSHEET.md) and [optional model prompt](docs/PATTERN_PROPOSAL_PROMPT.md) prepare the broader workflow outside the app. See [technical notes](docs/TECHNICAL_PLAN.md) for reuse and gaps.

**Primary data route:** build a small structured evidence collection from permitted public documents. The local v2 batch now has 20 observations across three provisional histories/eight sources. One limited human review covers four observations/C02, with saved review and analysis revision 1; the remaining observations/proposals are outside that review. C02 is accepted as a source-reported sequence, without original-order authentication or an advocacy-effect claim. The team does not depend on a TrialWatch database. Case facts, actions, outcomes and collective-action signals each need supporting evidence. Populated research and exported real memos remain local. See [current checkpoint and remaining work](docs/SPRINT_PLAN.md).

## Run locally

Python 3.11 or newer. No packages, API keys, accounts, internet or model calls are needed for the synthetic demo.

To get the code from GitHub:

```powershell
git clone https://github.com/lucas-ms1/TrialWatch-Hackathon-.git
cd TrialWatch-Hackathon-
```

Then start the app:

```powershell
python -m reviewdesk --port 8767
```

Open `http://127.0.0.1:8767`. Keep the terminal running; Ctrl+C stops it. Port 8767 avoids earlier rehearsal servers on 8765/8766. State persists in `data/processed/campaigndesk/` using SQLite. Use `--state-dir data/processed/my-rehearsal` for a fresh rehearsal. A changed seed requires a separate state directory.

The default contains **three fictional campaign dossiers and 14 source-attributed observations**: a reported dismissal following documented attention; a reported conviction with incomplete attention evidence; and a draft policy consultation with an unknown individual case outcome. These are software fixtures, not real cases, human validation or measured results.

For a ready-to-read preview, open `docs/demo/fallback.html` directly in a browser. Each teammate's live review state stays on their own computer; GitHub shares the code and synthetic examples, not a shared review database. Inspect usable material before choosing one small pattern question and an advocacy task; no fixed pair is required. The existing fixtures demonstrate software mechanics and do not select the team's first substantive example.

To explore the intended connected flow, open [docs/demo/signals-and-strategy.html](docs/demo/signals-and-strategy.html) in a local browser after cloning or downloading the repository. It is a self-contained fictional concept: cluster review, public responses and strategy options. It needs no server or account and has no collection, model inference, forecasting or saved review integration. GitHub's file view shows its source; download it to interact.

## Complete comparison workflow

1. Open a dossier from **Compare campaigns**. In **Evidence**, inspect passages, source links and event/publication dates. Unknown event dates remain undated. Select statements, optionally save supported corrections, then save an Include review under a demonstration reviewer name. Originals and history remain available.
2. In **Analysis**, classify each selected observation as social media, international attention, campaign action, legal outcome, policy outcome or context. Enter analyst name, campaign label, objective, interpretation, alternative explanations and limitations. Save the analysis. Fictional example text/coding, when loaded, still requires an explicit save.
3. Repeat for the other dossiers you want to inspect. Return to **Compare campaigns** to contrast recorded activity, reported outcomes, timelines and gaps. Counts refer to coded observations or cited sources, never audience reach, campaign size, cases in a population or effectiveness. The app is not limited to two dossiers.
4. Download the comparison as **editable Markdown or JSON**. Saved analyses retain their evidence snapshots. A later evidence correction flags an analysis as stale instead of silently rewriting it. Review and resave the analysis to refresh its evidence.

Missing evidence means unknown, not that no attention, action or outcome occurred. A case outcome is distinct from national policy impact; a draft consultation is not enacted reform. The export retains those limits alongside citations and excerpts.

**Add a report** supports manual URL/text intake with an attributed summary and exact excerpt. It does not fetch or extract. Duplicate links retain records separately. Intake still creates a separate dossier. To assemble several reports into one campaign dossier, use the [empty CSV template and batch importer](docs/RESEARCH_HANDOFF.md); no hand-editing of a JSON seed is required. Imported evidence still needs explicit app review and classification. New seed versions need separate state directories; reviews are not synchronized or migrated automatically. The prototype does not harvest social platforms or provide an automated campaign-discovery pipeline.

## Demo, method and submission

- [Ten-minute demo script](docs/DEMO_SCRIPT.md)
- [Offline fallback](docs/demo/fallback.html), [sample comparison Markdown](docs/demo/comparison.synthetic.md), [sample JSON](docs/demo/comparison.synthetic.json)
- [Analysis method and limits](docs/ANALYSIS_METHOD.md)
- [Short intended-use description](docs/TOOL_DESCRIPTION.md)
- [Product choice and rubric](docs/PROJECT_BRIEF.md)
- [Verification record](docs/VERIFICATION.md), [submission checklist](docs/SUBMISSION_CHECKLIST.md), [packet requirements](docs/EVENT_BRIEF.md)

Open the self-contained fallback directly in a browser without Python or internet. It is generated through the real backend using scripted synthetic reviews and coding; these are not human validation. Rebuild it with `python scripts/build_demo_fallback.py`.

```powershell
python scripts/validate_data.py examples/cases.synthetic.json
python -m unittest discover -s tests -v
python scripts/package_submission.py
```

The package script uses an explicit allowlist, validates synthetic data and verifies archive hashes. It writes a ZIP under `outputs/submission/`; it does not publish or submit. Required assets: repository or equivalent link, code/documentation/setup instructions, open-source license and short intended-use description. Final deadline: **October 10, 2026, 3:30 p.m. ET**. Demo: **10–15 minutes**. The team must still provide a judge-accessible link and perform external submission after separate authorization.

## Preserved research and AI role

The frozen run and reader edition remain under `outputs/philippines_pilot/20261006T160133Z/` in the original local research workspace. They and the source-specific historical adapters are excluded from this repository and package. The shared code does not require them. Those case histories are not complete campaign datasets; current status and several evidence questions remain unverified.

The prior experiment covered **20 reports from four publishers around three selected histories**. Against provisional AI references, AI triage retained 13/13 relevant reports and queued 0/6 definite negatives; the keyword baseline retained 11/13 and queued 1/6. AI also queued one uncertain reference item. The first pass failed citation-placement/date checks; one preserved same-corpus repair passed a bounded AI audit. These are not human-ground-truth accuracy or advocacy-effectiveness measurements. Exact human feedback, predictions and metrics remain unchanged.

Current classification and interpretation are manual. AI helped with earlier extraction and implementation; the demo makes no fresh model calls. The earlier briefing/follow-up backend remains compatible but is not the primary campaign-comparison demonstration.

## Data and license

[MIT](LICENSE) covers original code/docs and synthetic fixtures. [Third-party notices](THIRD_PARTY_NOTICES.md) preserve source rights. Full captures, private correspondence, historical outputs, runtime databases, organizer PDFs and the corpus-bearing notebook are excluded. Git ignore rules do not change Dropbox permissions or encrypt files. Do not enter confidential monitoring material.

Own prework is assumed permitted at the user's direction. Track 3 supersedes the earlier Track 1 build. No organizer endorsement, operational adoption, real-world usefulness, causal effect or national impact is claimed. The app is local only and is not a secure multi-user service. No outreach, monitoring or automated collection runs.
