import importlib.util
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'arena'))
SDK = importlib.util.find_spec('jwt') is not None and importlib.util.find_spec('mcp') is not None


@unittest.skipUnless(SDK, 'Install locked optional plugin runtime')
class OwnerAuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        from plugin.auth import OwnerVerifier
        self.verifier = OwnerVerifier('https://issuer.example/', 'https://arena.example/mcp', 'owner-123', public_key=self.key.public_key())

    def token(self, **updates):
        import jwt
        claims = {'iss': 'https://issuer.example/', 'aud': 'https://arena.example/mcp', 'sub': 'owner-123', 'exp': int(time.time()) + 60, 'iat': int(time.time()), 'scope': 'arena'}
        claims.update(updates)
        return jwt.encode(claims, self.key, algorithm='RS256')

    async def test_owner_passes_and_other_identities_fail(self):
        self.assertIsNotNone(await self.verifier.verify_token(self.token()))
        for changes in ({'sub': 'another'}, {'exp': 1}, {'aud': 'other'}, {'iss': 'https://evil.example/'}, {'scope': 'other'}):
            self.assertIsNone(await self.verifier.verify_token(self.token(**changes)))
        self.assertIsNone(await self.verifier.verify_token(''))
        self.assertIsNone(await self.verifier.verify_token('untrusted'))

    async def test_config_fails_closed(self):
        from plugin.auth import OwnerVerifier
        with self.assertRaises(ValueError):
            OwnerVerifier('', '', '')

    async def test_http_boundary_rejects_before_tool_execution(self):
        import httpx2
        import tempfile
        from plugin.server import create_server
        from arena_service import ArenaService
        from test_service import FakeRunner
        with tempfile.TemporaryDirectory() as root:
            runner = FakeRunner()
            server = create_server(ArenaService(root, runner), self.verifier)
            app = server.streamable_http_app(stateless_http=True, json_response=True)
            async with app.router.lifespan_context(app):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url='http://127.0.0.1:8768') as client:
                    payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}}}
                    headers = {'Accept': 'application/json, text/event-stream'}
                    for token in ('', self.token(sub='not-owner'), self.token(aud='wrong')):
                        response = await client.post('/mcp', json=payload, headers=dict(headers, **({'Authorization': 'Bearer ' + token} if token else {})))
                        self.assertEqual(response.status_code, 401)
                    response = await client.post('/mcp', json=payload, headers=dict(headers, Authorization='Bearer ' + self.token()))
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(runner.starts, [])


if __name__ == '__main__':
    unittest.main()
