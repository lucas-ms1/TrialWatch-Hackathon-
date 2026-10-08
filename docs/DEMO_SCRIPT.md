# Ten-minute demonstration: campaign and case-outcome comparison

Target ten minutes of content within the packet's 10–15-minute allocation; Q&A allocation is unstated. This demonstration follows the user's selected Track 3 example: comparing social-media activity, international attention and human-rights campaigns with reported legal or policy outcomes. Every demonstrated dossier is synthetic. The checks in the submission checklist establish software behavior, not human validation or real-world usefulness.

## Prepare

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
| 9:20–10:00 | Adoption question and concrete next step | “A partner could choose a defined set of campaigns, review a common coding guide, and check whether this comparison helps identify evidence gaps and useful follow-up questions. That evaluation has not run.” |

Use the full comparison export if live saves take longer than expected, stating exactly which rows were scripted. If the live app is unavailable, show the static fallback as generated output. Do not narrate static controls as live saves or call an unverified step implemented.

## Short answers for judges

**Why this Track 3 task?** The packet explicitly suggests analyzing social media, international attention and human-rights campaigns alongside policy changes and legal-case outcomes. The product delivers a cited cross-campaign comparison with explicit limits.

**Does it identify what works?** It supports descriptive comparison and questions for further research. It does not estimate campaign effects, rank effectiveness or infer that publicity caused a court or policy outcome. A credible causal study needs a separate design and suitable evidence.

**Why synthetic examples?** They let judges exercise the complete workflow without redistributing third-party source text or suggesting that a convenience sample establishes real campaign performance. The earlier 20-report sample was built for triage and lacks systematic intervention/outcome evidence.

**What does AI do?** The current comparison path uses analyst coding and deterministic software; it makes no fresh model calls. AI assisted preparation and implementation. Earlier saved extraction/audit work remains historical and distinct. The first historical pass had citation-placement/date errors, and the preserved repair passed a bounded AI audit; that history is not a reliability claim for this new task.

**What remains unmeasured?** Analyst usefulness, time savings, coding agreement, coverage and real advocacy impact. Software checks and synthetic examples answer none of those evaluation questions.

**What should a first partner test involve?** A bounded, partner-chosen set of public campaign records; a shared coding guide; independent human coding; explicit handling of missing outcomes and source lineage; and a comparison of review effort and usefulness. No new collection or evaluation is running as part of this local build.
