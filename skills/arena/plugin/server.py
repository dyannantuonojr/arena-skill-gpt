"""Personal Arena MCP server. Optional locked Python 3.11+ environment."""
import argparse
import asyncio
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp.server import MCPServer
from mcp.server.apps import Apps, ResourceCsp
from mcp.server.auth.settings import AuthSettings
from mcp.types import ToolAnnotations
from arena_runner import ArenaRunner
from arena_service import ArenaService

UI_URI = 'ui://arena/v1.html'


def create_server(service, owner_policy=None):
    auth = None
    if owner_policy:
        auth = AuthSettings(issuer_url=owner_policy.issuer, resource_server_url=owner_policy.audience,
                            required_scopes=['arena'], validate_token_resource=True)
    apps = Apps()
    apps.add_html_resource(UI_URI, Path(__file__).with_name('ui').joinpath('index.html').read_text(encoding='utf-8'),
                           title='Arena tree', prefers_border=True, csp=ResourceCsp(connect_domains=[], resource_domains=[]))
    server = MCPServer('Personal Arena', version='1.0.0', token_verifier=owner_policy, auth=auth, extensions=[apps],
                       instructions='Open Arena to enter a question and optional grading guidance. Start only on an explicit run request or Start action. Reading, discovery and reconnects do not start workers.')

    async def invoke(method, *args):
        try:
            return await asyncio.to_thread(method, *args)
        except Exception:
            # Native SDK tool errors must not expose host paths, account details,
            # model logs, or filesystem diagnostic content.
            raise ValueError('Arena request could not be completed. Check the run ID, input, readiness, or host operator diagnostics.') from None

    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True, idempotentHint=True)

    @server.tool(annotations=read, meta={'ui': {'resourceUri': UI_URI}})
    async def open_arena(run_id: str | None = None) -> dict:
        """Open the Arena tree and question form. Does not start workers."""
        return await invoke(service.open_arena, run_id)

    @server.tool(annotations=write)
    async def start_run(question: str, request_id: str, guidance: str = '') -> dict:
        """Start 16 fixed answers, 15 judgments and 2 finalist packages using the owner's Codex account. Requires an explicit run request. Retry with the same request_id and identical inputs."""
        return await invoke(service.start_run, question, guidance, request_id)

    @server.tool(annotations=read)
    async def get_run_status(run_id: str) -> dict:
        """Read progress without resuming or changing workers."""
        return await invoke(service.get_run_status, run_id)

    @server.tool(annotations=read)
    async def get_answer(run_id: str, answer_id: str) -> dict:
        """Read a frozen answer and its verified hash."""
        return await invoke(service.get_answer, run_id, answer_id)

    @server.tool(annotations=read)
    async def get_finalist_package(run_id: str, answer_id: str) -> dict:
        """Read a validated finalist guide and inert native Archify geometry."""
        return await invoke(service.get_finalist_package, run_id, answer_id)

    @server.tool(annotations=write)
    async def stop_run(run_id: str) -> dict:
        """Cancel only the specified current run when the owner asks to stop it."""
        return await invoke(service.stop_run, run_id)

    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transport', choices=('stdio', 'streamable-http'), default='stdio')
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--data-dir', type=Path, default=Path.home() / '.arena' / 'plugin-runs')
    parser.add_argument('--repo-root', type=Path)
    args = parser.parse_args(argv)
    owner = None
    if args.transport == 'streamable-http':
        from plugin.auth import OwnerVerifier
        owner = OwnerVerifier(os.environ.get('ARENA_OAUTH_ISSUER', ''), os.environ.get('ARENA_OAUTH_AUDIENCE', ''),
                              os.environ.get('ARENA_OWNER_SUBJECT', ''), jwks_url=os.environ.get('ARENA_OAUTH_JWKS_URL'))
    runner = ArenaRunner(args.data_dir, repo_root=args.repo_root)
    service = ArenaService(args.data_dir, runner)
    server = create_server(service, owner)
    try:
        if args.transport == 'stdio':
            server.run(transport='stdio')
        else:
            server.run(transport='streamable-http', host='127.0.0.1', port=args.port,
                       stateless_http=True, json_response=True, max_request_body_size=128 * 1024)
    finally:
        runner.stop()


if __name__ == '__main__':
    main()
