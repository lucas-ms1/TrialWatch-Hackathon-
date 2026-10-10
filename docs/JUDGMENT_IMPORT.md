# Judgment import preview

Open **Import judgments** in the rights desk. Load a UTF-8 `judgment-import/1` JSON bundle, preview its metadata and passages, select passages, then save the evidence. Search and pagination keep the preview short. Selection survives search and page changes. The importer stores quotations and starts an unassessed case; it does not generate a legal summary, assign scores or record a human review.

The initial real provider is **LawPhil**, for a bounded noncommercial Philippine pilot. Its [collection notice](https://lawphil.net/copyright.html) names a Creative Commons Attribution-Non Commercial 4.0 Philippine licence. The inspected pages also carry an older Attribution-NonCommercial 3.0 notice in their HTML comments. Both notices remain in provenance; the software does not silently relabel the source. The [3.0](https://creativecommons.org/licenses/by-nc/3.0/) and [4.0](https://creativecommons.org/licenses/by-nc/4.0/) licence references remain available. Source title, URL, publisher, notices and the text-processing changes accompany the intake. This route does not establish commercial-use permission or endorsement. Actual populated files remain local and are excluded from the public package.

WorldLII's own current terms could not be verified. Its linked providers have their own terms; no WorldLII crawler is implemented. The importer makes no external requests. LawPhil access and licence checks precede any acquisition; an imported URL is provenance, not an instruction for the server to fetch it.

## Local file contract

Start with the [blank bundle template](../examples/judgment-import.template.json). It deliberately fails validation until required source fields are filled. The bundle has `schema_version: "judgment-import/1"`, `provider: "lawphil"`, and a `document` object containing:

- `document_id`, `title`, `url`, `publisher`, `court`, `country`, `citations` and `proceeding_id`;
- separate `publication_date`, `decision_date`, `retrieved_at`, `language` and `translation_status`;
- exactly one of `html` or `text`;
- optional `raw_sha256` and `decoded_encoding`, retained as supplied capture metadata.

LawPhil uses publisher `LawPhil / Arellano Law Foundation`, court `Supreme Court of the Philippines`, country `Philippines`, and an HTTPS judgment URL under `lawphil.net/judjuris/`. The metadata are supplied fields, not independently authenticated extraction. Unknown publication dates, underlying event dates and person identifiers stay unknown. Partial decision dates preserve their precision. A decision date is never substituted for publication, notice, detention or other event dates.

For offline practice, use the explicitly fictional `synthetic_fixture` provider and the synthetic example. Its source URL uses `example.invalid`, publisher is `Synthetic judgment fixture`, court is `Fictional Court`, and its original fixture content uses MIT. These records display as fictional.

## Preview and saving

`POST /api/judgments/inspect` returns the document metadata, permission/provenance details, selectable passages and potential duplicates. `POST /api/judgments/preview` adds the selected passage IDs and returns an unsaved `rights-intake/2` record. Both operations leave saved state unchanged. The existing `POST /api/rights/intake` performs the explicit save.

HTML is parsed as data. Scripts, styles and navigation are removed; whitespace and paragraph boundaries are normalized. Displayed quotations match the retained cleaned source text exactly. Locators explicitly say **derived HTML/text paragraph**, so they are not mistaken for official paragraph numbering. Footnote references and available section labels remain visible. Original raw captures and byte hashes remain in the local acquisition ledger; the computed decoded-content and cleaned-text hashes have separate roles.

Document URL and cleaned-text version determine the import identity, independently of selected passages. An exact repeat reopens the existing record. Another version of the same source prompts comparison; documents, proceedings and people are not merged automatically. Additional retained passages use the append-only operation below rather than creating another independent case.

Quotes remain attributed and unclassified: party submissions, court reasoning, separate opinions and reproduced testimony are not automatically labelled findings. Rights mappings are null. Advocacy opportunities and human dispositions require their own evidence and review.

Size limits reject oversized input instead of silently truncating. The local HTTP request limit is 1 MiB; source text is limited to 500,000 characters, raw content to 750,000 UTF-8 bytes and individual selected excerpts to 12,000 characters. The response reports its selection bound. Oversized paragraphs remain visible but cannot be selected as one observation.

## Retained passages and prepared analysis

`POST /api/rights/evidence-additions/<candidate_id>` takes `expected_revision` (the current unified evidence revision), `author`, `origin` (`manual`, `ai_prepared` or `synthetic_prepared`) and `claims`. Each claim uses the existing structured claim fields and a new claim ID. Its source must already belong to the candidate, and its exact quotation must occur in that source's saved full text. This operation adds no source, fetches no URL and overwrites no intake, quotation or review. Separate addition history retains the author, origin, date and revision. Additions change evidence dependencies, making earlier assessments and proposals stale.

The existing assessment endpoint accepts an explicitly prepared result for all twenty dimensions. Each result includes applicability, support/contrary observation IDs, rationale, anchored concern or a nonnumeric state, separate confidence/completeness and next verification. The server validates and snapshots supplied analysis; it does not infer scores from paragraph counts or a judgment outcome. `ai_prepared` records remain pending human review.

Historical examples use the complete retained source, distinguish party submissions from adjudicated findings, and identify event-time law. Later General Comments are labelled interpretive guidance when they postdate the proceeding. Published outcomes are already visible during preparation, so these examples demonstrate retrospective analysis rather than prediction. Current status, preferences, mandate and opportunity require separate evidence. Compared verification/deferral options and exports use the existing intervention worksheet. Real examples remain local; the public package continues to contain original code/docs, blank templates and fictional data only.
