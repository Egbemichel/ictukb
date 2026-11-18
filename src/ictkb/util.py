"""Small helpers shared by the pipeline and the API."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

TIER_LIMITS_DEFAULT = {"realtime": 1, "daily": 7, "semester": 120, "static": 365}

_FRENCH = {"le", "la", "les", "des", "du", "et", "de", "pour", "une", "un", "est", "sont", "dans", "au", "aux", "que", "qui", "vous", "nous"}
_ENGLISH = {"the", "and", "of", "for", "to", "is", "are", "in", "that", "with", "you", "we", "your", "will", "on"}


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def today() -> date:
    return date.today()


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def jsonable(value: Any) -> Any:
    """Convert YAML-parsed dates to ISO strings so the structure can be validated as JSON."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def detect_language(text: str) -> str:
    """Rough en/fr detection from function-word frequency; sufficient for routing content."""
    words = re.findall(r"[a-zA-Zàâçéèêëîïôûùüÿœ]+", text.lower())[:400]
    fr = sum(1 for w in words if w in _FRENCH)
    en = sum(1 for w in words if w in _ENGLISH)
    return "fr" if fr > en * 1.2 else "en"


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def tier_limit(tier: str, max_age_days: int | None, limits: dict[str, int] | None = None) -> int:
    if max_age_days:
        return max_age_days
    return (limits or TIER_LIMITS_DEFAULT).get(tier, 365)


def is_stale(tier: str, last_verified: date | str, max_age_days: int | None = None,
             limits: dict[str, int] | None = None, on: date | None = None) -> bool:
    if isinstance(last_verified, str):
        last_verified = date.fromisoformat(last_verified[:10])
    age = ((on or today()) - last_verified).days
    return age > tier_limit(tier, max_age_days, limits)


def with_retries(call, attempts: int = 6, base_delay: float = 2.0):
    """Run call(); retry on transient network errors with exponential backoff."""
    import time

    import httpx

    for attempt in range(attempts):
        try:
            return call()
        except httpx.TransportError:
            if attempt == attempts - 1:
                raise
            time.sleep(min(base_delay * 2**attempt, 30))
