from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...cloud import delivery_url
from ...config import get_settings
from ...content import load_categories
from ...freshness import category_report
from ...util import is_stale
from ..deps import authenticate, get_conn

router = APIRouter(prefix="/v1", tags=["documents"], dependencies=[Depends(authenticate)])


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, conn=Depends(get_conn)) -> dict:
    s = get_settings()
    doc = conn.execute(
        "SELECT * FROM documents WHERE id = %s AND status = ANY(%s)", (doc_id, s.allowed_statuses)
    ).fetchone()
    if not doc:
        raise HTTPException(404, "Document not found")
    chunks = conn.execute(
        "SELECT chunk_index, heading_path, content FROM chunks WHERE document_id = %s ORDER BY chunk_index",
        (doc_id,),
    ).fetchall()
    attachments = [{**a, "url": delivery_url(a["cloudinary_id"], a["kind"], s)} for a in doc["attachments"] or []]
    return {
        "id": doc["id"], "title": doc["title"], "category": doc["category"], "subcategory": doc["subcategory"],
        "program_level": doc["program_level"], "department": doc["department"], "language": doc["language"],
        "source_type": doc["source_type"], "source_url": doc["source_url"], "attachments": attachments,
        "academic_year": doc["academic_year"], "semester": doc["semester"],
        "valid_from": doc["valid_from"], "valid_until": doc["valid_until"],
        "freshness_tier": doc["freshness_tier"], "last_verified": doc["last_verified"],
        "stale": is_stale(doc["freshness_tier"], doc["last_verified"], doc["max_age_days"]),
        "tags": doc["tags"], "related": doc["related"], "updated_at": doc["updated_at"],
        "chunks": chunks,
    }


@router.get("/documents")
def list_documents(category: str | None = None, limit: int = Query(50, ge=1, le=200),
                   offset: int = Query(0, ge=0), conn=Depends(get_conn)) -> dict:
    s = get_settings()
    params: list = [s.allowed_statuses]
    where = "status = ANY(%s)"
    if category:
        where += " AND category = %s"
        params.append(category)
    rows = conn.execute(
        f"SELECT id, title, category, freshness_tier, last_verified FROM documents WHERE {where} "
        "ORDER BY category, id LIMIT %s OFFSET %s", (*params, limit, offset),
    ).fetchall()
    return {"documents": rows, "limit": limit, "offset": offset}


@router.get("/categories")
def categories(conn=Depends(get_conn)) -> dict:
    meta = load_categories()["categories"]
    counts = {r["category"]: r for r in category_report(conn)}
    return {"categories": [
        {"id": cid, "label": info["label"], "description": info["description"],
         "documents": counts.get(cid, {}).get("documents", 0)}
        for cid, info in meta.items()
    ]}


@router.get("/freshness")
def freshness(conn=Depends(get_conn)) -> dict:
    return {"categories": category_report(conn)}
