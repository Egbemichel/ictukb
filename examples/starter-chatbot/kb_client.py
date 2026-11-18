"""Minimal client for the ICT University knowledge base API."""

from __future__ import annotations

import os

import httpx

BASE_URL = os.environ.get("KB_API_URL", "http://localhost:8000")
API_KEY = os.environ.get("KB_API_KEY", "")


def search(query: str, top_k: int = 5, **filters) -> dict:
    response = httpx.post(
        f"{BASE_URL}/v1/search",
        json={"query": query, "top_k": top_k, "filters": filters or None},
        headers={"X-API-Key": API_KEY},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def report(query: str, verdict: str, note: str = "", document_id: str | None = None) -> None:
    httpx.post(
        f"{BASE_URL}/v1/feedback",
        json={"query": query, "verdict": verdict, "note": note, "document_id": document_id},
        headers={"X-API-Key": API_KEY},
        timeout=30,
    ).raise_for_status()
