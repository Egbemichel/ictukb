from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import Caller, authenticate, get_conn
from ..schemas import FeedbackRequest

router = APIRouter(prefix="/v1", tags=["feedback"])


@router.post("/feedback", status_code=201)
def submit_feedback(body: FeedbackRequest, caller: Caller = Depends(authenticate), conn=Depends(get_conn)) -> dict:
    row = conn.execute(
        "INSERT INTO feedback (query, chunk_id, document_id, verdict, note, api_key_id) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (body.query, body.chunk_id, body.document_id, body.verdict, body.note, caller.key_id),
    ).fetchone()
    return {"id": row["id"]}
