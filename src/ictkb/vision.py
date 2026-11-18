"""Reading text from images (menu boards, posters) with a vision model."""

from __future__ import annotations

import base64

import httpx

from .config import get_settings
from .util import with_retries

URL = "https://api.cohere.com/v2/chat"
MAX_BYTES = 8 * 1024 * 1024
PROMPT = (
    "Transcribe all text visible in this image exactly as written, keeping line breaks, prices, quantities and times. "
    "{hint} If the image has no readable text about food, menus, prices, schedules, events, sports or announcements "
    "(for example a photo of people, a meme or a sticker), reply with the single word NONE. Do not add commentary."
)
HINTS = {
    "canteen-menu": "It is probably a canteen or food menu: keep every dish with its price.",
    "bus-update": "It is probably a bus route or timetable: keep stops and times.",
}


def transcribe_image(data: bytes, mime: str = "image/jpeg", kind: str = "") -> str:
    """Return the text in the image, or an empty string when there is nothing relevant."""
    if len(data) > MAX_BYTES:
        raise ValueError("Image is larger than 8 MB")
    settings = get_settings()
    if not settings.cohere_api_key:
        raise RuntimeError("COHERE_API_KEY is not set")
    url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    payload = {
        "model": settings.vision_model,
        "temperature": 0,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT.format(hint=HINTS.get(kind, ""))},
                {"type": "image_url", "image_url": {"url": url}},
            ],
        }],
    }
    headers = {"Authorization": f"Bearer {settings.cohere_api_key}"}
    response = with_retries(lambda: httpx.post(URL, json=payload, headers=headers, timeout=120))
    response.raise_for_status()
    parts = response.json()["message"]["content"]
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
    return "" if text.upper().strip(". ") == "NONE" else text
