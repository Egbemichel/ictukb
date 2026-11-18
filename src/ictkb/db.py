"""Database access: connections, the API connection pool, migrations, vector literals."""

from __future__ import annotations

from collections.abc import Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

_pool: ConnectionPool | None = None


def connect(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url, row_factory=dict_row, autocommit=autocommit, prepare_threshold=None)


def open_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url,
            min_size=1,
            max_size=5,
            max_idle=240,
            kwargs={"row_factory": dict_row, "prepare_threshold": None},  # pooled Neon endpoints use PgBouncer
            check=ConnectionPool.check_connection,
            open=False,
        )
        _pool.open(wait=True, timeout=30)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def vec_literal(vector: Sequence[float]) -> str:
    """Render a vector in the textual form accepted by pgvector."""
    return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply pending SQL files from db/migrations in lexical order. Returns the applied names."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    done: list[str] = []
    for path in sorted(get_settings().migrations_dir.glob("*.sql")):
        if path.name in applied:
            continue
        conn.execute(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
        done.append(path.name)
    conn.commit()
    return done


def get_meta(conn: psycopg.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM kb_meta WHERE key = %s", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: psycopg.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO kb_meta (key, value) VALUES (%s, %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        (key, value),
    )
