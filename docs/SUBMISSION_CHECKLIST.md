# Local submission checklist

**Track 3: Advocacy and Impact — compare campaigns and case outcomes.** Official deadline: **October 10, 2026, 3:30 p.m. ET**. Demo: **10–15 minutes**. See [EVENT_BRIEF.md](EVENT_BRIEF.md); internal checks below are not official scoring rules.

## Required assets prepared locally

- [x] Working comparison prototype, documentation and setup/usage [README](../README.md).
- [x] [MIT license](../LICENSE) for original code/docs/synthetic examples and [third-party notices](../THIRD_PARTY_NOTICES.md).
- [x] [Short tool and intended-use description](TOOL_DESCRIPTION.md).
- [x] [Demo narrative](DEMO_SCRIPT.md) and self-contained [offline fallback](demo/fallback.html).
- [x] Disclosure of pre-event work, AI assistance, synthetic material and evidence limits.
- [ ] Team-provided member names, lead and roles confirmed.
- [x] GitHub destination selected and code/demo publication authorized by the user on October 8: [team repository](https://github.com/lucas-ms1/TrialWatch-Hackathon-).
- [ ] Organizer collection channel and final submission details confirmed.
- [ ] Team timed rehearsal completed within the allocation.
- [ ] Final hackathon submission authorized and performed.

The unchecked items require team participation or external authorization. Repository sharing does not constitute final hackathon submission, organizer endorsement or confirmation of team eligibility.

## Package boundary

The explicit allowlist in `scripts/package_submission.py` includes code, tests, active submission docs, synthetic demo artifacts and the static configuration needed by legacy synthetic tests. The local research source register, research plans, experiment observations, historical outputs, source captures, emails, credentials, runtime state, organizer PDFs and notebook bundles are excluded. Third-party source material is not relicensed. Git ignore rules do not change Dropbox permissions.

The package script checks synthetic flags, file inventory, archive integrity and every file hash. Clean extraction verification is recorded in [VERIFICATION.md](VERIFICATION.md). Do not use a working research ZIP as the submission package.

## Acceptance and claims

Observed verification belongs in [VERIFICATION.md](VERIFICATION.md), including browser checks, source validation, persistence, exports, frozen-file hashes and package checks. Do not mark tests as human evidence validation.

The product compares documented observations and reported outcomes. It does not estimate social reach, rank campaign effectiveness, infer causation, authenticate court decisions or demonstrate national impact. Missing records remain unknown. The prior 20-report AI-reference triage experiment is separate from this workflow and supplies no advocacy-effectiveness score.

A partner usefulness check, systematic real campaign dataset and causal study have not run. No live monitoring, outreach, source collection, spending or notebook changes occur during this build.
