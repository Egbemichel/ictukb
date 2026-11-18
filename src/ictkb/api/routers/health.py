from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ... import __version__
from ...config import get_settings
from ...db import get_meta, open_pool

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health")
def health() -> dict:
    s = get_settings()
    try:
        with open_pool().connection() as conn:
            docs = conn.execute("SELECT count(*) AS n FROM documents").fetchone()["n"]
            chunks = conn.execute("SELECT count(*) AS n FROM chunks").fetchone()["n"]
            model = get_meta(conn, "embedding_model")
    except Exception as exc:
        raise HTTPException(503, f"Database unavailable: {type(exc).__name__}") from exc
    return {"status": "ok", "version": __version__, "environment": s.kb_env,
            "documents": docs, "chunks": chunks, "embedding_model": model}
