# Supporting documents

Use **Attach files** beneath **Question / task** in the same Arena UI. Attach
files as context or ask questions about their contents. Enter a question, leave
rubric guidance blank or add priorities, and press the selected workflow's Start
button only when ready. Attaching, previewing, switching modes and removing files
from a question never start model workers. Counts remain Arena33 and Grudge6.

Supported files: **XLSX, CSV, PDF with selectable text, DOCX, TXT and Markdown**.
Limits: 8 files per question, 10 MiB per file, 20 MiB total. Documents that exceed
extraction limits are rejected with an explanation rather than silently shortened.
A failed upload must be removed from the question before Start is enabled. Use
Preview to inspect extracted content and format warnings before running.

Examples:
- Attach a budget and ask “Which categories increased, and cite sheet/cell ranges?”
- Attach a report and ask “Summarize the findings and cite the relevant pages.”
- Attach an agreement and ask “Identify inconsistent definitions, citing paragraphs.”
- Attach two documents and ask “Compare their claims and flag contradictions.”

Every run saves its own originals, complete accepted extraction, source index and
hash manifest. All roles receive the same frozen snapshots. Editing/removing a
staged upload cannot alter an existing result. Request retries bind exact upload
IDs (which bind filenames, byte counts and SHA256); the run's manifest separately
binds its copied bytes. Uploaded contents are task data, never role instructions.
Source copies/extractions stay on the configured private host and are supplied to
its signed-in Codex workers when you explicitly run a question. Do not publish
run folders or staging data as part of the Git repository.

## Citation locations

XLSX uses sheet and cell, such as `Budget!B2:C5`; CSV uses `CSV!A1:B10`; PDF uses
`page 3`; DOCX uses `paragraph 4` or `table 1 row 2 cell 3`; text uses `line 12`.
Grudge Match's evidence checker audits original, review and synthesis claims
against these same snapshots. A supporting-document citation must name a declared
file ID, exact filename and a location represented in the accepted extraction.
Its report labels this as **supplied document** support, distinct from independent
verification of the real-world claim. Web citations remain available for external
facts. Document citations open a verified source preview in the answer panel.

Answer prompts receive the index's fragment citation format:
`[filename and location](#document-DOCUMENT_ID/URL_ENCODED_LOCATION)`.
Checker source records use `kind: "document"`, `document_id`, `title` (exact file
name), `locator`, `checked_on`, and a concise `finding`; omit `url` for these local
sources. Unknown IDs or locations are rejected. Source previews may show a bounded
prefix; they explicitly say when partial. Workers use the complete accepted
extraction, not the preview excerpt.

## Extraction coverage

- XLSX: populated cells with coordinates, formula text and available cached values.
  Formulas/macros are not executed. Cached results may be missing or stale; the UI
  says when they are unavailable. Charts, images and Excel rendering are not read.
- CSV: supplied cell text and coordinates. Formula-like strings are not executed.
  UTF-8/UTF-16 BOM files are supported; a Windows-1252 fallback is disclosed.
- PDF: up to 200 pages of extracted text. No OCR or image understanding is provided.
  Image-only/encrypted PDFs are rejected. Pages without text and table-layout
  limitations are disclosed; provide an OCR/text export when needed.
- DOCX: body paragraphs and table cells. Images, text boxes, headers/footers,
  footnotes, nested tables, comments and revision history are not analyzed.
- TXT/Markdown: UTF-8 text with line numbers.

Parsing runs in a separate process with a 15-second wall-clock timeout and a
512-MiB memory limit (Windows Job Object / Unix resource limit); Unix also has a
CPU limit. Expanded XLSX/DOCX archives are limited to 50 MiB. PDF stream decoding
is capped at 8 MiB with a bounded work budget. Extraction is limited to 500,000
characters and 50,000 populated locations, with worksheet dimension limits.
Split or simplify files that exceed these limits. Unsupported legacy `.xls` and
`.doc` files should be exported as XLSX/CSV or DOCX first.

## Setup and storage

Install the updated locked optional plugin runtime requirements, then refresh the
connected plugin tools. No additional model API key or third-party upload service
is needed. The picker sends bounded chunks through the existing authenticated MCP
connection. This works without assuming ChatGPT's optional file-library APIs.
Ordinary chat-composer attachments are not automatically imported; use Attach
files in the Arena interface.

Staging copies live under the plugin data directory's `supporting-uploads` folder;
run copies live under each run's `supporting` folder. **Remove from question** only
removes the file from the next submission; it does not erase saved runs or the
host's retained staging copy. The file on the user's device is never modified.
The personal connection remains personal; this change does not share the plugin
or grant access to other users.
