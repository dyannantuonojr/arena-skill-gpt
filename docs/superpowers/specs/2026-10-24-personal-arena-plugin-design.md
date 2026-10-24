# Personal Arena plugin interface: upgrade design

Status: proposed programming design. No remote plugin is built or connected.

## Purpose and corrected scope

Upgrade the existing Arena application into a personal ChatGPT/Codex plugin
connected to the owner's always-on computer. Archify documents how we will
program this upgrade. It is not a required planning step for people using the
finished plugin. There is no prepare_plan tool, plan approval screen, or mandatory
pre-run planning diagram in the product.

The finished interface opens directly to the Arena tree and a question field with
optional grading guidance. Starting a run remains an explicit owner action.
Preserve 16 fixed answers, 15 judgments, two required finalist packages, clickable
answers, collapsed assumptions/review scope, and zoom-preserving updates. The
existing finalist Archify diagrams remain required.

## Architecture and approaches

Build a narrow MCP service around the existing Python runner, then adapt the
existing tree interface to an MCP Apps UI resource. Keep the loopback app working.
Use the maintained official MCP SDK in an isolated optional runtime; the proposed
plugin runtime is Python 3.11+, while the core retains its Python 3.8+ support.
Pin the released SDK and lock dependencies during implementation rather than
assuming its current main branch API is the installed release.

Prefer a private OpenAI Secure MCP Tunnel for the remote connection, subject to
account access. It needs a runtime key and tunnel permissions in addition to
Codex sign-in. An OAuth-protected public HTTPS endpoint is an alternative
requiring a separate deployment choice. Local stdio is a development transport;
it cannot alone connect ChatGPT on another device.

Only the owner may connect. Bind access to verified server-side identity and
reject other identities. Tunnel availability does not by itself prove that a
workspace tunnel is private to one person. Require owner-only OAuth validation
unless the deployed tunnel demonstrably enforces that exact identity boundary.
No public unauthenticated endpoint or automatic public fallback.

## Programming sequence

1. Extract a small service boundary around start/status/stop and saved run reads.
   Add durable start-request IDs so retries never create duplicate tournaments.
   Scope cancellation to the requested active run. Preserve runner behavior.
2. Add MCP tool registration, input/output schemas, immediate run-ID responses,
   and bounded progress/result reads using the service boundary. No arbitrary
   shell or filesystem tools and no credentials in responses.
3. Port the tree, question/rubric controls, answer panel, and finalist tabs into
   an MCP UI resource. Use the MCP Apps bridge instead of localhost fetches.
   Nested frames are restricted by default in ChatGPT: first test the native
   Archify renderer with the allowed UI policy; if unsupported, make a
   self-contained renderer adaptation in the wrapper without patching vendor.
   The acceptance target remains an embedded tree with every answer readable.
4. Add owner authentication and private connection configuration. Keep secrets
   and host-specific identities outside Git. Reuse the existing Codex sign-in.
   Missing identity/configuration blocks remote tool calls.
5. Test the complete interface with labeled fixtures, SDK protocol tests,
   denial cases, retry/restart cases, actual browser interactions, and existing
   regression tests. Do not run a new real tournament as an installation test.
6. Package the plugin skill, manifests, dependency lock, setup checks, and
   documentation. After reviewing the exact target computer and connection
   change, connect the owner's ChatGPT account and verify discovery and fixture
   UI behavior. A real tournament needs its own explicit start request.

## Service and behavior contracts

- Tools: open_arena, start_run, get_run_status, get_answer,
  get_finalist_package, and stop_run. Opening/reading never starts workers.
- start_run accepts exact question, optional guidance, and request_id. Persist
  a stable request-to-run reservation before worker launch. Repeating identical
  requests returns the same run ID; changing content for the same ID is rejected.
  A crash reports the reserved run's actual/interrupted state without restarting.
- One active run, up to the existing three workers; return busy for another run.
- stop_run(run_id) refuses to stop a newer run when given a stale ID.
- Historical reads validate contained paths and accepted artifact hashes without
  changing the live runner's selected run or calling restore().
- Return a run ID promptly; no tournament-length MCP request. Polling/reconnecting
  does not resume interrupted workers. The existing 33-job count excludes retries.
- UI state retains selected answer, active tab, zoom/pan, and scroll across updates.
  Question and optional guidance are available directly in the plugin interface.
- Preserve original license/credits and the pinned vendor bundle unchanged.
- Publish portable setup only; never publish private tunnel IDs, secrets, or runs.

## Future plugin skill scope

The plugin SKILL.md explains how to open the interface, submit the owner's exact
question with optional guidance, inspect actual status, read every answer and both
finalist packages, and stop a specific run. It does not require a planning diagram
or separate plan approval. Start only when the owner asks to run Arena or presses
Start. Do not interpret opening, reconnecting, or a status request as run consent.

## Completion evidence

Require SDK discovery/call tests; owner-only rejection tests; duplicate-start,
crash recovery and stale-stop regressions; saved artifact integrity checks; UI
question submission, answer navigation, finalist tabs and live-camera tests; and
the existing Windows/Linux core suite. Validate the embedded UI in the actual
ChatGPT client before claiming it works there. Installation alone is not remote
connectivity. Tunnel access, target computer, and native renderer embedding remain
explicit deployment/compatibility checks rather than assumed capabilities.

## References

- [Programming workflow diagram](personal-arena-plugin/workflow.html)
- [Implementation tasks](../plans/2026-10-24-personal-arena-plugin.md)
- [MCP UI resources and iframe policy](https://developers.openai.com/plugins/build/chatgpt-ui)
- [Private tunnel requirements](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [Official Python MCP SDK runtime](https://github.com/modelcontextprotocol/python-sdk/blob/main/pyproject.toml)

The diagram shows proposed development work, not a deployed plugin or user flow.
