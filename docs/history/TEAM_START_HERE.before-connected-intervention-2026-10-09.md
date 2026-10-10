# Team start here

The latest product is **TrialWatch Rights Index**, focused only on fair-trial rights and expression. Track 3 remains selected: make evidence usable for advocacy prioritization and comparison. Legal analysis overlaps Track 2; this is not an official TrialWatch assessment or approved track change.

```powershell
python -m reviewdesk --port 8768 --state-dir data/processed/rightsdesk-v1
```

Open `http://127.0.0.1:8768/rights.html`. Python 3.11+; no install, keys or model service. Synthetic default is shareable; each machine stores its own SQLite review state. A fresh rehearsal needs a fresh state directory. Keep earlier real seeds/state paired; no automatic review transfer.

Read [README](../README.md), [rubric](RIGHTS_RUBRIC.md), [demo script](DEMO_SCRIPT.md), [checkpoint](SPRINT_PLAN.md) and [verification](VERIFICATION.md). Walk through intake → cited dimension draft → scoped human review → index → export → correction/stale warning. A teammate should trace at least one support and contrary passage and explain why missing evidence is unscored.

The running application does not make fresh AI extraction calls. Mapping and rule selection are explicit/manual, scoring deterministic. Prior AI research is prepared material; human approval requires an actual named reviewer and reason. Published expert grades remain separately attributed. No combined percentage or probability exists.

Assign builder/checker, legal evidence reviewer and presenter/lead roles; names are still open. Tomorrow: qualified applicability/rubric review, one advocate-style usefulness walkthrough, bounded evidence corrections, final 10–15-minute rehearsal and allowlisted package. Internal ready target 2:30 p.m. ET; official submission October 10 3:30 p.m. ET.

Do not share raw research, runtime databases, PDFs, private correspondence or notebook bundles by default. This run has no push/publication/submission/outreach authorization. The legacy comparison interface and historical plans remain available, with their earlier scope preserved.
