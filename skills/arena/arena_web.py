"""Loopback-only HTTP entry point for the Arena viewer (Python standard library)."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import shutil
import threading
import time
from urllib.parse import unquote, urlsplit

from arena_view import export_view

MAX_BODY = 128 * 1024


def _public(value):
    """Remove common credential formats from runner diagnostics."""
    if isinstance(value, dict):
        return {key: _public(item) for key, item in value.items()
                if str(key).lower() not in ('token', 'access_token', 'refresh_token', 'api_key', 'authorization')}
    if isinstance(value, list):
        return [_public(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r'(?i)(bearer\s+)\S+', r'\1[redacted]', value)
        return re.sub(r'\bsk-[A-Za-z0-9_-]+', '[redacted]', value)
    return value


class ArenaHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, data_root, port, runner):
        self.data_root = Path(data_root).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self.token = secrets.token_urlsafe(32)
        self.action_lock = threading.Lock()
        self.capability_lock = threading.Lock()
        self.capability_cache = None
        self.capability_time = 0
        self.welcome_root = self.data_root / '.welcome'
        if self.welcome_root.is_symlink():
            raise ValueError('Unsafe welcome directory')
        self.welcome_root.mkdir(exist_ok=True)
        if self.welcome_root.resolve() != self.welcome_root.absolute():
            raise ValueError('Unsafe welcome directory')
        for name in ('rubric.md', 'index.html', 'index.state.json'):
            if (self.welcome_root / name).is_symlink():
                raise ValueError('Unsafe welcome file')
        shutil.copyfile(str(Path(__file__).with_name('rubric.md')), str(self.welcome_root / 'rubric.md'))
        export_view({'dir': str(self.welcome_root), 'agents': {}, 'rounds': [], 'mode': 'select'},
                    self.welcome_root / 'index.html')
        super().__init__(('127.0.0.1', port), ArenaHandler)

    def capabilities(self):
        with self.capability_lock:
            if self.capability_cache is None or time.monotonic() - self.capability_time > 5:
                try:
                    self.capability_cache = _public(self.runner.capabilities())
                except Exception:
                    self.capability_cache = {'ready': False, 'error': 'Runtime availability check failed.'}
                self.capability_time = time.monotonic()
            return dict(self.capability_cache)

    def server_close(self):
        try:
            self.runner.stop()
        except Exception:
            # A cancellation failure must not keep the listening socket open.
            pass
        finally:
            super().server_close()


class ArenaHandler(BaseHTTPRequestHandler):
    server_version = 'ArenaLocal/1.0'

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def parse_request(self):
        if not super().parse_request():
            return False
        # Apply the DNS-rebinding guard even to unsupported HTTP methods.
        if not self._host():
            self._reply(403, {'error': 'Invalid local host.'})
            return False
        return True

    def log_message(self, format, *args):
        # Task text, tokens and request paths never enter access logs.
        pass

    def _reply(self, status, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _host(self):
        hosts = self.headers.get_all('Host', [])
        port = self.server.server_port
        return len(hosts) == 1 and hosts[0] in ('127.0.0.1:%d' % port, 'localhost:%d' % port)

    def _guard(self, mutation=False):
        if not self._host():
            self._reply(403, {'error': 'Invalid local host.'})
            return False
        if mutation:
            origins = self.headers.get_all('Origin', [])
            tokens = self.headers.get_all('X-Arena-Token', [])
            expected = 'http://' + self.headers['Host']
            if len(origins) != 1 or origins[0] != expected or len(tokens) != 1 or not tokens[0].isascii() or not hmac.compare_digest(tokens[0], self.server.token):
                self._reply(403, {'error': 'Local request authorization required.'})
                return False
        return True

    def do_GET(self):
        if not self._guard():
            return
        path = urlsplit(self.path).path
        if path == '/api/config':
            self._reply(200, {'token': self.server.token, 'capabilities': self.server.capabilities()})
        elif path == '/api/status':
            try:
                result = _public(self.server.runner.status())
                result['capabilities'] = self.server.capabilities()
                self._reply(200, result)
            except Exception:
                self._reply(500, {'error': 'Unable to read run status.'})
        elif path.startswith('/api/'):
            self._reply(404, {'error': 'Unknown endpoint.'})
        else:
            self._static(path)

    def do_HEAD(self):
        self.do_GET()

    def do_OPTIONS(self):
        if self._guard():
            self._reply(405, {'error': 'Method not allowed.'})

    def do_POST(self):
        if not self._guard(mutation=True):
            return
        path = urlsplit(self.path).path
        if path not in ('/api/run', '/api/stop'):
            self._reply(404, {'error': 'Unknown endpoint.'})
            return
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            self._reply(400, {'error': 'A JSON body with a content length is required.'})
            return
        try:
            length = int(self.headers['Content-Length'])
            if length < 0 or length > MAX_BODY:
                self._reply(413, {'error': 'Request body too large.'})
                return
            if self.headers.get_content_type() != 'application/json':
                self._reply(415, {'error': 'Expected application/json.'})
                return
            body = json.loads(self.rfile.read(length).decode('utf-8'))
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            self._reply(400, {'error': 'Invalid JSON body.'})
            return
        if path == '/api/run':
            task, rubric = body.get('task'), body.get('rubric', '')
            agents, wave = body.get('agents', 16), body.get('wave', 3)
            if not isinstance(task, str) or not task.strip() or not isinstance(rubric, str) or type(agents) is not int or agents != 16 or type(wave) is not int or not 1 <= wave <= 3:
                self._reply(400, {'error': 'Provide a nonempty task, text rubric, 16 agents and wave size from 1 to 3.'})
                return
        with self.server.action_lock:
            try:
                if path == '/api/run':
                    if self.server.runner.status().get('status') == 'running':
                        self._reply(409, {'error': 'An Arena run is already active.'})
                        return
                    result = self.server.runner.start(task=task, rubric=rubric, agents=agents, wave=wave)
                else:
                    result = self.server.runner.stop()
                self._reply(200, _public(result))
            except (ValueError, TypeError):
                self._reply(400, {'error': 'Invalid run request.'})
            except RuntimeError:
                self._reply(409 if self.server.runner.status().get('status') == 'running' else 503,
                            {'error': 'Run unavailable. Check local runtime readiness.'})
            except Exception:
                self._reply(500, {'error': 'Unable to update the run.'})

    def _static(self, raw_path):
        path = unquote(raw_path)
        # Permit only the generated viewer and its exported diagram assets.
        if '\\' in path or '\x00' in path or any(part in ('.', '..') for part in path.split('/')):
            self._reply(404, {'error': 'File not found.'})
            return
        match = re.fullmatch(r'/runs/([A-Za-z0-9_-]+)/viewer/(.*)', path)
        if match:
            root = self.server.data_root / match[1] / 'viewer'
            relative = match[2]
        else:
            root = self.server.welcome_root
            relative = 'index.html' if path == '/' else path.lstrip('/')
        allowed = relative in ('index.html', 'index.state.json') or re.fullmatch(r'finalists/[A-Za-z0-9_-]+/diagram\.html', relative)
        target = root / relative
        try:
            resolved = target.resolve(strict=True)
            resolved.relative_to(self.server.data_root)
            resolved.relative_to(root.absolute())
            if not allowed or resolved != target.absolute() or not resolved.is_file():
                raise ValueError()
            current = target
            while current != self.server.data_root:
                if current.is_symlink():
                    raise ValueError()
                current = current.parent
            content = resolved.read_bytes()
        except (OSError, ValueError, RuntimeError):
            self._reply(404, {'error': 'File not found.'})
            return
        mime = 'application/json; charset=utf-8' if relative.endswith('.json') else 'text/html; charset=utf-8'
        self._reply(200, content, mime)


def make_server(data_root, port=8767, runner=None, codex=None, node=None, repo_root=None):
    if runner is None:
        from arena_runner import ArenaRunner
        runner = ArenaRunner(data_root, codex=codex, node=node, repo_root=repo_root)
    return ArenaHTTPServer(data_root, port, runner)


create_server = make_server


def main(argv=None):
    parser = argparse.ArgumentParser(description='Serve Arena on the loopback interface.')
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--data-dir', type=Path, default=Path.home() / '.arena' / 'runs')
    parser.add_argument('--codex')
    parser.add_argument('--node')
    parser.add_argument('--repo-root', type=Path, help='local Git working tree for validating repository evidence')
    parser.add_argument('--open-run', help='show a saved run without launching workers')
    args = parser.parse_args(argv)
    server = make_server(args.data_dir, args.port, codex=args.codex, node=args.node, repo_root=args.repo_root)
    if args.open_run:
        try:
            server.runner.restore(args.open_run)
        except Exception:
            server.server_close()
            raise
    print('http://127.0.0.1:%d/' % server.server_port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
