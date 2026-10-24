# Fixed-answer Selection Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task.

**Goal:** Default to 16 fixed answers, 15 independent judges and 31 jobs.
**Architecture:** Add explicit selection/evolve modes to the existing state engine.
**Tech Stack:** Python 3.8+ standard library, native agent tools, Archify docs.
**Spec:** ../specs/2026-10-24-fixed-selection.md

## Global Constraints
- Selection is default; explicit evolve preserves the original 91-job structure.
- Selection never modifies answers; saved legacy states retain evolving behavior.
- Maintain 1-16 CLI bounds, existing weights/fatal rules and MIT credit.

## Review Focus
- Plans count jobs and waves correctly for both modes and optional baselines.
- Winners follow fixed branches instead of reseeding between rounds.
- Missing or changed frozen answers stop progression.
- Invalid judges remain retries, never coordinator choices.
- A full selection run and legacy evolving run both resume through real CLI.

### Task 1: Engine and tests
- [x] Add failing behavioral tests for selection phases, counts and fixed paths.
- [x] Add mode-aware planning, judging templates, branch progression and hashes.
- [x] Run all tests including CLI simulations of both modes.

### Task 2: Distribution
- [ ] Update prompts, README, manifest metadata and source-backed Archify diagram.
- [ ] Independently review, address findings, validate skill and publish.
