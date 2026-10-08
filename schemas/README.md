# Case data contract

This is a generic preparation scaffold, not an official hackathon deliverable or an interpretation of Track 1 rules. Check organizer rules before using prebuilt code in a submission.

Run from the workspace root with Python 3.11 or newer; no installation or external packages are needed:

```powershell
python scripts/validate_data.py examples/cases.synthetic.json
python -m unittest discover -s tests -v
```

The JSON Schema defines the record structure. The standard-library validator implements only its used subset of keywords and adds the semantic rules below. It does not implement the entire JSON Schema specification, fetch source pages, verify quotations, or assess guilt or legality. It rejects unknown schema keywords so unsupported future schema additions fail visibly. Exit codes are 0 for valid files, 1 for input failures, and 2 for CLI or schema-loading errors.

- Each case is a review candidate with a document-unique `case_id`, an explicit `synthetic` flag, and one Southeast Asian country code. Country codes are scope metadata; they imply no comparative assessment of countries.
- Sources need an ID, HTTP(S) URL, publisher, publication date (or `null`), retrieval timestamp with timezone, and a language tag. Source IDs and claim IDs must be unique within a case. Evidence references are local to their case.
- Every claim needs at least one source-linked quote and a locator such as a page, paragraph, or timestamp. Record attributed reports and allegations as such. A citation alone does not prove that a claim is supported: a person must compare the source, quote, and claim.
- Preserve the original source-language text in `quote`. Set `translation` to `null` when no translation exists; otherwise record its text, target language, human/machine method, and reviewer (or `null` if unreviewed). Source `language` describes the original. An unreviewed machine translation is not verified evidence.
- `event_date` belongs to the reported event. `published_date` belongs to its source. Never substitute one for the other. Use ISO dates (`YYYY-MM-DD`) or `null` if unknown; use timestamps with timezone for retrieval and review. Do not invent dates or silently translate quotations.
- `pending`, `in_review`, `needs_sources`, and `ready_for_expert_review` are human workflow states. The last requires a named reviewer and review timestamp; it is not a legal finding. Cases with no claims must have `needs_sources` status.
- Descriptive labels, country selections, and source metadata also need human verification. The contract contains no subjective numeric guilt, risk, or fairness score.

`examples/cases.synthetic.json` contains only invented cases, invented evidence text, and nonresolving `example.invalid` URLs. Countries are illustrative routing labels. No example represents a real person, prosecution, event, publisher, or legal rule. The third fixture shows an intake shell with no asserted facts. Keep synthetic examples distinct from any future real source collection, and do not present them as research findings.
