# Grudge Match Evidence Implementation Plan

> Use superpowers:executing-plans inline; independent final review required.

**Goal:** Add evidence checking and citations for original answer, review and synthesis.
**Spec:** docs/superpowers/specs/2026-10-24-grudge-evidence.md
**Architecture:** Structured report from a separate live-search worker after synthesis, deterministic validation and anonymous judge index; evidence grouped per origin in same viewer. Six jobs, no real run during setup. Existing Arena and historical five-job matches remain compatible.

- [x] Validate and safely render claim/source records, including all three origins, unavailable sources, unsafe links and source-title injection.
- [x] Add sixth worker and Grudge-only native live search; require an accepted report before judge, preserve frozen outputs and hashes, test initial count and legacy reads.
- [x] Display readable report and per-answer evidence supplements; source links use host open-link bridge; keep question/rubric layout and mode toggle.
- [x] Independent review, including final per-answer supplement delta: no remaining important findings. No real workers.
- [x] Complete broader tests, deploy idle personal runtime, and update existing draft PR and repository description.

Document uploads explicitly deferred by the user.

Verification: 176 tests passed (5 Windows filesystem skips); independent review
found no important remaining issue. Browser fixtures exercised all three evidence
sections, citation opening, per-answer references and refresh on report arrival,
with Starts:0. Actual ChatGPT widget shows six-job Grudge mode and five pending
nodes, idle. The runtime is healthy/ready; both real-run directories remain empty.
Repository About now describes six jobs and citations for all three outputs.
