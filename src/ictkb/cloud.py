"""Cloudinary access through its REST API (signed uploads, delivery URLs)."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import httpx

from .config import Settings, get_settings
from .util import with_retries


def resource_type(kind: str) -> str:
    return "image" if kind == "image" else "raw"


def public_id_for(category: str, stem: str, ext: str, kind: str) -> str:
    """Raw resources keep their extension in the public id; images do not."""
    base = f"ictu/{category}/{stem}"
    return base if kind == "image" else f"{base}{ext}"


def delivery_url(cloudinary_id: str, kind: str, settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    if not settings.cloudinary_cloud_name:
        return None
    return f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}/{resource_type(kind)}/upload/{cloudinary_id}"


def upload(path: Path, public_id: str, kind: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if not settings.cloudinary_enabled:
        raise RuntimeError("Cloudinary credentials are not configured")
    timestamp = str(int(time.time()))
    params = {"overwrite": "true", "public_id": public_id, "timestamp": timestamp}
    to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params))
    signature = hashlib.sha1((to_sign + settings.cloudinary_api_secret).encode()).hexdigest()
    url = f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/{resource_type(kind)}/upload"
    def send() -> httpx.Response:
        with path.open("rb") as handle:
            return httpx.post(
                url,
                data={**params, "api_key": settings.cloudinary_api_key, "signature": signature},
                files={"file": (path.name, handle)},
                timeout=300,
            )

    response = with_retries(send)
    response.raise_for_status()
    return response.json()
