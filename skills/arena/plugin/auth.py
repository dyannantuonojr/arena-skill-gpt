"""Owner-only resource-server token verification. No token is logged or persisted."""
import asyncio
from urllib.parse import urlsplit
import jwt
from mcp.server.auth.provider import AccessToken


class OwnerVerifier:
    def __init__(self, issuer, audience, owner, jwks_url=None, public_key=None):
        for value in (issuer, audience):
            parsed = urlsplit(value)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Configure HTTPS issuer and resource audience')
        if not owner or not isinstance(owner, str):
            raise ValueError('Configure one immutable owner subject')
        if public_key is None:
            parsed = urlsplit(jwks_url or '')
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Configure trusted HTTPS JWKS URL')
        self.issuer, self.audience, self.owner = issuer, audience, owner
        self.public_key = public_key
        self.keys = jwt.PyJWKClient(jwks_url, timeout=5) if public_key is None else None

    async def verify_token(self, token):
        if not token or len(token) > 16384:
            return None
        try:
            key = self.public_key
            if key is None:
                key = (await asyncio.to_thread(self.keys.get_signing_key_from_jwt, token)).key
            claims = jwt.decode(token, key, algorithms=['RS256'], audience=self.audience,
                                issuer=self.issuer, options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']})
            scopes = claims.get('scope', '')
            if not isinstance(scopes, str) or claims['sub'] != self.owner or 'arena' not in scopes.split():
                return None
            return AccessToken(token=token, client_id=claims.get('azp') or 'arena-owner',
                               scopes=['arena'], expires_at=claims['exp'],
                               resource=self.audience, subject=self.owner)
        except (jwt.PyJWTError, ValueError, TypeError, OSError):
            return None
