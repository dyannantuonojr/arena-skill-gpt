# Personal Arena Plugin Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add an owner-only MCP plugin interface to the existing Arena runner and tree UI.

**Architecture:** Reuse the runner behind a small service API; expose it through an optional MCP runtime and MCP Apps UI resource. Keep the loopback application and bundled Archify renderer intact. Connect remotely only after local behavior, owner isolation, and embedded rendering are verified.

**Tech Stack:** Core Python standard library; optional Python 3.11+ official MCP SDK runtime; SQLite start reservations; existing HTML/JavaScript tree; bundled Node Archify.

**Spec:** ../specs/2026-10-24-personal-arena-plugin-design.md

## Global Constraints

- Core retains Python 3.8+ support; optional plugin runtime is Python 3.11+.
- Preserve 16 fixed answers + 15 judgments + 2 required finalist packages.
- One active run; up to three workers. No new real tournament during installation.
- No product planning gate or prepare_plan tool. Archify here depicts programming work.
- Preserve loopback Host/Origin/nonce protections, vendor bytes, credits, and licenses.
- No remote exposure or account connection until the exact deployment is reviewed.

## File map

- skills/arena/arena_service.py: controlled start/read/stop boundary and durable requests.
- skills/arena/arena_runner.py: reserved run creation support without automatic retries.
- skills/arena/plugin/server.py: official SDK protocol registration and UI resource.
- skills/arena/plugin/auth.py: verified owner identity checks at remote request boundary.
- skills/arena/plugin/requirements.lock: tested released SDK and resolved dependencies.
- skills/arena/plugin/ui/: MCP bridge and embedded tree interface wrapper.
- skills/arena/arena_view.py: shared viewer data/selection behavior where reusable.
- skills/arena/plugin/SKILL.md: plugin operations; no mandatory planning step.
- mcp.json, .codex-plugin/plugin.json: portable plugin connection metadata.
- docs/PERSONAL_PLUGIN.md: local setup, private connection, diagnostics, rollback.
- tests/test_service.py, tests/test_plugin_protocol.py, tests/test_plugin_auth.py:
  meaningful contract tests; plugin-only CI runs on supported Python versions.

## Review focus

- Lost start response: identical request cannot launch a second tournament.
- Host crash: reserved requests remain interrupted; reconnect never resumes workers.
- Stale cancellation: old run ID cannot stop the current run.
- Older result read: inspecting it cannot select over or interrupt a current run.
- UI sandbox restrictions: native diagrams, answer access, and zoom work in ChatGPT.

## Task 1: Safe service boundary

**Interfaces:** ArenaService(data_root, runner); start_run(question: str,
guidance: str, request_id: str) -> dict; get_run_status(run_id: str) -> dict;
get_answer(run_id: str, answer_id: str) -> dict;
get_finalist_package(run_id: str, answer_id: str) -> dict;
stop_run(run_id: str) -> dict.

- [x] Add failing tests for duplicate and changed-content request IDs, crash
  after reservation, stale stop, concurrent start, and historical reads during
  another active run. Assert worker launch count and unchanged active run ID.
- [x] Run `python -m unittest discover -s tests -p test_service.py -v`; confirm failures.
- [x] Implement SQLite reservation-before-launch, stable run IDs, strict run/path
  validation and artifact hash checks; minimally extend runner start to accept
  only service-reserved new run IDs. Interrupted reservations never auto-start.
- [x] Run service and runner suites; verify no core behavior regression; commit.

## Task 2: MCP tools and optional runtime

**Interfaces:** create_server(service, owner_policy) returns the installed SDK's
server object. Tools consume the Task 1 service and return typed structured data.
open_arena(run_id: str | None) returns the versioned UI resource reference and
initial state, without starting workers.

- [x] In an isolated plugin environment, select a released official SDK compatible
  with Python 3.11+, pin/lock it, and record its actual server/transport interfaces.
- [x] Add failing real-SDK client tests for initialize, tools/list, resources/read,
  exact optional guidance, bounded result payloads, unknown IDs and tool schemas.
