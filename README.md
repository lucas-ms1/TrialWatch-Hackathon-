# TrialWatch Philippines: Campaign Evidence Comparison

Compare documented social-media activity, international attention and human-rights campaign actions with reported legal and policy developments. Built for **Track 3: Advocacy and Impact**, October 9–10, 2026, with an initial Philippines focus.

An advocacy analyst reviews evidence, classifies observations, compares campaign timelines and exports a cited comparison memo. The memo distinguishes reported outcomes, unknowns, analyst interpretations and alternative explanations. It supports asking better questions about campaigns; it does not rank effectiveness or infer that a campaign caused an outcome.

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

For a ready-to-read preview, open `docs/demo/fallback.html` directly in a browser. Each teammate's live review state stays on their own computer; GitHub shares the code and synthetic examples, not a shared review database. The next group decision is to agree on one comparison question and two campaign histories; see [the group work plan](docs/SPRINT_PLAN.md).

## Complete comparison workflow

1. Open a dossier from **Compare campaigns**. In **Evidence**, inspect passages, source links and event/publication dates. Unknown event dates remain undated. Select statements, optionally save supported corrections, then save an Include review under a demonstration reviewer name. Originals and history remain available.
2. In **Analysis**, classify each selected observation as social media, international attention, campaign action, legal outcome, policy outcome or context. Enter analyst name, campaign label, objective, interpretation, alternative explanations and limitations. Save the analysis. Fictional example text/coding, when loaded, still requires an explicit save.
3. Repeat for a second dossier. Return to **Compare campaigns** to contrast recorded activity, reported outcomes, timelines and gaps. Counts refer to coded observations or cited sources, never audience reach, campaign size, cases in a population or effectiveness.
4. Download the comparison as **editable Markdown or JSON**. Saved analyses retain their evidence snapshots. A later evidence correction flags an analysis as stale instead of silently rewriting it. Review and resave the analysis to refresh its evidence.

Missing evidence means unknown, not that no attention, action or outcome occurred. A case outcome is distinct from national policy impact; a draft consultation is not enacted reform. The export retains those limits alongside citations and excerpts.

**Add a report** supports manual URL/text intake with an attributed summary and exact excerpt. It does not fetch or extract. Duplicate links retain records separately. The current intake creates a separate dossier; assembling a richer real campaign requires an adapted seed. The prototype does not harvest social platforms or provide an automated campaign-discovery pipeline.

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
