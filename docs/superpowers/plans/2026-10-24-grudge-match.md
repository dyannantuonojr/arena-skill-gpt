# Grudge Match Implementation Plan

> For agentic workers: use superpowers:executing-plans inline, followed by one independent review.

**Goal:** Add the approved five-job Grudge Match workflow to the same personal plugin and repository.
**Architecture:** GrudgeRunner extends the existing owned worker runner; GrudgeService extends durable reservations and verified reads. Separate tools and resource reuse the existing viewer. Existing Arena defaults remain unchanged.
**Tech Stack:** Python standard library, locked MCP SDK, existing HTML/JS viewer, vendored native Archify.
**Spec:** docs/superpowers/specs/2026-10-24-grudge-match.md

## Constraints
- No real model run during development/setup.
- Question above optional rubric; tree and readable outputs retained.
- Original, review, synthesis, judge, winner-only Archify: five jobs before retries.
- Existing Arena unchanged.

## Review focus
- Original may beat synthesis; only actual winner gets package.
- Invalid judge scores cannot choose winner or skip a job.
- Tampered or unaccepted outputs never become readable/advance.
- Duplicate start and restarts never launch duplicates; workflows cannot run concurrently.
- Question/rubric remain exact and visible; reviews/judgments readable; reads start no work.

## Task 1: Runner/service
- [ ] Write failing fixture tests for sequential dependencies, both possible winners, rejected judgment, tampering and durable requests.
- [ ] Implement grudge_match.py reusing owned runner and service.
- [ ] Run tests; verify five jobs and only one artifact job.

## Task 2: Plugin/interface
- [ ] Write failing protocol/resource tests for separate Grudge tools, idle read and visible form.
- [ ] Register Grudge tools/resource; reuse existing viewer with workflow configuration and labeled outputs.
- [ ] Verify original tools unchanged, new viewer and all output links with no model workers.

## Task 3: Delivery
- [ ] Document invocation and exact job count; add operating skill.
- [ ] Run appropriate suite and independent final review; repair important findings.
- [ ] Deploy files to existing personal runtime and refresh idle connection only. Verify idle UI, no real runs. Keep Git changes reviewable.
