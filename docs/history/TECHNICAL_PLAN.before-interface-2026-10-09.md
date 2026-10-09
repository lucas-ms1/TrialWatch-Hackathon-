> Historical document: superseded for active scope by the latest entries in [DECISIONS.md](../DECISIONS.md). Original prose retained; relative links adjusted for this archive folder.

# Implementation notes: advocacy comparisons and outcome estimates

October 9, 2026. The intended product now includes finding similar cases and movements, comparing advocacy approaches across contexts and jurisdictions, examining actors and moments of engagement, and estimating likely advocacy outcomes. A secondary task is identifying publicly documented collective action before or while it occurs. These are product objectives; the running application remains a manual, deterministic comparison prototype. This update adds no predictor, collection, monitoring, model/API calls or dependencies.

## Available, prepared and proposed

| Component | Available or prepared now | Proposed extension |
| --- | --- | --- |
| Evidence intake | Manual text/URL intake; 30-field CSV bridge groups reports under explicit dossier IDs | Additional strategy metadata and validated source/event relationships |
| Review and provenance | Excerpts, attribution, date roles, language/translation notes, originals and correction history | Human adjudication of new evidence and comparable case/movement units |
| Connections | Manual duplicate links; supplied event IDs and source-lineage notes survive import | Reviewed identity/event matches and reasoned analogue suggestions |
| Comparison | Multiple saved dossier analyses, six manual observation roles, dated/undated timelines, Markdown/JSON exports | Context-specific tactic/outcome tables with inclusion rules, denominators and missingness |
| Candidate review | External blank pattern worksheet and proposal prompt; local worked notice-of-charges example | Saved candidate, analogue and strategy-review objects with supporting and challenging evidence |
| Revisions | Saved app analyses snapshot evidence; later review revisions flag stale analyses | Automatic dependency tracking for new objects; external worksheets currently require manual checks |
| Outcome estimation | No implemented or validated forecast | Conditional forecasts with explicit outcome, horizon, uncertainty and abstention |
| Collective action | Manual examination of supplied evidence only | Separate review of public announcements, reports of action underway and forecasts; no active monitoring |

Implementation locations: `reviewdesk/server.py` (`evidence_export`, `campaign`, `campaign_export`, `advocacy`), `reviewdesk/static/app.js` and `scripts/build_research_seed.py`. A dossier is an analyst grouping, not a verified unique case or movement. Event IDs and distinct URLs do not establish deduplicated counts or source independence. The legacy case validator and runtime dossier format are separate structures.

The local notice-of-charges checkpoint contains nine AI-prepared observations across three provisional histories. It remains human-review-pending and is useful for inspecting evidence and testing connections. It is not a comparative-effectiveness dataset or a basis for numerical outcome estimates. The frozen historical triage experiment remains unchanged and supplies no forecasting or advocacy-impact validation.

## Intended analysis stages

1. **Retrieve analogues.** Match reviewed context and objective features, then show why each case or movement is similar, which consequential features differ and which are unknown. Distinguish a case, campaign, movement, report and event. Similarity is a reason to investigate transferability, not proof that an approach will work elsewhere. Cross-jurisdiction comparisons must expose differences in institutions, legal process, civic space, resources and stage of proceedings.
2. **Compare observed advocacy and outcomes.** Define the comparison unit, eligible population, observation window, outcome and follow-up before summarizing tactics. Display documented successes, setbacks, unresolved histories and missing evidence. Separate planned action, completed action and reported outcome. Counts of reports cannot become outcome denominators, reach or effectiveness scores. A table may describe associations within a stated sample; it cannot automatically rank the most effective tactic.
3. **Assess contribution and timing.** Map organization/institution roles, engagement dates, procedural decision points and evidence of a plausible response mechanism. Record contrary evidence, pre-existing trends, simultaneous tactics, legal developments and alternative explanations. A human may judge a contribution hypothesis stronger or weaker; an assertion that a particular actor or moment caused the greatest impact requires a defensible comparison and causal design. Chronology alone is insufficient.
4. **Estimate likely outcomes conditionally.** Specify an outcome, time horizon, information cutoff, target context and an explicit advocacy scenario. Report what comparable histories can and cannot support, with uncertainty and sensitivity to differences. The probability of an outcome given an observed approach is not the causal benefit of choosing that approach. If comparable data, follow-up or evaluation are insufficient, abstain from a numerical estimate and return evidence gaps and conditional scenarios, not invented confidence percentages.
5. **Review collective-action signals separately.** Label direct public evidence of an announced/planned action, source-attributed reports of action underway, and a forecast of future action as different record types. An announcement does not prove an event occurred; an underway report needs an event date and an as-of date and does not establish present status indefinitely. Keep scope at public organization/event level, without individual private tracking. Future signal detection would need a defined coverage frame and separate validation before any monitoring implementation or authorization.

