# Demonstration planning and existing synthetic walkthrough

**October 9:** the final product is an interface integrating collective-action signals and advocacy strategy. The accepted first real evidence drill concerns notice of charges, opportunities to respond and documented responses; the specific practitioner task and final demo slice remain open. The existing script below rehearses the implemented campaign-comparison baseline; its fictional histories do not select the substantive example. See the [current direction](PROJECT_BRIEF.md), [team start page](TEAM_START_HERE.md) and standalone [fictional signals-to-strategy concept](demo/signals-and-strategy.html).

For a broader demonstration, a proposed ten-minute sequence is: state the advocate's question (1 minute); trace selected observations to excerpts, dates and identity/source limits (2 minutes); inspect one candidate pattern in the external worksheet (2 minutes); challenge it with a shared account, contrary evidence or gap (2 minutes); show a correction and explain the app's stale-analysis warning plus the worksheet's manual recheck (1 minute); show the editable result and next investigation step (2 minutes). Adapt after the material/usefulness trial. This is a proposal, not a completed demonstration. If no candidate is supported, show why it was rejected; do not manufacture a finding.

Disclose exactly what runs: the app's review/comparison is deterministic; the prepared worksheet is external; the optional AI prompt has not been executed. No live extraction, discovery, monitoring or forecasting exists. Retain the synthetic fallback while deciding the final example.

## Existing baseline rehearsal, preserved

Target ten minutes of content within the packet's 10–15-minute allocation; Q&A allocation is unstated. This demonstration follows the user's selected Track 3 example: comparing social-media activity, international attention and human-rights campaigns with reported legal or policy outcomes. Every demonstrated dossier is synthetic. The checks in the submission checklist establish software behavior, not human validation or real-world usefulness.

## Prepare

Lead with an intended decision, such as which claims can responsibly enter a briefing and what evidence to verify next. The broader interface and notice/response evidence drill are settled; the final demo records, period, specific practitioner and operational task remain open. No pair is required. Use the synthetic workflow until separately checked material is ready; do not present feasibility notes as findings. A first batch can use [CSV import](RESEARCH_HANDOFF.md), but importing records is not source verification or synchronized team review.

- Start the local app using the README command and a separate fresh state directory. Keep the frozen Philippines experiment and prior human feedback unchanged.
- Use the three synthetic campaign dossiers in the default fixture. Use the exact titles currently shown by the application; the third provides a draft policy-consultation report and no selected legal-case outcome evidence.
- For live saves, use a name such as `LIVE DEMO PRACTICE — synthetic only`. The offline fallback uses `SCRIPTED DEMO ANALYST — no human validation`; never present its generated records as an actual human review.
- Keep `docs/demo/fallback.html` open in a second browser tab. It opens directly from disk and links to `comparison.synthetic.md` and `comparison.synthetic.json`. Regenerate it with `python scripts/build_demo_fallback.py` if the software or seed changes.
- Keep the local exported comparison ready. It contains selected evidence, categories, dates, gaps, alternative explanations and provenance; no full third-party research corpus is required.

## Run of show

| Time | Show | Say and establish |
| --- | --- | --- |
| 0:00–0:45 | Campaign workspace and synthetic notice | “TrialWatch asks how campaigns and attention relate to legal or policy developments. Our tool helps an analyst compare documented histories without treating timing as proof of impact.” |
| 0:45–1:20 | Three dossier summaries | “These are fictional Philippines examples: different attention patterns, two reported legal outcomes, and a third with a draft consultation but no selected case-outcome evidence. A draft consultation is not an adopted policy. This is a workflow demonstration, not research findings.” |
| 1:20–2:45 | First dossier's evidence and exact excerpts | Show a campaign action, an attention statement and a reported outcome. Distinguish event, publication and retrieval dates. “The source reports this development; the tool does not authenticate a court finding.” |
| 2:45–3:45 | Save selected evidence, then campaign coding | Save Include with a reason and select the supported statements. Code them as social media, international attention, campaign action, legal outcome, policy development or context. “Include selects evidence for analysis; it does not certify truth. These categories are analyst choices. A policy development may be a proposal, decision or implementation stage; inspect the source.” |
| 3:45–4:50 | First saved campaign analysis | Enter the campaign label and objective, a narrow interpretation, alternative explanations and limitations. Save it. “Other legal, institutional or contextual changes could explain an outcome. We preserve these possibilities alongside the comparison.” |
| 4:50–6:00 | Second dossier and save | Repeat evidence selection and coding for the contrasting dossier. Explain the distinction between a reported case development and a policy change. Save the second analysis. Avoid claiming national impact from a single case outcome. |
| 6:00–7:10 | Compare saved dossiers | Show the side-by-side categories and reported outcomes. “These counts are selected coded statements. They are not social reach, engagement, prevalence or a ranking of campaign success.” |
| 7:10–7:50 | Third dossier in the prepared fallback, or live if already saved | Point to incomplete legal-case outcome evidence and the draft consultation. “No selected case-outcome evidence means the case outcome is unknown. The draft consultation is an intermediate policy development, not an adopted policy or a failed campaign.” Disclose when this is the scripted fallback. |
| 7:50–8:45 | Markdown/JSON comparison export | Inspect a citation, excerpt, category, date role, limitation and alternative explanation. Show saved evidence revision and any changed-review warning. “An analysis retains the evidence snapshot it was saved against; later edits cannot silently rewrite it.” |
| 8:45–9:20 | Responsible-use limits | “The app does not fetch posts, estimate reach, monitor cases, contact anyone or infer causal impact. The prior historical triage experiment is separate and does not measure advocacy effectiveness.” |
| 9:20–10:00 | Briefing decision and next verification priority | Show one claim safe to carry forward with attribution and one claim still requiring verification. “An advocacy analyst can trace the claim, see which saved analysis a correction affects, and export the revised memo. This is the benefit we need to test against a spreadsheet; practitioner usefulness has not yet been established.” |

Use the full comparison export if live saves take longer than expected, stating exactly which rows were scripted. If the live app is unavailable, show the static fallback as generated output. Do not narrate static controls as live saves or call an unverified step implemented.

## Short answers for judges

**Why this Track 3 task?** The packet explicitly suggests analyzing social media, international attention and human-rights campaigns alongside policy changes and legal-case outcomes. The product delivers a cited cross-campaign comparison with explicit limits.

**Does it identify what works?** It supports descriptive comparison and questions for further research. It does not estimate campaign effects, rank effectiveness or infer that publicity caused a court or policy outcome. A credible causal study needs a separate design and suitable evidence.

**Why synthetic examples?** They let judges exercise the complete workflow without redistributing third-party source text or suggesting that a convenience sample establishes real campaign performance. The earlier 20-report sample was built for triage and lacks systematic intervention/outcome evidence.

**What does AI do?** The current comparison path uses analyst coding and deterministic software; it makes no fresh model calls. AI assisted preparation and implementation. Earlier saved extraction/audit work remains historical and distinct. The first historical pass had citation-placement/date errors, and the preserved repair passed a bounded AI audit; that history is not a reliability claim for this new task.

**What remains unmeasured?** Analyst usefulness, time savings, coding agreement, coverage and real advocacy impact. Software checks and synthetic examples answer none of those evaluation questions.

**What should a first partner test involve?** A bounded, partner-chosen set of public campaign records; a shared coding guide; independent human coding; explicit handling of missing outcomes and source lineage; and a comparison of review effort and usefulness. No new collection or evaluation is running as part of this local build.
