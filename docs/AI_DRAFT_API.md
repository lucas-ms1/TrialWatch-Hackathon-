# Pending draft API

The local app can import a preserved model output, save a manual pending draft or load the entirely invented example. An explicit `--allow-live-draft` startup flag enables at most one additional bounded Codex CLI request in that isolated state. The default is off. Discover the executable through `PATH`; use the CLI's existing ChatGPT login-status command, without reading or exporting authentication files. No API-key setup is used.

Drafts are evidence-assisted preparation. Imported receipts report a saved run; a fresh successful integrated request is identified separately. Mocked provider tests establish software behavior only. Every draft keeps twenty null mappings, unresolved stage questions and a separate pending legal review. Saving an option never executes it.

The current clean-input draft adapter requires PDF-page locators and at most twenty proposition/passage bridges, with its original bounded stage structure. Retained HTML judgment examples use the separate source-backed rights-assessment and intervention contracts. They do not invent PDF pages or pass a larger HTML evidence record through this adapter. Their preparation origin identifies in-chat AI preparation rather than a saved or live CLI run.

`GET /api/ai-drafts/state/<candidate_id>` returns the latest draft, immutable history, separate scoped source-summary history, provider/schema/citation errors and an honest capability status. `synthetic_example` is available only for the matching invented case. Returned citations resolve passage IDs to source URLs/titles and stable intake claim IDs. Input factual passages retain exact quotes, PDF/printed-page roles, attribution context, date roles and uncertainty; standard questions refer to supplied standard passage IDs.

`POST /api/ai-drafts/import/<candidate_id>` takes exactly:

```json
{
  "expected_revision": 0,
  "author": "Preparation attribution",
  "origin": "saved_model",
  "draft_json": "raw original UTF-8 JSON text",
  "model_input_json": "raw clean input JSON text",
  "schema_json": "raw bounded output schema JSON text",
  "receipt_json": "raw completed run receipt JSON text"
}
```

Use `Path.read_bytes().decode("utf-8")` when importing raw files. Universal-newline conversion changes byte hashes on Windows. Origins are `saved_model`, `manual_draft` and `synthetic_fixture`; manual/synthetic receipts must be null. `live_model` is reserved for the integrated runtime. A saved-model receipt must report a completed, one-call ChatGPT CLI run using `gpt-6.1-sol`, with no tool events and matching exact input/schema/output hashes. This is reference integrity, not provider authentication or legal validation.

`part2-clean-input/1` is a drafting sidecar, not a rights intake. The actual case first enters through genuine `rights-intake/2`. Runtime checks require a matching current rubric, exact intake sources, all claim/passage bridge links, exact source excerpts/locators, competing accounts, unknown dates, null rights mappings and no approval. Every full factual passage must also occur in its own saved structured-intake source text when that capture exists. Selected Abra date/scope guards preserve the individual notice account, separate dated motion grant and undated dismissal, document/cover roles and general-refiling limits. These mechanical checks do not establish substantive support, authenticity, law applicability or usefulness.

`POST /api/ai-drafts/live/<candidate_id>` takes `{expected_revision, author, model: "gpt-6.1-sol"}`. A current validated saved clean input is required. The request runs in an empty temporary working directory with user configuration/rules ignored, project instructions disabled, API-key environment variables removed and shell/browser/file/MCP/app/plugin/agent features disabled. Only supplied input and the bounded schema reach the request. Unknown tool-item types fail closed. The durable attempt marker is reserved before execution; timeout/provider/validation failure permits no automatic retry. Raw prompt, input, schema, provider events/output and receipt remain in the isolated state's ignored `ai_runs` directory. None belongs in the public package. Visible errors leave saved/manual paths usable.

`POST /api/ai-drafts/addenda/<candidate_id>` takes `{expected_revision, author, note}`. It appends a new draft revision retaining the raw model output, hashes, provenance and old dependency snapshot. A note is an attributed addendum; it neither rewrites the raw output nor records human approval.

`POST /api/ai-drafts/source-reviews/<candidate_id>` takes exactly `{expected_review_revision, draft_revision, reviewer, decision, claim_ids, passage_ids, reason, reported_inspection: true}`. Decisions are `accept_with_qualifications`, `correction` or `unresolved`. Scope must contain resolving selected claims and their exact supporting passage bridge. This separate source-summary record describes the reviewer's reported inspection; it cannot approve rights dimensions, authenticate a whole case or dispose of an advocacy proposal. Generic agreement, silence and software tests never supply it. Historical review references remain unchanged and can appear as clearly attributed addenda; no new review timestamp is invented.

`POST /api/ai-drafts/worksheet/<candidate_id>` takes `{expected_draft_revision, author, selected_option_id: "verify_records" | "defer_public_route"}`. This explicit save creates source-backed historical context, a blank twenty-dimension assessment only if none exists, and a pending deterministic intervention proposal with both alternatives. It preserves every AP passage/AC bridge and the exact named route in the option's objective. Current opportunity, authority, preferences, harm and feasibility remain unknown. Existing assessed rights are not overwritten. The route saves no rights review, source-summary review or human disposition. Its constituent saves are append-only; a failed save must be inspected before retrying.

Draft dependencies include the actual candidate, evidence-review revision, captured source text and rubric. Re-importing identical raw draft/input/schema bytes retains their earlier dependency snapshot; it cannot make an old draft current after a correction. Derived assessments/context do not become draft inputs merely because the worksheet saved them. Proposals snapshot exact assessment/context versions and the linked AI draft ID/revision/hashes. Evidence corrections, reassessment, context changes or draft addenda stale dependent proposals without altering old snapshots or decisions.

`GET /api/ai-drafts/export/<draft_id>?format=md|json` exports the immutable selected draft, current stale warnings, exact sources/locators/bridge, all alternatives, separately scoped reviews, addenda and raw hashes. Export is a local artifact, not approval or publication.

Run `python -m unittest discover -s tests -p test_ai_drafts.py -v`. The synthetic example is reproducible with `python scripts/build_ai_fixture.py` and uses only invented source text plus the original prototype rubric.
