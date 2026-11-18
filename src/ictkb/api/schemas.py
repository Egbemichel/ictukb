"""Request and response models of API version 1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    category: str | None = None
    program_level: Literal["bachelor", "masters", "phd"] | None = None
    language: Literal["en", "fr"] | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    filters: SearchFilters | None = None


class Attachment(BaseModel):
    cloudinary_id: str
    kind: str
    description: str
    url: str | None = None
    text_file: str | None = None
    collected_on: str | None = None


class DocumentRef(BaseModel):
    id: str
    title: str
    category: str
    source_url: str | None
    attachments: list[Attachment]
    last_verified: str
    freshness_tier: str
    status: str
    stale: bool


class SearchResult(BaseModel):
    chunk_id: int
    text: str
    heading_path: str | None
    score: float
    similarity: float
    document: DocumentRef


class SearchResponse(BaseModel):
    confidence: Literal["high", "low", "none"]
    results: list[SearchResult]


class FeedbackRequest(BaseModel):
    query: str | None = Field(default=None, max_length=1000)
    chunk_id: int | None = None
    document_id: str | None = None
    verdict: Literal["wrong", "missing", "outdated", "helpful"]
    note: str | None = Field(default=None, max_length=2000)
