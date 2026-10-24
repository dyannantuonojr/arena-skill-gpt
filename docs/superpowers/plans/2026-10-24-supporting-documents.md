# Supporting Documents Implementation Plan

> Use superpowers:executing-plans inline with one independent final review.

**Goal:** Supporting-file uploads and questions about files in both existing modes.
**Spec:** docs/superpowers/specs/2026-10-24-supporting-documents.md
**Architecture:** bounded app-only MCP chunks -> private validated staging -> data-only extraction in a limited subprocess -> immutable per-run snapshots -> worker input and source-location evidence. Same question/rubric/tree, no model starts from uploads.

- [x] Upload/extraction/snapshot tests; CSV, XLSX, PDF, DOCX and long-text fixtures.
- [x] Common store and locked optional parser dependencies; memory/time/expansion bounds.
- [x] Durable request IDs, run snapshots, archival verification and worker context in both workflows.
- [x] UI picker/preview/remove, failed-file start blocking, mode drafts and supplied-document citations.
- [x] Independent review found three issues; each reproduced and repaired with regressions. Follow-up review confirmed fixes. Existing retries also no longer depend on mutable staging.
- [x] Full 190-test suite passed (5 platform skips), with clean independent review. Deployed to the idle personal runtime; live ChatGPT upload and preview tested with a synthetic CSV and a multi-chunk TXT. No real run.
- [ ] Push the upload changes and README clarification/banner; update the existing draft PR and the default-branch project introduction.
