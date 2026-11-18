"""API key management. Keys are stored as SHA-256 hashes; the clear value is shown once."""

from __future__ import annotations

import secrets

import psycopg

from .util import sha256

PREFIX = "ictkb_"


def hash_key(key: str) -> str:
    return sha256(key)


def create_key(conn: psycopg.Connection, owner: str, rate_limit_per_min: int | None = None) -> tuple[str, str]:
    key = PREFIX + secrets.token_urlsafe(32)
    row = conn.execute(
        "INSERT INTO api_keys (owner, key_hash, rate_limit_per_min) VALUES (%s, %s, %s) RETURNING id",
        (owner, hash_key(key), rate_limit_per_min),
    ).fetchone()
    conn.commit()
    return str(row["id"]), key


def revoke_key(conn: psycopg.Connection, key_id: str) -> bool:
    cur = conn.execute(
        "UPDATE api_keys SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL", (key_id,)
    )
    conn.commit()
    return cur.rowcount > 0


def list_keys(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        "SELECT id::text, owner, rate_limit_per_min, created_at, last_used_at, revoked_at "
        "FROM api_keys ORDER BY created_at"
    ).fetchall()
