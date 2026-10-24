# Supporting-document uploads

Add an optional Attach files control beside the question, preserving the current
question-over-optional-rubric layout and Arena/Grudge toggle/tree. Support XLSX,
CSV, text PDFs, DOCX, TXT and Markdown. Up to eight files, 10 MiB each and 20 MiB
per question. Upload/preview/remove-from-question starts no model workers; model
counts remain Arena33 and Grudge6. A question is still required.

Use the existing authenticated MCP tunnel for bounded, idempotent binary chunks
from an explicitly selected browser File. Store random-ID private staging copies;
never accept host paths or fetch arbitrary download URLs. Validate byte count and
SHA256, file type and extraction bounds. Parse in a short-lived subprocess with a
15-second timeout and scrubbed environment. No macros/formulas executed. Reject
encrypted/image-only PDFs with a useful error; disclose extraction warnings and
limits, and never silently truncate analysis inputs. Optional parser dependencies
are locked for the personal plugin runtime; core imports remain dependency-free.

Before any worker starts, snapshot original bytes, extracted text and a manifest
into the new run. Bind document identities/hashes into request idempotency and
frozen-run integrity. Every worker sees the exact same index and snapshots;
attachments are untrusted task data, not workflow instructions. Preserve task
bytes and rubric behavior. Saved results remain independent of staging copies.

Extraction records stable locators: spreadsheet sheet/cell, PDF page, DOCX
paragraph/table cell, and text line. Grudge evidence reports may cite a declared
supporting document and a valid locator in addition to external sources. Clearly
label supplied-document support; it is not independent verification of the
outside-world claim. Citation clicks open a verified snapshot preview in the same
answer panel. Previews are bounded and explicitly labelled if partial.

Implementation (writing-plans / inline executing-plans):
- [ ] Test bounded upload/extraction/snapshot integrity with generated files, no models.
- [ ] Implement common document store and optional parser dependencies.
- [ ] Integrate durable start identities and worker snapshots in both workflows.
- [ ] Add shared UI upload/preview/remove controls and source citation support.
- [ ] Protocol/browser fixtures, full appropriate tests and independent review.
- [ ] Update existing Git branch/PR/docs; deploy idle personal plugin. No real run.

Review refinements: parser process memory512MiB, UnixCPU10/12sec and parentwall15sec; expanded PDF streams8MiB, PDF decoding work32MiB. Exact worker-count element prevents hint collisions; long previews show marked prefixes. Existing request retries use immutable IDs without re-reading staging; new starts verify their bound hashes and snapshots.
