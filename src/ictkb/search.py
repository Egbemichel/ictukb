"""Hybrid retrieval: vector similarity and keyword match fused with reciprocal rank fusion."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import psycopg

from .cloud import delivery_url
from .config import get_settings
from .db import vec_literal
from .embedding import Embedder
from .util import is_stale

STOPWORDS = {
    "the", "and", "for", "are", "how", "what", "when", "where", "who", "can", "does", "do", "is", "my",
    "you", "your", "with", "that", "this", "from", "have", "will", "any", "there", "which",
    "les", "des", "une", "est", "sont", "pour", "dans", "que", "qui", "quels", "quel", "quelle",
    "comment", "puis", "aux", "par", "sur", "vous", "nous", "mes", "mon", "ses",
}
CANDIDATES = 40
RRF_K = 60


@dataclass
class Filters:
    category: str | None = None
    program_level: str | None = None
    language: str | None = None


@dataclass
class SearchOutcome:
    confidence: str  # high | low | none
    results: list[dict] = field(default_factory=list)


def build_tsquery(text: str) -> str:
    tokens = [t for t in re.findall(r"\w+", text.lower()) if len(t) > 2 and t not in STOPWORDS]
    seen: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
    return " | ".join(seen[:24]) if seen else "zzzznomatchzzzz"


def search(conn: psycopg.Connection, embedder: Embedder, query: str, top_k: int = 5,
           filters: Filters | None = None) -> SearchOutcome:
    settings = get_settings()
    filters = filters or Filters()
    clauses = [
        "d.status = ANY(%(statuses)s)",
        "(d.valid_until IS NULL OR d.valid_until >= current_date)",
    ]
    params: dict = {
        "statuses": settings.allowed_statuses,
        "emb": vec_literal(embedder.embed_query(query)),
        "tsq": build_tsquery(query),
        "cand": CANDIDATES,
        "k": top_k,
        "rrf": RRF_K,
    }
    if filters.category:
        clauses.append("d.category = %(category)s")
        params["category"] = filters.category
    if filters.language:
        clauses.append("d.language = %(language)s")
        params["language"] = filters.language
    if filters.program_level:
        clauses.append("(d.program_level && ARRAY[%(level)s, 'all']::text[])")
        params["level"] = filters.program_level
    where = " AND ".join(clauses)

    sql = f"""
    WITH cand_vec AS (
      SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> %(emb)s::vector) AS rnk
      FROM chunks c JOIN documents d ON d.id = c.document_id
      WHERE {where}
      ORDER BY c.embedding <=> %(emb)s::vector
      LIMIT %(cand)s
    ),
    cand_kw AS (
      SELECT c.id,
             row_number() OVER (ORDER BY ts_rank_cd(c.tsv, to_tsquery('simple', %(tsq)s)) DESC) AS rnk
      FROM chunks c JOIN documents d ON d.id = c.document_id
      WHERE {where} AND c.tsv @@ to_tsquery('simple', %(tsq)s)
      ORDER BY ts_rank_cd(c.tsv, to_tsquery('simple', %(tsq)s)) DESC
      LIMIT %(cand)s
    ),
    fused AS (
      SELECT id, SUM(1.0 / (%(rrf)s + rnk)) AS score
      FROM (SELECT id, rnk FROM cand_vec UNION ALL SELECT id, rnk FROM cand_kw) u
      GROUP BY id
    )
    SELECT f.score, 1 - (c.embedding <=> %(emb)s::vector) AS similarity,
           c.id AS chunk_id, c.chunk_index, c.heading_path, c.content,
           d.id AS doc_id, d.title, d.category, d.source_url, d.attachments, d.last_verified,
           d.freshness_tier, d.max_age_days, d.origin, d.status
    FROM fused f
    JOIN chunks c ON c.id = f.id
    JOIN documents d ON d.id = c.document_id
    ORDER BY f.score DESC, similarity DESC
    LIMIT %(k)s
    """
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return SearchOutcome("none", [])

    results = []
    for r in rows:
        attachments = []
        for att in r["attachments"] or []:
            attachments.append({**att, "url": delivery_url(att["cloudinary_id"], att["kind"], settings)})
        results.append({
            "chunk_id": r["chunk_id"],
            "text": r["content"],
            "heading_path": r["heading_path"],
            "score": float(r["score"]),
            "similarity": float(r["similarity"]),
            "document": {
                "id": r["doc_id"], "title": r["title"], "category": r["category"],
                "source_url": r["source_url"], "attachments": attachments,
                "last_verified": r["last_verified"].isoformat(), "freshness_tier": r["freshness_tier"],
                "status": r["status"],
                "stale": is_stale(r["freshness_tier"], r["last_verified"], r["max_age_days"]),
            },
        })
    best = max(x["similarity"] for x in results)
    return SearchOutcome("high" if best >= settings.min_similarity else "low", results)
