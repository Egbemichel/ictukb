"""Index writer: hash-based change detection, embedding, upsert and orphan removal."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import psycopg

from .chunking import Chunk, chunk_markdown
from .config import Settings, get_settings
from .content import ContentDoc
from .db import get_meta, set_meta, vec_literal
from .embedding import Embedder
from .util import approx_tokens, sha256

DOC_COLUMNS = [
    "title", "category", "subcategory", "program_level", "department", "language", "source_type",
    "source_url", "attachments", "academic_year", "semester", "valid_from", "valid_until",
    "freshness_tier", "status", "last_verified", "verified_by", "owner", "tags", "related",
    "origin", "origin_ref", "max_age_days",
]


@dataclass
class IndexDoc:
    id: str
    meta: dict
    chunks: list[Chunk]
    origin: str = "git"
    origin_ref: str | None = None
    max_age_days: int | None = None
    keep_verified_on_unchanged: bool = False
    content_hash: str = field(init=False)

    def __post_init__(self) -> None:
        self.content_hash = sha256(self.meta["title"] + "\x1f" + "\x1e".join(c.content for c in self.chunks))

    def row(self) -> dict:
        m = self.meta
        return {
            "title": m["title"], "category": m["category"], "subcategory": m.get("subcategory"),
            "program_level": m.get("program_level") or ["all"], "department": m.get("department"),
            "language": m.get("language", "en"), "source_type": m["source_type"],
            "source_url": m.get("source_url"), "attachments": json.dumps(m.get("attachments") or []),
            "academic_year": m.get("academic_year"), "semester": m.get("semester"),
            "valid_from": m.get("valid_from"), "valid_until": m.get("valid_until"),
            "freshness_tier": m["freshness_tier"], "status": m["status"],
            "last_verified": m["last_verified"], "verified_by": m.get("verified_by"),
            "owner": m["owner"], "tags": m.get("tags") or [], "related": m.get("related") or [],
            "origin": self.origin, "origin_ref": self.origin_ref, "max_age_days": self.max_age_days,
        }


@dataclass
class IndexReport:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    skipped: int = 0

    @property
    def changed(self) -> int:
        return self.inserted + self.updated + self.deleted

    def __str__(self) -> str:
        return (f"inserted={self.inserted} updated={self.updated} unchanged={self.unchanged} "
                f"deleted={self.deleted} skipped_not_eligible={self.skipped}")


def build_index_doc(doc: ContentDoc, settings: Settings | None = None) -> IndexDoc:
    """Turn a validated Markdown document, with its extracted attachment text, into index units."""
    settings = settings or get_settings()
    title = doc.meta["title"]
    chunks = chunk_markdown(title, doc.body)
    for att in doc.meta.get("attachments") or []:
        description = att["description"]
        chunks.append(Chunk("Attachment", f"{title} | Attachment ({att['kind']})\n\n{description}", "attachment"))
        text_file = att.get("text_file")
        if text_file and (settings.root / text_file).exists():
            text = (settings.root / text_file).read_text(encoding="utf-8")
            chunks.extend(chunk_markdown(f"{title} - {description}", text, source="attachment"))
    return IndexDoc(id=doc.id, meta=doc.meta, chunks=chunks)


def ensure_embedding_model(conn: psycopg.Connection, embedder: Embedder) -> None:
    stored = get_meta(conn, "embedding_model")
    if stored is None:
        set_meta(conn, "embedding_model", embedder.name)
        conn.commit()
    elif stored != embedder.name:
        raise RuntimeError(
            f"The index was built with '{stored}' but the configured model is '{embedder.name}'. "
            "Run 'ictkb reindex' to re-embed all chunks with the new model."
        )


def _upsert(conn: psycopg.Connection, embedder: Embedder, d: IndexDoc, force: bool) -> str:
    existing = conn.execute("SELECT content_hash FROM documents WHERE id = %s", (d.id,)).fetchone()
    row = d.row()
    if existing and existing["content_hash"] == d.content_hash and not force:
        cols = [c for c in DOC_COLUMNS if not (d.keep_verified_on_unchanged and c == "last_verified")]
        assignments = ", ".join(f"{c} = %({c})s" for c in cols)
        conn.execute(f"UPDATE documents SET {assignments} WHERE id = %(id)s", {**row, "id": d.id})
        return "unchanged"

    columns = ["id", *DOC_COLUMNS, "content_hash", "updated_at"]
    placeholders = ", ".join(f"%({c})s" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != "id")
    conn.execute(
        f"INSERT INTO documents ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT (id) DO UPDATE SET {updates}",
        {**row, "id": d.id, "content_hash": d.content_hash, "updated_at": datetime.now(timezone.utc)},
    )
    conn.execute("DELETE FROM chunks WHERE document_id = %s", (d.id,))
    if d.chunks:
        vectors = embedder.embed_documents([c.content for c in d.chunks])
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (document_id, chunk_index, heading_path, source, content, token_count, embedding) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s::vector)",
                [
                    (d.id, i, c.heading_path, c.source, c.content, approx_tokens(c.content), vec_literal(v))
                    for i, (c, v) in enumerate(zip(d.chunks, vectors, strict=True))
                ],
            )
    return "updated" if existing else "inserted"


def run_index(
    conn: psycopg.Connection,
    embedder: Embedder,
    docs: list[IndexDoc],
    origin: str,
    origin_ref: str | None = None,
    statuses: list[str] | None = None,
    prune: bool = True,
    force: bool = False,
) -> IndexReport:
    """Upsert eligible documents and, when pruning, delete documents of the same origin that vanished."""
    statuses = statuses or get_settings().allowed_statuses
    ensure_embedding_model(conn, embedder)
    report = IndexReport()
    eligible: list[IndexDoc] = []
    for d in docs:
        if d.meta["status"] in statuses:
            eligible.append(d)
        else:
            report.skipped += 1
    for d in eligible:
        outcome = _upsert(conn, embedder, d, force)
        setattr(report, outcome, getattr(report, outcome) + 1)
    if prune:
        keep = [d.id for d in eligible]
        if origin_ref is None:
            cur = conn.execute("DELETE FROM documents WHERE origin = %s AND id <> ALL(%s)", (origin, keep))
        else:
            cur = conn.execute(
                "DELETE FROM documents WHERE origin = %s AND origin_ref = %s AND id <> ALL(%s)",
                (origin, origin_ref, keep),
            )
        report.deleted = cur.rowcount
    conn.commit()
    return report


def reindex_all(conn: psycopg.Connection, embedder: Embedder, batch: int = 96) -> int:
    """Re-embed every stored chunk with the configured model and record the model name."""
    rows = conn.execute("SELECT id, content FROM chunks ORDER BY id").fetchall()
    for i in range(0, len(rows), batch):
        part = rows[i:i + batch]
        vectors = embedder.embed_documents([r["content"] for r in part])
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE chunks SET embedding = %s::vector WHERE id = %s",
                [(vec_literal(v), r["id"]) for r, v in zip(part, vectors, strict=True)],
            )
    set_meta(conn, "embedding_model", embedder.name)
    conn.commit()
    return len(rows)


def record_run(conn: psycopg.Connection, source: str, started: datetime, changed: int, status: str,
               error: str | None = None) -> None:
    conn.execute(
        "INSERT INTO ingestion_runs (source, started_at, finished_at, docs_changed, status, error) "
        "VALUES (%s, %s, now(), %s, %s, %s)",
        (source, started, changed, status, error),
    )
    conn.commit()
