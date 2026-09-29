"""Who is asking: a guest, or a signed-in ComeMorocco user.

The mobile app sends the Supabase access token as `Authorization: Bearer …`.
It is verified here, never trusted as-is:

  - SUPABASE_JWT_SECRET set  → HS256 with the project's JWT secret
  - SUPABASE_URL set         → asymmetric keys from the project's JWKS endpoint

A missing token means a guest. An invalid or expired token also means a
guest — the request still gets an answer, just under guest limits — and is
logged, so a broken client shows up without locking anyone out of help.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt

from app.config import get_settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Caller:
    user_id: str | None = None

    @property
    def signed_in(self) -> bool:
        return self.user_id is not None


GUEST = Caller()


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def caller_from_authorization(header: str | None) -> Caller:
    if not header or not header.lower().startswith("bearer "):
        return GUEST
    token = header[7:].strip()
    settings = get_settings()
    try:
        if settings.supabase_jwt_secret:
            claims = jwt.decode(
                token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated"
            )
        elif settings.supabase_url:
            jwks = _jwks_client(settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json")
            key = jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, key.key, algorithms=["RS256", "ES256"], audience="authenticated")
        else:
            log.warning("bearer token received but no SUPABASE_JWT_SECRET / SUPABASE_URL is configured")
            return GUEST
    except jwt.PyJWTError as exc:
        log.info("ignoring invalid bearer token: %s", exc)
        return GUEST
    user_id = claims.get("sub")
    return Caller(user_id=user_id) if user_id else GUEST
