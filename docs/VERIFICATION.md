# Verification record

October 8 publication review: the public allowlist now contains **39 files**. Two historical adapters containing source-specific wording and human-feedback mappings, plus three unused research helpers, were removed from the release list before the GitHub push. Their original local files remain unchanged and ignored. From a fresh extraction of the 39-file package, the validator, all **63 tests**, fallback rebuild and live HTTP app smoke passed. Publication review found no additional blockers in the remaining release files. The October 7 record below describes the earlier local package.

October 7, 2026. Software verification of the Track 3 campaign-comparison prototype using synthetic material. These checks are not a real-world usefulness study or human validation of evidence.

## Observed results

| Check | Result |
| --- | --- |
| Unit tests | **63 passed**, including 10 campaign-comparison and 9 retained briefing/follow-up tests; all 63 also passed from a clean extracted package |
| Case schema validator | Passed on 3 synthetic case-schema examples; structural validation only |
| Frontend syntax | Passed using bundled Node |
| Browser workflow | Edge 154: clean workspace → evidence review → analyst coding → three saved comparisons → cited Markdown download |
| Dates and evidence | Known and unknown date groups, source passages and publication dates visible; actual outcome text shown in comparison |
| Corrections/staleness | Supported correction preserved the original, flagged saved analysis stale, and refreshed only after a new analysis save |
| Saved vs unsaved | Unsaved analyst text excluded from exported comparison; download matched backend Markdown except request timestamp |
| Manual intake | Rejected excerpt absent from pasted text; accepted exact passage; markup remained literal text rather than executing |
| Restart persistence | Three analyses, correction/review revisions, analysis history and manual intake survived server restart |
| Layout | Desktop comparison/timeline and 390px mobile visually inspected; table scrolls horizontally at 1050px within a 330px container, with no document overflow |
| Browser errors | No application JavaScript or CSP errors in final rendered checks |
| Offline fallback | Opened directly from disk with browser networking disabled; citations, limits and editable-output links retained |
| Frozen research | All **61 files** in the pre-build research/experiment SHA-256 manifest unchanged |
| Submission archive | **44 explicitly allowlisted files**, ZIP integrity and per-file SHA-256 verified; no runtime databases, captures, notebook or organizer PDFs |
| Clean extraction | Validator, all 63 tests, fallback rebuild and live HTTP app smoke passed using extracted files alone |

The archive test first identified a missing static configuration file required by legacy synthetic regression tests. It was added to the allowlist and the full clean-extraction checks then passed. That configuration contains parameters, not research observations. A narrow-screen table issue was found and fixed; final geometry and visual inspection passed.

The installed Chrome headless launch exited before loading the app, so browser checks used installed Edge successfully. Test-only browser automation uses the available bundled Playwright runtime; the application and public tests require only Python's standard library.

## Reproduce and boundaries

Run the README validation and unit-test commands. Build the fallback with `python scripts/build_demo_fallback.py`; build the allowlisted ZIP with `python scripts/package_submission.py`. The package builder verifies its exact inventory and file hashes every run. A final documentation-only rebuild preserves the code and fixtures used in the successful clean-extraction test.

Browser receipts, screenshots and isolated test state stay in ignored `outputs/verification/`. They are not part of the submission package. The default app still starts with no saved reviewer or analyst judgments; the offline fallback is explicitly scripted.

These checks do not establish source accuracy, current case status, coding agreement, analyst time savings, practitioner usefulness, campaign causation or national impact. No external publication, submission, message, monitoring job or notebook edit occurred. Team membership/lead, a judge-accessible release link, submission channel and timed human rehearsal remain pending.
