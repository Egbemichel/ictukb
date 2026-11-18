"""Write surface. Content is changed only by triggering the pipeline; there is no free-form write."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from ...connectors import sheets, web
from ...db import connect
from ...embedding import get_embedder
from ...keys import create_key, revoke_key
from ..deps import clear_key_cache, get_conn, require_admin

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class Note(BaseModel):
    kind: str = Field(pattern="^(canteen-menu|bus-update|announcement|student-life-post)$")
    text: str = Field(min_length=5, max_length=6000)
    by: str = Field(min_length=2, max_length=60)
    title: str | None = Field(default=None, max_length=120)
    key: str | None = Field(default=None, max_length=80)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    until: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class NewKey(BaseModel):
    owner: str = Field(min_length=2, max_length=80)
    rate_limit_per_min: int | None = Field(default=None, ge=1, le=6000)


def _sync_sheet(name: str) -> None:
    with connect() as conn:
        sheets.sync_all(conn, get_embedder(), name=name)


def _crawl() -> None:
    web.crawl(get_embedder())


@router.post("/sync/sheet/{name}", status_code=202)
def sync_sheet(name: str, tasks: BackgroundTasks) -> dict:
    if name not in {c["name"] for c in sheets.load_config()}:
        raise HTTPException(404, "Unknown sheet")
    tasks.add_task(_sync_sheet, name)
    return {"accepted": name}


@router.post("/sync/website", status_code=202)
def sync_website(tasks: BackgroundTasks) -> dict:
    tasks.add_task(_crawl)
    return {"accepted": "website"}


@router.post("/keys", status_code=201)
def new_key(body: NewKey, conn=Depends(get_conn)) -> dict:
    key_id, key = create_key(conn, body.owner, body.rate_limit_per_min)
    return {"id": key_id, "owner": body.owner, "api_key": key}


@router.delete("/keys/{key_id}")
def delete_key(key_id: str, conn=Depends(get_conn)) -> dict:
    if not revoke_key(conn, key_id):
        raise HTTPException(404, "Key not found or already revoked")
    clear_key_cache()
    return {"revoked": key_id}


@router.post("/notes", status_code=201)
def new_note(body: Note, conn=Depends(get_conn)) -> dict:
    from datetime import date

    from ...notes import post_note

    try:
        doc_id = post_note(
            conn, get_embedder(), body.kind, body.text, body.by, title=body.title, key=body.key,
            on=date.fromisoformat(body.date) if body.date else None,
            valid_until=date.fromisoformat(body.until) if body.until else None,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"id": doc_id}


class Transcribe(BaseModel):
    image_base64: str = Field(min_length=20, max_length=12_000_000)
    mime: str = Field(default="image/jpeg", pattern="^image/(jpeg|png|webp)$")
    kind: str = Field(default="", max_length=30)


@router.post("/transcribe")
def transcribe(body: Transcribe) -> dict:
    """Read the text of an image (a menu board or a poster); returns an empty string when there is none."""
    import base64
    import binascii

    from ...vision import transcribe_image

    try:
        data = base64.b64decode(body.image_base64, validate=True)
        return {"text": transcribe_image(data, body.mime, body.kind)}
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/notes/{doc_id}")
def remove_note(doc_id: str, conn=Depends(get_conn)) -> dict:
    from ...notes import delete_note

    if not delete_note(conn, doc_id):
        raise HTTPException(404, "Post not found")
    return {"deleted": doc_id}
