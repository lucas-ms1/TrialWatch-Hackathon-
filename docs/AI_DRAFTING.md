# Pending evidence-assisted drafting

The local interface can retain a supplied model draft with its original raw output, clean input, schema and run receipt. It displays attributed summaries, supporting and competing passages, an exact passage-to-intake-claim bridge, date roles, unresolved stage questions, gaps and two bounded alternatives. Draft preparation is separate from source review, rights assessment and a human intervention disposition. Twenty rights mappings remain null.

The default app works without model access. Structured intake, manual pending drafts and deterministic worksheets remain available. On the fictional starter's first case, **Pending AI draft → Save invented pending-draft example** demonstrates this route with an explicitly synthetic fixture and no model request. The fixture is not a retained real run or human review.

The Pending AI draft tab has four screens: **Open or prepare → Read draft → Evidence and gaps → Compare alternatives**. Back/Next and the numbered step controls navigate within the tab; the URL preserves the selected screen on refresh. Open saved draft goes to the summary, and successful import goes there automatically. AP source passages, legal excerpts and AC intake claims open in a read-only evidence window. Chronology, stage questions, gaps and option details expand on demand. These navigation actions record no inspection or approval. Original draft mappings remain distinct from any newer rights assessment.

For a separately supplied real draft, import the four original UTF-8 files: draft JSON, clean model-input JSON, output-schema JSON and run-receipt JSON. Import checks their raw hashes, the bounded schema, own-source excerpts, exact passage/claim links, competing accounts, unknown dates and all twenty null mappings. A completed receipt is provenance supplied with a prior run; it does not authenticate the facts or establish a fresh integrated run. Use a new isolated seed/state for real intake and keep populated materials outside the public package.

An attributed addendum creates another saved revision while retaining the raw model output and its hash. A carried-forward historical review note retains its original reviewer, timestamp and exact scope; it is not a new review. Source-summary reviews have a separate contract and table. They do not approve rights dimensions or create an advocacy disposition.

**Save context & pending proposal** explicitly bridges the latest current draft's options into the existing intervention worksheet. It records dated supplied passages, competing evidence, unknown current factors and alternatives, plus an entirely not-assessed rights preparation when none exists. It saves no source/legal approval, no human acceptance and no executed action. Draft, evidence, rubric, assessment and context revisions remain inspectable. Corrections and changed dependencies mark earlier dependent material stale while retaining its snapshots.

This shortcut appears on the alternatives screen and remains there after saving, alongside the saved proposal's exports and status. It is unavailable when rights have already been assessed; use the explicit Advocacy / intervention worksheet for a proposal based on those assessed rights. The interface mirrors the existing backend restriction and does not replace the assessment.

## Optional bounded CLI path

The server exposes the live-draft action only when started with `--allow-live-draft`:

```powershell
python -m reviewdesk --port 8782 --seed <new-local-seed.json> --state-dir <new-local-state> --allow-live-draft
```

The path discovers `codex` locally and checks `codex login status` for an existing ChatGPT login. It does not read authentication files, expose credentials to browser code, require an API key or create a purchase. It reuses an already validated clean input and schema. The request explicitly selects `gpt-6.1-sol`, runs in an empty temporary directory and disables tools, browser/search, agents, apps, plugins and project instructions. Supplied evidence is data, never instructions.

One attempt is persisted per isolated state, without automatic retries. Missing executable/login, disabled access, provider failure, disallowed tool events, malformed output, citations or changed dependencies fail visibly; saved/manual paths remain usable. Raw input/output and a receipt stay in the new state's local `ai_runs` directory. Only an actual successful integrated request can establish that path's operation on a particular machine. A successful run does not establish legal accuracy or usefulness.

## Local API

The [exact request/response contract](AI_DRAFT_API.md) includes raw newline preservation and persistence details.

- GET `/api/ai-drafts/state/<case_id>`: saved history, pending status, exact links, current dependency warnings, separate source-summary history, visible errors and capability status.
- POST `/api/ai-drafts/import/<case_id>`: `expected_revision`, `author`, `origin`, `draft_json`, `model_input_json`, `schema_json`, `receipt_json`. Raw JSON fields are strings; manual/synthetic origins require a null receipt. The server reserves `live_model` for its own successful request.
- POST `/api/ai-drafts/live/<case_id>`: `expected_revision`, `author`, `model: "gpt-6.1-sol"`.
- POST `/api/ai-drafts/addenda/<case_id>`: `expected_revision`, `author`, `note`.
- POST `/api/ai-drafts/worksheet/<case_id>`: `expected_draft_revision`, `author`, `selected_option_id`.
- GET `/api/ai-drafts/export/<draft_id>?format=md|json`: cited pending draft/options and preserved provenance.
- POST `/api/ai-drafts/source-reviews/<case_id>`: exact draft revision, reviewer, explicitly reported inspected claim/passage IDs, limited decision and reason. This endpoint is separate from rights review; source-summary acceptance cannot approve a legal dimension.

The prototype performs no new source acquisition, current-status lookup, intervention execution, movement detection, calibrated forecast or monitoring. Counts and software checks describe the supplied records and mechanics. The public package contains original code/docs, blank templates and synthetic fixtures only; populated prompts, outputs, captures, SQLite state and real screenshots remain local. MIT does not license third-party sources.