- [x] Run the protocol tests with the locked plugin runtime; confirm failures.
- [x] Register the six named tools, immediate run-ID return, correct read/write
  annotations, versioned resource URI, and `text/html;profile=mcp-app` MIME type.
  Keep SDK imports outside the core Python 3.8 test path.
- [x] Run protocol tests with a fake runner; assert opening and reading start zero
  jobs. Verify stdout remains protocol-only for stdio; commit.

## Task 3: Embedded Arena interface

**Interfaces:** UI uses the standard MCP Apps bridge for open/start/status/answer/
package/stop calls; it receives service DTOs rather than localhost paths.

- [x] Add labeled browser fixtures for initial state, running updates, completed
  finalists and errors. Test question submission and blank guidance preservation.
- [x] Port the tree-first layout, answer/match selection, finalist tabs and
  collapsed scope/assumptions. Retain camera/scroll/tab through live updates.
- [x] Probe nested native Archify iframe behavior under the documented CSP.
  If blocked, implement a self-contained wrapper renderer adaptation without
  changing vendor; verify tree selection and all native finalist outputs.
- [x] Browser-test all 16 answer selections, both finalist tabs, exact camera
  preservation, duplicate Start prevention and visible reconnect errors.
- [x] Validate resource policy and bridge calls; commit. Do not claim ChatGPT
  compatibility until Task 6 verifies it in the real client.

## Task 4: Owner-only authentication

**Interfaces:** OwnerPolicy.authorize(verified_identity) -> owner_id or rejection.
Identity comes from transport token verification, never tool arguments.

- [x] Add failing tests for missing, wrong-owner, expired, wrong-audience and
  wrong-issuer identities; ensure denial occurs before run/filesystem access.
- [x] Implement the SDK-supported OAuth verification boundary with one configured
  issuer/subject owner binding and bounded safe diagnostics. Tunnel-only identity
  is usable only if independently proven equivalent for this deployment.
- [x] Run `python -m unittest discover -s tests -p test_plugin_auth.py -v` in the
  plugin environment; require all denial tests pass. Confirm no secret in outputs.
- [x] Check local stdio is local-only and remote transport fails closed when
  owner configuration is missing; commit.

## Task 5: Package and regression verification

- [x] Add plugin SKILL.md with direct open/run/read/stop instructions and optional
  grading guidance. Include no prepare_plan or per-run planning requirement.
- [x] Add portable manifests/config templates, runtime setup/health diagnostics,
  private host configuration instructions and a rollback procedure. Keep owner
  identity, credentials and tunnel IDs outside the repository.
- [x] Add separate plugin CI on Python 3.11/3.12 while retaining core 3.8/3.12 CI.
- [x] Run `python -m unittest discover -s tests` for the core, plugin SDK contract
  tests in the locked environment, skill validation, bundle integrity and real
  Archify checks against software fixtures. No model jobs.
- [x] Review changes against the spec, check license/credit preservation, commit.

## Task 6: Connect and verify the personal deployment

- [ ] Confirm target always-on machine; inspect its available private tunnel and
  owner-auth configuration. Prepare a concrete connection summary for approval.
- [ ] Once that exact access change is authorized, configure the private tunnel
  and personal ChatGPT plugin. No public HTTPS fallback without a separate choice.
- [ ] Verify tools discovery and an actual embedded labeled fixture: question,
  optional rubric, tree, every answer, finalist diagrams, zoom, reconnect and stop.
- [ ] Verify non-owner access is rejected. Report remote readiness only if both
  access isolation and the actual client UI pass.
- [ ] Leave a fresh real Arena test for the owner's explicit Start request.

## Self-review

Every review-focus case maps to Task 1 or Task 3. The optional SDK runtime cannot
raise the core minimum Python version. No plan-ID or pre-run Archify dependency
remains. Remote activation and actual-client rendering remain completion gates,
not claims inferred from local fixture success.

Implementation status: Tasks 1–5 verified locally (154 tests, five Windows filesystem skips). Task 6 target is this Windows computer. Remote access is not enabled; actual ChatGPT client and owner-only tunnel validation remain pending.
