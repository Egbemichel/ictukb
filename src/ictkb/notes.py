"""Short-lived posts: the daily canteen menu, bus updates and announcements.

These messages originate in WhatsApp groups. A maintainer copies the message and posts it with
`ictkb post` (or POST /v1/admin/notes). Each post becomes a document that expires on its own, so
an old menu or notice is never returned after its last valid day.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import psycopg

from .chunking import chunk_markdown
from .content import EMAIL, load_categories
from .embedding import Embedder
from .indexer import IndexDoc, record_run, run_index
from .util import detect_language, slugify, today

KINDS = {
    "canteen-menu": {"prefix": "canteen-menu", "category": "canteen", "title": "Canteen menu", "days": 0, "daily": True},
    "bus-update": {"prefix": "transport-update", "category": "transport", "title": "Bus update", "days": 7, "daily": False},
    "student-life-post": {"prefix": "student-life-update", "category": "student-life", "title": "Student life update", "days": 14, "daily": False},
    "announcement": {"prefix": "announcements-current-note", "category": "announcements", "title": "Announcement", "days": 14, "daily": False},
}
MAX_CHARS = 6000


def check_text(text: str) -> str:
    text = text.strip()
    if len(text) < 5:
        raise ValueError("The text is empty")
    if len(text) > MAX_CHARS:
        raise ValueError(f"The text is longer than {MAX_CHARS} characters")
    allowed = {d.lower() for d in load_categories().get("allowed_email_domains", [])}
    for match in EMAIL.finditer(text):
        if match.group(1).lower() not in allowed:
            raise ValueError(f"Email address outside the official domains: {match.group(0)}")
    return text


def build_note(kind: str, text: str, by: str, on: date | None = None, title: str | None = None,
               valid_until: date | None = None, key: str | None = None) -> IndexDoc:
    if kind not in KINDS:
        raise ValueError(f"Unknown kind '{kind}'. Use one of: {', '.join(KINDS)}")
    spec = KINDS[kind]
    text = check_text(text)
    on = on or today()
    until = valid_until or on + timedelta(days=spec["days"])
    label = title.strip() if title else spec["title"]
    if spec["daily"]:
        doc_id = f"{spec['prefix']}-{on.isoformat()}"
        full_title = f"{spec['title']} for {on.isoformat()}"
    else:
        suffix = slugify(key)[:60] if key else (slugify(title)[:40] if title else "post")
        doc_id = f"{spec['prefix']}-{on.isoformat()}-{suffix}"
        full_title = f"{label} ({on.isoformat()})"
    meta = {
        "id": doc_id, "title": full_title, "category": spec["category"], "subcategory": kind, "program_level": ["all"],
        "language": detect_language(text), "source_type": "observation", "source_url": None, "attachments": [],
        "freshness_tier": "realtime", "status": "verified", "last_verified": today().isoformat(),
        "verified_by": by, "owner": by, "tags": [kind], "related": [], "valid_from": on.isoformat(),
        "valid_until": until.isoformat(),
    }
    body = f"## {full_title}\n\n{text}"
    return IndexDoc(id=doc_id, meta=meta, chunks=chunk_markdown(full_title, body), origin="note", origin_ref=kind,
                    max_age_days=max(1, (until - on).days + 1))


def post_note(conn: psycopg.Connection, embedder: Embedder, kind: str, text: str, by: str, **kwargs) -> str:
    started = datetime.now(timezone.utc)
    doc = build_note(kind, text, by, **kwargs)
    run_index(conn, embedder, [doc], origin="note", origin_ref=kind, statuses=["verified"], prune=False)
    record_run(conn, f"note:{kind}", started, 1, "ok")
    return doc.id


def prune_expired(conn: psycopg.Connection) -> int:
    """Delete posts whose last valid day has passed."""
    cur = conn.execute("DELETE FROM documents WHERE origin = 'note' AND valid_until < current_date")
    conn.commit()
    return cur.rowcount



def delete_note(conn: psycopg.Connection, doc_id: str) -> bool:
    """Delete one post (only documents created from posts can be removed this way)."""
    cur = conn.execute("DELETE FROM documents WHERE id = %s AND origin = 'note'", (doc_id,))
    conn.commit()
    return cur.rowcount > 0
