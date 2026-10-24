# Required Output Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for implementation.

**Goal:** Browse every answer and require implementation guides with Archify for finalists.
**Architecture:** Static safe HTML export plus hash-bound artifact acceptance and delivery gates.
**Tech Stack:** Python3.8+ stdlib, native workers, Archify/Node/browser for finalist diagrams.
**Spec:** ../specs/2026-10-24-required-outputs.md

## Global Constraints
- Fixed original answers; collapse assumptions and review scope by default.
- Mandatory finalist packages;33 default jobs=31core+2packages.
- Legacy saved-state compatibility; no skipped artifacts disguised as complete.

## Review Focus
- All entries selectable, including eliminated entries and both finalists.
- No raw answer HTML/script execution; hidden sections remain accessible collapsed.
- Wrong answer/candidate/HTML hashes or failing receipts block delivery.
- Report links stay inside the run; stale exports are regenerated.
- Required dependency failures remain incomplete, not optional fallback.

### Tasks
- [x] Test and implement a reusable all-answer viewer with collapsed scope sections.
- [x] Add artifact phase, acceptance command, hash validation and report delivery gate.
- [x] Generate two current finalist packages with real Archify checks.
- [x] Browser-test current viewer, independently review, run full CI and publish.
