"""Staleness reporting from the content files (no database) and from the index."""

from __future__ import annotations

import psycopg

from .config import Settings, get_settings
from .content import ContentDoc, load_categories
from .util import TIER_LIMITS_DEFAULT, is_stale, tier_limit, today


def limits(settings: Settings | None = None) -> dict[str, int]:
    cats = load_categories(settings or get_settings())
    return {**TIER_LIMITS_DEFAULT, **cats.get("freshness_tiers", {})}


def stale_from_files(docs: list[ContentDoc], settings: Settings | None = None) -> list[dict]:
    lim = limits(settings)
    out = []
    for d in docs:
        m = d.meta
        if m.get("status") != "verified" or "last_verified" not in m:
            continue
        if is_stale(m["freshness_tier"], m["last_verified"], None, lim):
            age = (today() - today().fromisoformat(m["last_verified"])).days
            out.append({
                "id": d.id, "category": m["category"], "owner": m["owner"], "tier": m["freshness_tier"],
                "last_verified": m["last_verified"], "age_days": age,
                "limit_days": tier_limit(m["freshness_tier"], None, lim),
            })
    return sorted(out, key=lambda r: (r["owner"], r["id"]))


def stale_from_db(conn: psycopg.Connection, settings: Settings | None = None) -> list[dict]:
    lim = limits(settings)
    rows = conn.execute(
        "SELECT id, category, owner, freshness_tier AS tier, last_verified, max_age_days, origin "
        "FROM documents WHERE status = 'verified' AND origin <> 'web'"
    ).fetchall()
    out = []
    for r in rows:
        if is_stale(r["tier"], r["last_verified"], r["max_age_days"], lim):
            out.append({
                "id": r["id"], "category": r["category"], "owner": r["owner"], "tier": r["tier"],
                "last_verified": r["last_verified"].isoformat(),
                "age_days": (today() - r["last_verified"]).days,
                "limit_days": tier_limit(r["tier"], r["max_age_days"], lim),
            })
    return sorted(out, key=lambda r: (r["owner"], r["id"]))


def category_report(conn: psycopg.Connection, settings: Settings | None = None) -> list[dict]:
    """Per category: document count, last content change, and stale count."""
    lim = limits(settings)
    rows = conn.execute(
        "SELECT category, id, freshness_tier, last_verified, max_age_days, updated_at "
        "FROM documents WHERE status = ANY(%s)", ((settings or get_settings()).allowed_statuses,)
    ).fetchall()
    report: dict[str, dict] = {}
    for r in rows:
        entry = report.setdefault(r["category"], {"category": r["category"], "documents": 0, "stale": 0, "last_update": None})
        entry["documents"] += 1
        if is_stale(r["freshness_tier"], r["last_verified"], r["max_age_days"], lim):
            entry["stale"] += 1
        stamp = r["updated_at"].isoformat()
        if entry["last_update"] is None or stamp > entry["last_update"]:
            entry["last_update"] = stamp
    return sorted(report.values(), key=lambda e: e["category"])
