"""Shared dependencies: database connection, API-key authentication, rate limiting, admin guard."""

from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from ..config import get_settings
from ..db import open_pool
from ..keys import hash_key

KEY_CACHE_TTL = 60.0
WINDOW = 60.0


@dataclass
class Caller:
    key_id: str | None
    owner: str
    limit: int
    ident: str


_key_cache: dict[str, tuple[float, Caller | None]] = {}
_hits: dict[str, deque[float]] = defaultdict(deque)


def get_conn():
    with open_pool().connection() as conn:
        yield conn


def _lookup(key: str) -> Caller | None:
    digest = hash_key(key)
    cached = _key_cache.get(digest)
    now = time.monotonic()
    if cached and now - cached[0] < KEY_CACHE_TTL:
        return cached[1]
    with open_pool().connection() as conn:
        row = conn.execute(
            "UPDATE api_keys SET last_used_at = now() WHERE key_hash = %s AND revoked_at IS NULL "
            "RETURNING id::text AS id, owner, rate_limit_per_min",
            (digest,),
        ).fetchone()
    caller = None
    if row:
        limit = row["rate_limit_per_min"] or get_settings().default_rate_limit_per_min
        caller = Caller(row["id"], row["owner"], limit, f"key:{row['id']}")
    _key_cache[digest] = (now, caller)
    return caller


def clear_key_cache() -> None:
    _key_cache.clear()


def authenticate(request: Request, x_api_key: str | None = Header(default=None)) -> Caller:
    settings = get_settings()
    if x_api_key:
        caller = _lookup(x_api_key)
        if caller is None:
            raise HTTPException(401, "Invalid or revoked API key")
    elif settings.require_api_key:
        raise HTTPException(401, "Missing X-API-Key header")
    else:
        host = request.client.host if request.client else "unknown"
        caller = Caller(None, "anonymous", settings.default_rate_limit_per_min, f"ip:{host}")

    now = time.monotonic()
    window = _hits[caller.ident]
    while window and now - window[0] > WINDOW:
        window.popleft()
    if len(window) >= caller.limit:
        retry = max(1, int(WINDOW - (now - window[0])))
        raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": str(retry)})
    window.append(now)
    return caller


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    expected = get_settings().admin_token
    if not expected:
        raise HTTPException(503, "Admin interface is disabled (ADMIN_TOKEN is not set)")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(403, "Invalid admin token")
