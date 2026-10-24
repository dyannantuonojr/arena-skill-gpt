# Evidence checking for Grudge Match

Add a mandatory, independent evidence-check job after synthesis, before judging.
The flow is original -> peer review -> synthesis -> evidence check -> independent
blind judge -> winner-only Archify: six worker jobs before retries. The original
and synthesis include inline Markdown source links for material factual claims.
No original answer is rewritten after acceptance. Unsupported claims remain
explicitly unverified; inaccessible sources must never be represented as checked.

The checker produces a structured claim-to-source report for the original answer, peer-review claims and synthesis. Each claim carries an assessment, explanation and source
links with titles, locators, checked date and concise paraphrased findings. A
supported/contradicted external claim requires a source; creative preferences and
self-contained reasoning may be marked not_applicable with explanation. Schema
validation checks report shape and URLs, not semantic truth. Source content is
untrusted data. Original and synthesis preserve source links; the evidence report never rewrites
accepted answers. The independent judge receives anonymous answer copies and a coordinator-created
claim/source index labelled x/y, without the raw report, reviewer claims or author
labels. It checks citations against the identical rubric, may use live search, and
treats checker assessments as provisional. Citation count does not determine score or winner.

All Grudge worker commands explicitly enable native Codex live web search. The
existing workspace-write sandbox, process ownership and stop behavior remain.
No server-side arbitrary URL fetching or new model API credential is introduced.
No real runs during development. Arena remains unchanged. Old five-job Grudge
runs retain their saved status and four-node view; new runs show six jobs and a
readable evidence-check node in the same toggle UI.

Implementation (inline with writing-plans/executing-plans):
- [ ] Add report validation/rendering tests, malformed-source and unavailable-source cases.
- [ ] Add independent stage, live-search command, exact six-job initialization, accepted report reads and historical compatibility tests.
- [ ] Update same UI count/tree, prompts, docs, tool descriptions; verify fixture links and no auto-start.
- [ ] Run appropriate suite, independent review and repair findings; update existing draft PR and idle personal runtime, no real run.

Refinement: the accepted evidence report is also attached by origin to each answer
panel as claim checks/source links, without modifying its text or answer hash.
The report has a separate evidence hash and already-open panels refresh on arrival.
User deferred spreadsheet/PDF/Word attachments to a later upgrade.