## Minimum information for a manual strategy review

Keep these comparison fields in a versioned worksheet beside existing evidence exports initially. Do not silently append them to the existing CSV contract or claim they are app fields. A schema/importer change needs validation and relevant README tests before use.

| Field group | Minimum content |
| --- | --- |
| Units and selection | Stable case/campaign/movement/event IDs; grouping and identity uncertainty; inclusion/exclusion rules; sampling frame and selection rationale; eligible comparison denominator |
| Source and revision | Observation ID, exact excerpt, source URL/identifier, publisher, original language/translation status, publication and retrieval times, evidence revision, source lineage/dependence and access limits |
| Context and similarity | Jurisdiction, institutions, affected groups, procedural stage, legal provisions, civic-space constraints and known resources; matching features, material differences, unknowns and transferability rationale |
| Advocacy episode | Objective, tactic or combination, public organization/actor role, target institution, planned/completed status, start/end or unknown dates, engagement relative to decision points and available evidence of scale |
| Outcome and follow-up | Precisely defined legal/policy/public-response outcome; observed status including setback/unresolved/unknown; outcome event date; follow-up window and completeness; distinction between source allegation, reported finding and analyst judgment |
| Comparison and contribution | Comparable units with/without the tactic where defensible; support and challenges; concurrent interventions, alternative explanations, outcome ascertainment differences and missingness |
| Estimate or signal | Information cutoff, target outcome and horizon, advocacy scenario, comparability assumptions, basis/uncertainty, abstention reason; for collective action, announced/underway/forecast classification and source/date basis |
| Human decision | AI-prepared versus human-reviewed status, named reviewer when actually supplied, accepted/revised/rejected disposition, verification action, review date and saved evidence versions |

Outcomes need their own evidence; a campaign's stated objective is not an observed success. Unknown follow-up cannot be treated as failure or silently dropped. Multiple reports of a single episode must not increase its weight. Evidence of a nationwide policy change and an individual case development should remain separate outcome definitions.

## Smallest next implementation after a useful manual trial

Reuse the [pattern-review worksheet](../PATTERN_REVIEW_WORKSHEET.md) and [proposal prompt](../PATTERN_PROPOSAL_PROMPT.md) for the evidence drill, extending a working copy with the strategy fields above. Carry observation IDs, citations and evidence versions into every interpretation; manually revisit affected conclusions after corrections. This can expose which comparison fields and output are useful before database changes.

The recommended first software extension is a saved candidate/analogue review object that references selected claims and their snapshots. Store support/challenge/context roles, similarity and differences, source/identity uncertainty, analyst interpretation, human disposition and next verification action. Flag affected objects when evidence changes or is excluded. Tactic/outcome tables and conditional forecast records can follow only once the corresponding data and review contract are defined. These are proposals, not implemented features or official milestones; the final audience, output and owners remain open.

## Evaluation before forecast claims

An existing model may be tested as a proposal assistant using permitted excerpts and checked examples. Separate extraction, matching, source-dependence checks, analogy and interpretation; require exact evidence IDs and human review of each proposal. Include repeated reports, uncertain identity, contrary evidence, missing dates and tempting causal claims. Freeze proposals before independent checking and retain errors. A small demonstration does not establish general accuracy. Provider choice, paid/API execution and training remain undecided; none occurs through these preparation documents.

A forecast evaluation must define the target outcome and horizon, reconstruct only information available at each prediction cutoff and preserve predictions before outcomes are revealed. Use prospective or strictly time-held-out evaluation; prevent leakage through later source text, retrospective outcome summaries, related reports, repeated cases and model selection on the test period. Evaluate transfer across jurisdictions separately rather than assuming it. Document any residual historical-knowledge leakage when a general model already knows case outcomes.

Compare against simple, stated baselines such as an eligible historical outcome rate or a rule using procedural stage. Assess calibration and a proper probability score, interval uncertainty, missing/censored outcomes, abstention coverage and performance by relevant context. A small, selected denominator or unstable follow-up may make even these estimates uninterpretable; abstain and collect better evidence. Future collective-action forecasts also need false-alert and missed-event measures, lead time and an explicit event definition. None of these results exists yet.

Separately, test whether an intended advocate can understand the evidence, reject a poor analogue and choose a concrete next investigation or engagement step. User usefulness, software correctness, predictive calibration and causal impact are distinct evaluations. No test or worksheet should collapse them into a claim of advocacy effectiveness.
