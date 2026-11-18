"""Test fixtures. Integration tests need PostgreSQL with pgvector (set TEST_DATABASE_URL)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("KB_ROOT", str(ROOT))
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("KB_ENV", "staging")
# Hashed vectors are sparse, so their cosine similarities are lower than those of a trained model
os.environ.setdefault("MIN_SIMILARITY", "0.12")
os.environ.setdefault("REQUIRE_API_KEY", "true")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]


@pytest.fixture(scope="session")
def db_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture()
def conn(db_url):
    import psycopg
    from psycopg.rows import dict_row

    from ictkb.db import migrate

    connection = psycopg.connect(db_url, row_factory=dict_row)
    migrate(connection)
    connection.execute("TRUNCATE chunks, documents, api_keys, feedback, ingestion_runs, kb_meta CASCADE")
    connection.commit()
    yield connection
    connection.close()
