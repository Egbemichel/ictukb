from __future__ import annotations

from fastapi import APIRouter, Depends

from ...embedding import get_embedder
from ...search import Filters, search
from ..deps import authenticate, get_conn
from ..schemas import SearchRequest, SearchResponse

router = APIRouter(prefix="/v1", tags=["search"], dependencies=[Depends(authenticate)])


@router.post("/search", response_model=SearchResponse)
def search_endpoint(body: SearchRequest, conn=Depends(get_conn)) -> SearchResponse:
    f = body.filters
    filters = Filters(
        category=f.category if f else None,
        program_level=f.program_level if f else None,
        language=f.language if f else None,
    )
    outcome = search(conn, get_embedder(), body.query, body.top_k, filters)
    return SearchResponse(confidence=outcome.confidence, results=outcome.results)
