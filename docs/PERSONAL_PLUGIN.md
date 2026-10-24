# Personal Arena MCP plugin

The optional plugin adds a tree interface and six MCP tools to Arena. Core Arena
still works through `arena_web.py`. Opening the plugin never starts a tournament.
Enter a question, optionally enter grading guidance, then press Start Arena.
Every answer can be selected in the tree or Find answer menu. Both finalists have
Implementation and Archify tabs. There is no mandatory planning step.

## Prepare this computer

Use Python 3.11+ for the optional official MCP SDK runtime, Node 18+, a supported
installed browser for Archify validation, and Codex signed in using ChatGPT.

```bash
python skills/arena/plugin/setup_runtime.py
python skills/arena/plugin/launch.py --help
```

Setup explicitly installs the locked dependencies under
`~/.arena/plugin-runtime`; it starts no server or model jobs. To use another
prepared runtime, set `ARENA_PLUGIN_PYTHON` to its Python executable. The core
app keeps its Python 3.8+ minimum and has no MCP dependency.

The root portable `plugin.json` and `mcp.json` define a local stdio plugin.
Install this checkout as a local plugin in a supporting client. The MCP launcher
uses the host-provided `PLUGIN_ROOT` and the prepared runtime. Installing a local
plugin does not make ChatGPT on another device reach this computer.

For manual stdio configuration, launch the absolute path to
`skills/arena/plugin/launch.py` with Python. Reserve stdout for MCP. Tools are
`open_arena`, `start_run`, `get_run_status`, `get_answer`,
`get_finalist_package`, and `stop_run`.

## Private remote connection

The remote HTTP server binds to 127.0.0.1 on port 8768. Keep the existing Arena
viewer on loopback; do not forward its port or change its Host/Origin checks.

Before starting remote HTTP, configure these environment variables locally:

| Name | Required value |
| --- | --- |
| `ARENA_OAUTH_ISSUER` | Trusted HTTPS OAuth issuer |
| `ARENA_OAUTH_AUDIENCE` | Exact HTTPS resource URL identifying this MCP service |
| `ARENA_OAUTH_JWKS_URL` | Trusted HTTPS issuer JWKS URL |
| `ARENA_OWNER_SUBJECT` | Your immutable OAuth subject, not an email guess |

The issuer must support the ChatGPT OAuth flow and issue RS256 access tokens for
this audience with scope `arena`. The server validates signature, issuer,
audience, expiry, issue time, scope and the one configured subject. A model tool
argument cannot select an identity. Missing configuration fails closed. This
package is a resource server, not an OAuth account/authorization provider.

```bash
python skills/arena/plugin/launch.py --transport streamable-http --port 8768
```

Run that command only after configuring the approved host. Use
`--data-dir PATH` for a dedicated owner run directory and `--repo-root PATH` for
committed repository evidence. Default plugin runs live in `~/.arena/plugin-runs`
and do not reuse a separately running web app's active run state.

Prefer an OpenAI Secure MCP Tunnel that reaches `http://127.0.0.1:8768/mcp`.
The tunnel has separate Platform access requirements and a runtime API key; it
does not authenticate Codex model workers and does not automatically enforce one
person's identity inside a shared workspace. Keep owner OAuth enabled. Configure
ChatGPT's custom MCP connection to use the approved tunnel and issuer. Keep
secrets, owner subject, tunnel IDs and private configuration out of Git and chat.

Do not use the stdio transport without its local trust boundary as an
unauthenticated remote server. A public HTTPS/OAuth deployment is a separate
choice, not an automatic fallback. The bundled manifest does not create a
tunnel, install a Windows startup service, or connect your account automatically.

## Interface and validation

The MCP Apps resource uses a versioned URI and the standard JSON-RPC bridge.
Native Archify SVG geometry is extracted with active content and remote resource
loads removed, then displayed in the component directly. This avoids nested
iframe and localhost dependencies. The existing standalone native HTML diagrams
retain the full Archify viewer. The embedded geometry view provides the tree's
pan/zoom and answer navigation; it does not include every standalone Archify
export/theme/animation control.

Run the core suite with `python -m unittest discover -s tests`. In the prepared
plugin runtime run the same suite; SDK protocol and authentication cases run
there instead of skipping. `python tests/serve_plugin_fixture.py` explicitly
starts a labeled loopback software fixture for browser QA, with no model calls.
It is not the remote server and must not be exposed or used for real tasks.

Local SDK/fixture tests establish implementation behavior. Actual ChatGPT
discovery, owner-only access, and UI compatibility must also be verified after
connection. Never label a remote installation ready from fixture results alone.

## Retries, recovery and rollback

A start request binds exact inputs to a durable request ID before launch. Retry
the same ID and inputs after a lost response; changed inputs for that ID are
rejected. One active/interrupted reservation blocks another start. Reconnecting
does not resume work. Stop accepts only the current owned run ID.

If a host crash leaves an interrupted reservation, stop/reap any surviving owned
worker processes and inspect the saved run before operator recovery. Do not
delete the reservation database or generate fresh request IDs to bypass it.
No remote recovery or arbitrary process-management tool is exposed.

To roll back the optional plugin, disconnect it in the client and stop its own
MCP/tunnel processes. Keep the run directory and SQLite reservation database to
preserve results and duplicate-start protection. The loopback Arena app and all
previous saved runs remain independently usable. Installing the plugin does not
change Codex sign-in or add a model API billing account.

## Official references

- [Plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [MCP UI resources](https://developers.openai.com/plugins/build/chatgpt-ui)
- [Private tunnel setup](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [Custom MCP connection](https://developers.openai.com/api/docs/guides/custom-mcp-server)


## Grudge Match in the same plugin

Use the **Arena / Grudge Match** toggle above the question in the same UI. The server also exposes **Open Grudge Match** directly, with the question above optional rubric guidance. Its six jobs produce a normal answer, independent peer review, synthesis, an evidence report covering all three, an independent scored comparison, and Archify for the winner only. Opening it does not start workers. Existing Arena tools are unchanged. See [Grudge Match](GRUDGE_MATCH.md) for usage and output IDs. Refresh the connected plugin tools after upgrading the server to discover the new tools.


## Supporting-file uploads

Use **Attach files** below the question in either mode. It accepts XLSX/CSV, PDF, DOCX, TXT and Markdown, with preview/remove controls. All workers use the same frozen run copies. Uploading never starts a run; job counts stay33/6. Refresh the plugin after installing the updated locked document parsers. See [supporting-document details](SUPPORTING_DOCUMENTS.md).
