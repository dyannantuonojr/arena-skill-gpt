"""Real HTTP round trips for the loopback Arena entry point."""
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'arena'))
from arena_web import make_server, MAX_BODY
import arena_web as W


class FakeRunner:
    def __init__(self):
        self.current = {'status': 'idle'}
        self.starts = []
        self.stops = 0
        self.checks = 0

    def capabilities(self):
        self.checks += 1
        return {'ready': True, 'auth': 'ready', 'codex': 'available'}

    def status(self):
        return dict(self.current)

    def start(self, **kwargs):
        self.starts.append(kwargs)
        self.current = {'id': 'example', 'status': 'running', 'phase': 'answers',
                        'completed': 0, 'total': 33, 'active': [],
                        'viewer_url': '/runs/example/viewer/index.html'}
        return dict(self.current)

    def stop(self):
        self.stops += 1
        self.current['status'] = 'cancelled'
        return dict(self.current)


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.runner = FakeRunner()
        self.server = make_server(self.root, port=0, runner=self.runner)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = '127.0.0.1:%d' % self.server.server_port
        self.origin = 'http://' + self.host
        self.token = self.request('GET', '/api/config')[1]['token']

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        request_headers = {'Host': self.host}
        if method == 'POST':
            request_headers.update({'Origin': self.origin, 'X-Arena-Token': getattr(self, 'token', ''),
                                    'Content-Type': 'application/json'})
        request_headers.update(headers or {})
        if isinstance(body, dict):
            body = json.dumps(body)
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        data = response.read()
        status, response_headers = response.status, dict(response.getheaders())
        connection.close()
        if response_headers.get('Content-Type', '').startswith('application/json'):
            data = json.loads(data)
        return status, data, response_headers

    def test_welcome_and_config(self):
        status, html, headers = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'Arena tree', html)
        self.assertIn('charset=utf-8', headers['Content-Type'])
        self.assertIn('no-store', headers['Cache-Control'])
        status, config, headers = self.request('GET', '/api/config')
        self.assertTrue(config['capabilities']['ready'])
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        self.assertFalse((self.root / '.welcome' / 'arena.json').exists())
        self.assertEqual(self.request('GET', '/index.state.json')[0], 200)

    def test_run_status_duplicate_and_stop(self):
        task = 'Explain café architecture'
        status, run, _ = self.request('POST', '/api/run', {'task': task, 'rubric': 'Evidence'})
        self.assertEqual(status, 200)
        self.assertEqual(self.runner.starts[0]['task'], task)
        self.assertEqual(run['viewer_url'], '/runs/example/viewer/index.html')
        self.assertEqual(self.request('POST', '/api/run', {'task': 'Second'})[0], 409)
        self.assertEqual(len(self.runner.starts), 1)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.request('GET', '/api/status'), range(16)))
        self.assertTrue(all(item[0] == 200 and item[1]['status'] == 'running' for item in results))
        self.assertEqual(self.runner.checks, 1)
        self.assertEqual(self.request('POST', '/api/stop', {})[1]['status'], 'cancelled')
        self.assertEqual(self.runner.stops, 1)

    def test_simultaneous_start_and_readiness_refresh(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: self.request('POST', '/api/run', {'task': 'One run'}), range(4)))
        self.assertEqual(sorted(item[0] for item in responses), [200, 409, 409, 409])
        self.assertEqual(len(self.runner.starts), 1)
        self.runner.capabilities = lambda: {'ready': False, 'error': 'Sign in locally.'}
        self.server.capability_time = 0
        self.assertFalse(self.request('GET', '/api/status')[1]['capabilities']['ready'])

    def test_host_origin_and_nonce(self):
        for path in ('/', '/api/config', '/api/status', '/runs/example/viewer/index.html'):
            self.assertEqual(self.request('GET', path, headers={'Host': 'evil.test'})[0], 403)
        self.assertEqual(self.request('PUT', '/', headers={'Host': 'evil.test'})[0], 403)
        for headers in ({'Origin': 'https://evil.test'}, {'Origin': 'null'}, {'Origin': ''},
                        {'X-Arena-Token': ''}, {'X-Arena-Token': 'wrong'}, {'Host': 'localhost:1'}):
            self.assertEqual(self.request('POST', '/api/run', {'task': 'x'}, headers)[0], 403)
        self.assertEqual(self.runner.starts, [])
        self.assertEqual(self.request('GET', '/api/stop')[0], 404)
        self.assertEqual(self.request('GET', '/api/run')[0], 404)
        self.assertEqual(self.request('OPTIONS', '/api/run')[0], 405)

    def test_input_validation(self):
        for body in ({}, {'task': ' '}, {'task': 1}, {'task': 'x', 'rubric': []},
                     {'task': 'x', 'agents': 8}, {'task': 'x', 'agents': True},
                     {'task': 'x', 'wave': 0}, {'task': 'x', 'wave': 4}, {'task': 'x', 'wave': True}):
            self.assertEqual(self.request('POST', '/api/run', body)[0], 400)
        for body in ('{', '[]', 'null'):
            self.assertEqual(self.request('POST', '/api/run', body)[0], 400)
        self.assertEqual(self.request('POST', '/api/run', 'x' * (MAX_BODY + 1))[0], 413)
        self.assertEqual(self.request('POST', '/api/run', '{}', {'Content-Type': 'text/plain'})[0], 415)

    def test_only_exported_files_and_no_escape(self):
        viewer = self.root / 'example' / 'viewer'
        diagram = viewer / 'finalists' / 'a01' / 'diagram.html'
        diagram.parent.mkdir(parents=True)
        diagram.write_text('<html>native diagram</html>', encoding='utf-8')
        (viewer / 'index.html').write_text('Viewer', encoding='utf-8')
        (viewer / 'index.state.json').write_text('{}', encoding='utf-8')
        (viewer / 'secret.txt').write_text('secret', encoding='utf-8')
        self.assertEqual(self.request('GET', '/runs/example/viewer/index.html')[0], 200)
        self.assertEqual(self.request('GET', '/runs/example/viewer/index.state.json')[0], 200)
        self.assertIn(b'native diagram', self.request('GET', '/runs/example/viewer/finalists/a01/diagram.html')[1])
        for path in ('/runs/example/task.md', '/runs/example/arena.json', '/rubric.md',
                     '/runs/example/viewer/', '/runs/example/viewer/secret.txt',
                     '/runs/example/viewer/../task.md', '/runs/example/viewer/%2e%2e/task.md',
                     '/runs/example/viewer/finalists/a01/../../index.html',
                     '/runs/example/viewer/finalists/a01%5c..%5cindex.html'):
            self.assertEqual(self.request('GET', path)[0], 404, path)

    def test_symlinks_rejected(self):
        target = self.root / 'actual'
        target.mkdir()
        (target / 'index.html').write_text('outside', encoding='utf-8')
        run = self.root / 'linked'
        run.mkdir()
        try:
            (run / 'viewer').symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest('Symlink creation is unavailable on this Windows account')
        self.assertEqual(self.request('GET', '/runs/linked/viewer/index.html')[0], 404)

    def test_errors_do_not_echo_runner_exceptions(self):
        def fail(**kwargs):
            raise Exception('secret bearer abc sk-password')
        self.runner.start = fail
        status, result, _ = self.request('POST', '/api/run', {'task': 'x'})
        self.assertEqual(status, 500)
        self.assertNotIn('secret', json.dumps(result))


class WebStartupTests(unittest.TestCase):
    def test_repository_root_is_forwarded_from_operator_configuration(self):
        server = mock.Mock()
        server.server_port = 8767
        server.serve_forever.side_effect = KeyboardInterrupt
        with mock.patch.object(W, 'make_server', return_value=server) as factory:
            W.main(['--repo-root', 'example-repository'])
        self.assertEqual(factory.call_args.kwargs['repo_root'], Path('example-repository'))

    def test_open_run_restores_saved_status_without_starting_workers(self):
        server = mock.Mock()
        server.server_port = 8767
        server.serve_forever.side_effect = KeyboardInterrupt
        with mock.patch.object(W, 'make_server', return_value=server):
            W.main(['--port', '8767', '--open-run', 'saved-run'])
        server.runner.restore.assert_called_once_with('saved-run')
        server.runner.start.assert_not_called()
        server.server_close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
