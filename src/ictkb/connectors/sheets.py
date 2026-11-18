"""Google Sheets connector for volatile tabular data (timetables, menu, announcements, directories).

A sheet must be shared as "anyone with the link can view". Each configured sheet is rendered
into self-contained text rows, optionally grouped into one document per group (for example
one timetable document per program, year and semester).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg

from ..chunking import Chunk
from ..config import Settings, get_settings
from ..embedding import Embedder
from ..indexer import IndexDoc, IndexReport, record_run, run_index
from ..util import load_yaml, slugify, today

EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
LEVELS = {"bachelor": "bachelor", "bachelors": "bachelor", "bsc": "bachelor", "master": "masters",
          "masters": "masters", "msc": "masters", "phd": "phd", "doctorate": "phd"}


def load_config(settings: Settings | None = None) -> list[dict]:
    settings = settings or get_settings()
    data = load_yaml(settings.sources_dir / "sheets.yml")
    defaults = data.get("defaults", {})
    return [{**defaults, **entry} for entry in data["sheets"]]


def fetch_csv(cfg: dict, settings: Settings | None = None) -> str | None:
    """Return the CSV text of a configured sheet, or None when it is not configured yet."""
    settings = settings or get_settings()
    if cfg.get("csv_path"):
        return (settings.root / cfg["csv_path"]).read_text(encoding="utf-8-sig")
    if not cfg.get("sheet_id"):
        return None
    url = EXPORT_URL.format(sheet_id=cfg["sheet_id"], gid=cfg.get("gid", 0))
    response = httpx.get(url, follow_redirects=True, timeout=60)
    response.raise_for_status()
    if "text/csv" not in response.headers.get("content-type", ""):
        raise RuntimeError(f"Sheet '{cfg['name']}' is not publicly readable (received a sign-in page)")
    return response.content.decode("utf-8-sig")


def parse_rows(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.reader(io.StringIO(text))
    try:
        headers = [h.strip() for h in next(reader)]
    except StopIteration:
        return [], []
    rows = []
    for raw in reader:
        row = {h: (raw[i].strip() if i < len(raw) else "") for i, h in enumerate(headers) if h}
        if any(row.values()):
            rows.append(row)
    return headers, rows


def render_row(row: dict[str, str]) -> str:
    return "- " + " | ".join(f"{k}: {v}" for k, v in row.items() if v)


def _levels(cfg: dict, rows: list[dict[str, str]]) -> list[str]:
    column = cfg.get("level_column")
    if column:
        found = {LEVELS.get(r.get(column, "").strip().lower()) for r in rows} - {None}
        if found:
            return sorted(found)
    return cfg.get("program_level") or ["all"]


def build_docs(cfg: dict, headers: list[str], rows: list[dict[str, str]]) -> list[IndexDoc]:
    missing = [c for c in cfg.get("columns", []) if c not in headers]
    if missing:
        raise ValueError(f"Sheet '{cfg['name']}' lacks required columns: {', '.join(missing)}")
    group_by = cfg.get("group_by") or []
    groups: dict[tuple, list[dict[str, str]]] = {}
    for row in rows:
        key = tuple(row.get(c, "") for c in group_by)
        if group_by and not all(key):
            continue  # a row without its group values cannot be placed in a document
        groups.setdefault(key, []).append(row)

    per_chunk = int(cfg.get("rows_per_chunk", 12))
    docs: list[IndexDoc] = []
    for key, members in groups.items():
        suffix = "-".join(slugify(v) for v in key)
        doc_id = f"{cfg['doc_id']}-{suffix}" if suffix else cfg["doc_id"]
        label = " / ".join(key)
        title = f"{cfg['title']} ({label})" if label else cfg["title"]
        chunks = []
        for i in range(0, len(members), per_chunk):
            part = members[i:i + per_chunk]
            heading = label or f"Rows {i + 1}-{i + len(part)}"
            body = "\n".join(render_row(r) for r in part)
            chunks.append(Chunk(heading, f"{title} | rows {i + 1}-{i + len(part)}\n\n{body}", "sheet"))
        sheet_url = f"https://docs.google.com/spreadsheets/d/{cfg['sheet_id']}" if cfg.get("sheet_id") else None
        meta = {
            "id": doc_id, "title": title, "category": cfg["category"], "subcategory": cfg.get("subcategory"),
            "program_level": _levels(cfg, members), "language": cfg.get("language", "en"),
            "source_type": "sheet", "source_url": sheet_url, "attachments": [],
            "freshness_tier": cfg["tier"], "status": "verified", "last_verified": today().isoformat(),
            "verified_by": f"sheet:{cfg['name']}", "owner": cfg.get("owner", "unassigned"),
            "tags": cfg.get("tags", []), "related": cfg.get("related", []),
        }
        docs.append(IndexDoc(
            id=doc_id, meta=meta, chunks=chunks, origin="sheet", origin_ref=cfg["name"],
            max_age_days=cfg.get("max_age_days"), keep_verified_on_unchanged=True,
        ))
    return docs


def sync_sheet(conn: psycopg.Connection, embedder: Embedder, cfg: dict, allow_empty: bool = False) -> IndexReport | None:
    started = datetime.now(timezone.utc)
    source = f"sheet:{cfg['name']}"
    try:
        text = fetch_csv(cfg)
        if text is None:
            return None
        headers, rows = parse_rows(text)
        docs = build_docs(cfg, headers, rows)
        if not docs and not allow_empty:
            raise RuntimeError("The sheet produced no documents; refusing to delete the existing ones")
        report = run_index(conn, embedder, docs, origin="sheet", origin_ref=cfg["name"], statuses=["verified"])
        record_run(conn, source, started, report.changed, "ok")
        return report
    except Exception as exc:
        conn.rollback()
        record_run(conn, source, started, 0, "error", str(exc)[:500])
        raise


def sync_all(conn: psycopg.Connection, embedder: Embedder, tiers: set[str] | None = None,
             name: str | None = None) -> dict[str, str]:
    results: dict[str, str] = {}
    for cfg in load_config():
        if name and cfg["name"] != name:
            continue
        if tiers and cfg["tier"] not in tiers:
            continue
        try:
            report = sync_sheet(conn, embedder, cfg)
            results[cfg["name"]] = "not configured" if report is None else str(report)
        except Exception as exc:
            results[cfg["name"]] = f"ERROR: {exc}"
    return results


def template_csv(cfg: dict) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerow(cfg["columns"])
    return buffer.getvalue()


__all__ = ["load_config", "sync_all", "sync_sheet", "build_docs", "parse_rows", "template_csv", "Path"]
