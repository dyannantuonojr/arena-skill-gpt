"""Optional runtime integration tests; SDK client talks to the real SDK server."""
import functools
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'arena'))
SDK = importlib.util.find_spec('mcp') is not None


@unittest.skipUnless(SDK, 'Install locked optional plugin runtime')
class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_grudge_tools_and_idle_resource(self):
        import anyio
        from mcp import ClientSession
        from plugin.server import create_server, GRUDGE_UI_URI
        from arena_service import ArenaService
        from grudge_match import GrudgeService
        from test_service import FakeRunner
        with tempfile.TemporaryDirectory() as root:
            original, grudge = FakeRunner(), FakeRunner()
            arena_service = ArenaService(Path(root)/'arena', original)
            server = create_server(arena_service, grudge_service=GrudgeService(Path(root)/'grudge', grudge))
            send_server, receive_server = anyio.create_memory_object_stream(10)
            send_client, receive_client = anyio.create_memory_object_stream(10)
            low = server._lowlevel_server
            async with anyio.create_task_group() as group:
                group.start_soon(functools.partial(low.run, receive_server, send_client, low.create_initialization_options()))
                async with ClientSession(receive_client, send_server) as client:
                    await client.initialize()
                    tools = (await client.list_tools()).tools
                    names = {t.name for t in tools}
                    self.assertIn('open_arena', names)
                    self.assertIn('open_grudge_match', names)
                    self.assertIn('start_grudge_match', names)
                    ui = (await client.read_resource(GRUDGE_UI_URI)).contents[0].text
                    self.assertIn('data-workflow="grudge"', ui)
                    self.assertLess(ui.index('id="task"'), ui.index('id="guidance"'))
                    self.assertLess(ui.index('id="guidance"'), ui.index('id="tree"'))
                    result = await client.call_tool('open_grudge_match', {})
                    self.assertFalse(result.is_error)
                    self.assertEqual(grudge.starts, [])
                    original.current = {'id': 'live', 'status': 'running'}
                    blocked = await client.call_tool('start_grudge_match', {'question': 'q', 'request_id': 'r'})
                    self.assertTrue(blocked.is_error)
                    self.assertEqual(grudge.starts, [])
                    original.current = {'id': None, 'status': 'idle'}
                    reserved = arena_service.start_run('interrupted question', '', 'interrupted')
                    original.current = {'id': None, 'status': 'idle'}
                    blocked = await client.call_tool('start_grudge_match', {'question': 'q', 'request_id': 'after-restart'})
                    self.assertTrue(blocked.is_error)
                    self.assertEqual(grudge.starts, [])
                group.cancel_scope.cancel()

    async def test_discovery_resources_and_calls_over_sdk_session(self):
        import anyio
        from mcp import ClientSession
        from plugin.server import create_server, UI_URI
        from arena_service import ArenaService
        from test_service import FakeRunner
        with tempfile.TemporaryDirectory() as root:
            runner = FakeRunner()
            server = create_server(ArenaService(root, runner))
            send_server, receive_server = anyio.create_memory_object_stream(10)
            send_client, receive_client = anyio.create_memory_object_stream(10)
            low = server._lowlevel_server
            async with anyio.create_task_group() as group:
                group.start_soon(functools.partial(low.run, receive_server, send_client, low.create_initialization_options()))
                async with ClientSession(receive_client, send_server) as client:
                    await client.initialize()
                    listed = await client.list_tools()
                    self.assertEqual({t.name for t in listed.tools}, {'open_arena', 'start_run', 'get_run_status', 'get_answer', 'get_finalist_package', 'stop_run'})
                    start = next(t for t in listed.tools if t.name == 'start_run')
                    self.assertFalse(start.annotations.read_only_hint)
                    resource = await client.read_resource(UI_URI)
                    self.assertEqual(resource.contents[0].mime_type, 'text/html;profile=mcp-app')
                    self.assertIn('Question', resource.contents[0].text)
                    opened = await client.call_tool('open_arena', {})
                    self.assertFalse(opened.is_error)
                    self.assertEqual(runner.starts, [])
                    begun = await client.call_tool('start_run', {'question': ' Exact question ', 'guidance': '', 'request_id': 'test-1'})
                    self.assertFalse(begun.is_error)
                    self.assertEqual(runner.starts[0][:2], (' Exact question ', ''))
                    await client.call_tool('start_run', {'question': ' Exact question ', 'guidance': '', 'request_id': 'test-1'})
                    self.assertEqual(len(runner.starts), 1)
                    invalid = await client.call_tool('get_run_status', {'run_id': '../private'})
                    self.assertTrue(invalid.is_error)
                group.cancel_scope.cancel()


if __name__ == '__main__':
    unittest.main()
