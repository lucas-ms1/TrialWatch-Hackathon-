# Current project decisions

Updated October 7, 2026. The user's definitive direction is **Track 3: Advocacy and Impact**, specifically **compare campaigns and case outcomes**, inspired by the packet example relating social media, international attention and human-rights campaigns to policy/legal outcomes. This supersedes both the older Track 1 build and the initial briefing-first proposal. Own prework is assumed permitted; do not reopen it.

| Decision | Choice | Reason |
| --- | --- | --- |
| Product | Campaign Evidence Comparison | Directly supports the user's selected Track 3 example |
| User/output | Advocacy analyst / cited comparison memo | Make documented activity, outcomes, gaps and interpretations inspectable |
| Scope | Descriptive evidence comparison | Existing data cannot support causal effectiveness estimates or campaign ranking |
| Geography | Philippines | Preserve the user's focus |
| Default data | Three synthetic campaign dossiers / 14 observations | Demonstrates contrasting sequences without inventing real evidence |
| Coding | Analyst assigns a primary role to each selected statement | Source claims and interpretations remain separate |
| Outcomes | Source-attributed legal/policy developments | Missing outcome is unknown; draft reform is not enacted change |
| Dates | Event dates separate from publication and recording timestamps | Unknown event dates are never replaced by publication dates |
| Revisions | Append-only review/analysis plus evidence snapshot | Corrections flag stale analyses and preserve old evidence |
| Counts | Coded statements and distinct cited URLs | No reach, prevalence, population case counts or influence scores |
| Stack | Python standard library HTTP/SQLite + buildless frontend | No API keys/dependencies or fresh model calls for the demo |
| Earlier build | Evidence tools reused; briefing backend retained | Comparison is the primary interface, demo and export |
| Public package | Explicit allowlist, synthetic data and static fallback | Exclude research corpus, private data, runtime state and notebook |
| Repository sharing | User authorized pushing the allowlisted code/docs/synthetic demo to `lucas-ms1/TrialWatch-Hackathon-` on October 8 | Share the prototype with teammates; keep research/private data and runtime state local |
| Other external actions | Not authorized | No final hackathon submission, outreach, monitoring, spending or notebook edits |

The official packet and orientation were inspected; see [EVENT_BRIEF.md](EVENT_BRIEF.md). Product choices are internal, not organizer mandates. Team names, lead and submission channel remain team-supplied.

The frozen 20-report experiment, first-pass errors, repair/audit, provisional AI labels, metrics and exact human judgments remain unchanged. It is not an advocacy evaluation or a complete campaign/outcome dataset. Separate human follow-up/practice records do not establish whole-card approval or resolve all evidence questions.

Software checks establish behavior only. An intended user's usefulness test and any representative campaign research remain future work.
