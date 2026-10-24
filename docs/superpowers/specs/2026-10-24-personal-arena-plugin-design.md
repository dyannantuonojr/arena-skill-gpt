# Personal Arena plugin: proposed design

Status: design for review; the remote plugin is not built or connected.

## Intent

Use Arena from the owner's ChatGPT/Codex conversation while the always-on computer
runs the existing signed-in Codex workers. Only the owner may connect. Keep the
question, optional grading guidance, fixed 16 answers, tree navigation, and both
required finalist implementation/Archify packages.

Interpretation of the latest conversation: use a skill and Archify to plan this
plugin first, and make planning followed by owner approval the finished plugin's
normal workflow. This interpretation can be corrected before implementation.

## Approaches

1. Recommended: a private MCP adapter beside Arena, reached through an OpenAI
   Secure MCP Tunnel if the owner's Platform/workspace has access. No inbound
   router port or public Arena web server. The tunnel requires its own runtime
   key and permissions; it does not replace the existing Codex sign-in.
2. Alternative: an HTTPS MCP endpoint with owner-only OAuth. This introduces
   public ingress and authentication operations; it is a separate deployment
   choice, not an automatic fallback.
3. Local stdio alone is useful for testing or Codex on that computer, but does not
   by itself connect ChatGPT on other devices to the always-on computer.

The owner selected personal-only access. Transport availability has not yet been
verified; this document proposes option 1. No tunnel or network exposure has been
enabled.

## Proposed user journey

1. Ask the personal Arena plugin a question; grading guidance stays optional.
2. The skill prepares a concise plan, success criteria, and a proposed Archify
   workflow. Preparing or editing a plan never starts tournament workers.
3. Show the plan and diagram with the expected 33 worker jobs plus possible retry
   overhead. The owner can edit them or approve running this exact question and
   guidance. A plain acknowledgment to a different question is not run consent.
4. On explicit run approval, submit the stored plan ID and digest. The server
   checks owner identity, current plan digest, and an idempotency key. It returns a
   run ID promptly; the 33-job tournament continues outside the MCP request.
5. Read progress and results on demand. Each answer remains selectable in the
   tree, and both finalists retain Implementation and Archify views.
6. The owner can stop an active run. A reconnect, status read, or server restart
   never silently starts or resumes workers.

Archify renders the authored plan; it does not supply or verify the reasoning.
The planning diagram is separate from the tournament and cannot revise its frozen
answers, judges, or required finalist packages. It adds renderer work but no new
tournament competitor or judging job.

## Proposed implementation boundaries

- Add a small MCP adapter using a maintained MCP SDK. Reuse `ArenaRunner` for
  execution and the existing bundled Archify finalizer for diagrams. Keep remote
  protocol/auth code separate from the loopback viewer's Host/Origin/nonce rules.
- Provide narrowly scoped `prepare_plan`, `start_run`, `get_run_status`,
  `get_answer`, `get_finalist_package`, `get_run_view`, and `stop_run` tools. No
  arbitrary commands, filesystem paths, account credentials, or host management.
- Plan records contain exact question/guidance, diagram and guide references,
  creation time, version, and digest. Changing inputs invalidates start approval.
  Duplicate start requests return the original run ID without duplicate workers.
- Persist the start reservation and its stable run ID before launching workers,
  including the plan digest and idempotency key in run metadata. Reconcile a
  crash between reservation and worker launch without launching a second run;
  return the reserved run's actual or interrupted state. Retrying a request after
  process restart must preserve this property. Never auto-resume interrupted work.
- `stop_run(run_id)` must match the active owner-bound run before calling the
  current runner's cancellation method; a stale stop cannot cancel a newer run.
- Read historical runs through validated read-only storage. Do not use passive
  `restore()` for every remote read: it selects the runner's current run and is
  intentionally unavailable while another run is active.
- Give planning its own bounded renderer entry point or shared finalizer helper.
  The existing finalist finalizer requires tournament state and its job ledger;
  preparing a plan must not fabricate a tournament to satisfy those requirements.
- One active tournament, up to the existing three workers. Report busy rather
  than silently queueing an unlimited number of runs.
- Long-running work returns a run ID immediately and uses bounded status reads;
  it must not hold a tunnel request open for the tournament's duration.
- All remote calls require a verified owner-only connection. Bind authenticated
  identity to a configured immutable owner ID; never trust a model-supplied email
  or `owner=true`. Use OAuth subject validation if tunnel access cannot enforce
  that owner boundary. Fail closed until owner-only access is demonstrated.
- Keep credentials in the host's protected runtime configuration, outside Git,
  tool outputs and logs. The runner keeps using its existing Codex sign-in.
- Return structured results to ChatGPT. For the visual tree, implement an MCP UI
  resource backed by bounded tools, with self-contained generated assets. A
  localhost link is only an additional same-computer option: it does not work on
  a remote phone. Do not expose the existing loopback API to solve that problem.
- Reuse the tree's answer selection and zoom-preserving behavior. Adapt its data
  access to the MCP UI bridge; validate native nested Archify iframe compatibility
  in the target ChatGPT client before promising an embedded tree works.
- Bundle plugin instructions, MCP configuration, setup checks, and credited
  Archify sources. Publish generic configuration only, never the owner's private
  tunnel ID, identity configuration, answers, or secrets.

## Draft skill instructions

This is instruction copy for the future plugin, not an installed skill:

```markdown
---
name: personal-arena
description: Plan and run Arena on the owner's connected computer, with optional grading guidance, a visual plan, fixed-answer judging, and finalist implementation guides.
---

Use the connected Arena MCP tools. Preserve the owner's question and optional
grading guidance. Prepare a plan and an Archify workflow first; mark proposed
steps honestly. Show the exact proposed run and its 33-job count plus retry
overhead. Start only after the owner explicitly approves that plan and run.
Do not treat planning, reading results, opening the plugin, or reconnecting as
permission to start workers. If the owner changes the task or guidance, update
the plan before execution. Report the returned run ID and actual status; do not
claim completion from a diagram or a worker message. Preserve all frozen answers.
Make every answer readable and both finalist packages available. A request to
stop cancels the owned run. If the host, authentication, renderer, or UI is
unavailable, report that condition without inventing results or bypassing checks.
```

## Validation and rollout

Before deployment, test MCP discovery and tool calls with no model jobs; rejected
non-owner access; input/path boundaries; changed-plan and duplicate-start cases;
disconnect/restart behavior; cancellation; native diagram validation; and the
embedded tree's answer navigation and zoom across progress updates. Use labeled
software fixtures. Keep the existing full test suite passing.

After those pass, connect the owner's account and verify read-only discovery and
a labeled fixture in the actual ChatGPT client. A fresh real tournament is a
separate owner-authorized test that consumes Codex usage. Do not start it during
installation. Report the connection as ready only after actual discovery and
owner-only access tests pass.

Before enabling the connection, identify which always-on computer is the target,
verify private tunnel availability, and show the precise connection/access change
for approval. Installing the package alone does not establish remote connectivity.

## References

- [OpenAI custom MCP connection](https://developers.openai.com/api/docs/guides/custom-mcp-server)
- [Secure MCP Tunnel and prerequisites](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [MCP server and optional UI](https://developers.openai.com/plugins/build/mcp-server)
- [Proposed visual workflow](personal-arena-plugin/workflow.html)

The workflow depicts proposed behavior, not deployed capabilities.
