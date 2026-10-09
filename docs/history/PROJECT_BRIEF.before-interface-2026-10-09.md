> Historical document: superseded for active scope by the latest entries in [DECISIONS.md](../DECISIONS.md). Original prose retained; relative links adjusted for this archive folder.

# Track 3: advocacy comparison and outcome estimation

October 9, 2026. The intended product helps advocates find useful analogues across cases and movements, compare advocacy approaches in different contexts and jurisdictions, investigate which actors and moments may have contributed to outcomes, and estimate likely advocacy outcomes when evidence supports doing so. Identifying collective action before or during its occurrence is a secondary intended capability. Start with the Philippines; transfer to other jurisdictions must expose differences that affect the comparison.

This direction extends the earlier pattern-review and campaign-comparison work. The [previous brief](PROJECT_BRIEF.before-strategy-2026-10-09.md) and [October 7–8 brief](PROJECT_BRIEF.2026-10-08.md) remain historical records. The broad audience is advocates; a named intended user, final workflow, output format and owners remain unagreed.

## What an advocate should be able to investigate

1. **Find analogues.** Retrieve cases or movements with relevant similarities in objectives, affected groups, institutions, legal setting, procedural stage, available tactics and constraints. Show the material differences and uncertain identity links. A similar history offers a comparison, not an interchangeable proxy for another population or jurisdiction.
2. **Compare advocacy approaches.** Connect each documented tactic to its objective, actors, target institution, timing, context and reported outcomes. Preserve unsuccessful approaches, unknown outcomes, contradictory accounts and source dependence. The intended question is which approaches appear most effective in which contexts; the current evidence does not answer it.
3. **Investigate actors and moments.** Trace who engaged whom and when, alongside procedural developments and public responses. Assess evidence for a contribution and competing explanations before treating an actor or moment as having the greatest impact. An event occurring after engagement establishes sequence, not causation.
4. **Estimate likely outcomes.** Use suitable comparable histories to make a bounded, revisable estimate about a defined future outcome. Show assumptions, evidence gaps, transfer limits and uncertainty; return “insufficient evidence” when an estimate is unsupported.
5. **Identify collective action.** Separately label a source's announced or planned action, evidence that action is underway or completed, and an analyst's forecast of an unannounced action. A public announcement can identify activity before it occurs without being a prediction. No live monitoring or collection has been authorized or started.

An evidence table, timeline or cited editable brief may support these tasks. The format should help an advocate compare options, challenge a conclusion and choose the next evidence check. Counts of observations or sources do not measure reach, incidence, effectiveness or impact.

## Requirements for a credible outcome estimate

Each proposed estimate must declare the outcome, time window, starting situation and advocacy approach under consideration; the comparison histories and why they transfer; the evidence cutoff; assumptions and alternative explanations; and uncertainty. Legal developments, policy changes, public attention and movement activity are distinct outcomes. Source-reported developments must remain distinct from analyst judgments about their causes.

Describing outcomes after an approach, estimating what might happen next and estimating an approach's causal contribution are different claims. Effectiveness comparisons must address differences such as case selection, institutional context, concurrent legal work, other campaigns, resources, documentation coverage and outcome windows. Unknown or unreported outcomes cannot be coded as failures or successes.

Before presenting numerical likelihoods as reliable, define and evaluate a forecasting method on later outcomes withheld from the method, compare it with a simple baseline and inspect calibration and errors. Until evidence supports an estimate, the product should explain what is missing. The current nine-observation sample cannot justify percentages, a ranking of tactics or a claim about greatest impact. These are intended capabilities, not validated model outputs.

## First concrete example, already accepted

**What do the records say about notice of charges and opportunities to respond in proceedings involving human-rights defenders, and what legal or public responses followed?** Keep this as the first worked example of the broader product.

The local mentor sample contains **nine AI-prepared observations across three provisional histories—Cordillera/Ilocos defenders, Sally Ujano and CERNET—from four public PDFs**. All remain human-review-pending. The local evidence reader, candidate review and walkthrough demonstrate a traceable evidence chain and its gaps. They are not a dataset measuring advocacy effectiveness, a validated matching system or a forecasting evaluation. The histories remain provisional; no current case status is inferred from historical material.

The next useful demonstration would show an advocate the evidence for one comparison, its strongest limitation and the evidence needed to assess a possible response or outcome. Keep source allegations, reported court findings, analyst interpretation and proposed advocacy separate. Practitioner usefulness and real-world impact remain unmeasured.

## What exists today

The local Python/SQLite application is **manual and deterministic**. Analysts can inspect attributed passages, make corrections, save reviews, classify observations, compare several campaign timelines and export editable Markdown/JSON. Saved analyses retain evidence snapshots; later evidence changes flag them for re-review. Duplicate links and unknowns remain visible.

The [pattern worksheet](../PATTERN_REVIEW_WORKSHEET.md) and [proposal prompt](../PATTERN_PROPOSAL_PROMPT.md) support preparation outside the app. Automatic analogy retrieval, effectiveness estimation, actor-impact attribution, forecasting and collective-action detection are not implemented. Worksheets need manual evidence rechecking. The default demonstration uses three fictional dossiers; local historical evidence and runtime state remain excluded from the synthetic public package.

## Hackathon fit and next decision

The [packet and orientation](../EVENT_BRIEF.md) permit a working prototype, demo or documented proof of concept. The rubric is Innovation 25, Feasibility 25, Human Rights Impact 30 and Ethical Rigor & Responsible AI 20. The proposed contribution is an inspectable path from comparable histories through evidence and uncertainty to a human strategy question. The broader ambition does not add official submission requirements.

Use mentorship to choose the advocate's concrete decision, one outcome and time window, and the minimum comparison evidence needed. Keep the accepted example ready while those choices are made. Work remains local preparation: no publication, submission, outreach, spending or monitoring is authorized.

See [current decisions](../DECISIONS.md), [technical notes](../TECHNICAL_PLAN.md) and the [short intended-use description](../TOOL_DESCRIPTION.md).
