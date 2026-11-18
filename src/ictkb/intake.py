"""Intake of collected files.

Collectors place files in incoming/<category>/ using the name category_topic_YYYY-MM-DD.ext.
For each file the intake step uploads it to Cloudinary, extracts its text into
content/<category>/_extracted/, and registers it as an attachment of the matching document
(category-topic). A new draft document is created when none exists.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from . import cloud
from .config import Settings, get_settings
from .connectors.sheets import load_config as load_sheets
from .content import load_categories
from .parsers import UnsupportedFile, extract_text, kind_for
from .util import today

NAME = re.compile(
    r"^(?P<category>[a-z]+(?:-[a-z]+)*)_(?P<topic>[a-z0-9]+(?:-[a-z0-9]+)*)(?:~(?P<part>[a-z0-9]+(?:-[a-z0-9]+)*))?"
    r"_(?P<date>\d{4}-\d{2}-\d{2})\.(?P<ext>[A-Za-z0-9]+)$"
)
PLACEHOLDER_DESC = "[[TO FILL: describe this file in one sentence for the person who will read the answer]]"


@dataclass
class IntakeResult:
    file: str
    status: str
    detail: str = ""


def _find_doc(content_dir: Path, doc_id: str) -> Path | None:
    for path in content_dir.rglob(f"{doc_id}.md"):
        if "_extracted" not in path.parts:
            return path
    return None


def _new_doc(settings: Settings, category: str, doc_id: str, topic: str) -> frontmatter.Post:
    meta = {
        "id": doc_id, "title": topic.replace("-", " ").capitalize(), "category": category,
        "program_level": ["all"], "language": "en", "source_type": "official_doc", "source_url": None,
        "attachments": [], "freshness_tier": "semester", "status": "draft",
        "last_verified": today().isoformat(), "verified_by": None, "owner": "unassigned",
        "tags": [], "related": [],
    }
    return frontmatter.Post("[[TO FILL: write the answer content for this topic]]", **meta)


def run_intake(settings: Settings | None = None, dry_run: bool = False, local_only: bool = False) -> list[IntakeResult]:
    settings = settings or get_settings()
    valid_categories = set(load_categories(settings)["categories"])
    results: list[IntakeResult] = []
    sheet_ids = {c["doc_id"] for c in load_sheets(settings)}
    incoming = settings.incoming_dir
    files = sorted(p for p in incoming.glob("*/*") if p.is_file() and not p.parent.name.startswith("_") and p.name.lower() != "readme.md")
    for path in files:
        match = NAME.match(path.name)
        category = path.parent.name
        if not match or match["category"] != category or category not in valid_categories:
            results.append(IntakeResult(path.name, "rejected", "name must be category_topic_YYYY-MM-DD.ext inside incoming/<category>/"))
            continue
        try:
            kind = kind_for(path)
        except UnsupportedFile as exc:
            results.append(IntakeResult(path.name, "rejected", str(exc)))
            continue

        topic, ext = match["topic"], "." + match["ext"].lower()
        doc_id = f"{category}-{topic}"
        if doc_id in sheet_ids:
            doc_id += "-files"  # the sheet owns the plain id; attached files get a companion document
        part = f"-{match['part']}" if match["part"] else ""
        stem = f"{topic}{part}_{match['date']}"
        public_id = cloud.public_id_for(category, stem, ext, kind)
        text = extract_text(path)
        notes = []
        if not text.strip():
            notes.append("no text extracted (scanned or image-only); the written description will be the only searchable text")
        if dry_run:
            results.append(IntakeResult(path.name, "dry-run", f"-> {doc_id}, {kind}, {len(text)} characters of text"))
            continue

        uploaded = False
        if not local_only and settings.cloudinary_enabled:
            cloud.upload(path, public_id, kind, settings)
            uploaded = True
        else:
            notes.append("not uploaded to Cloudinary (credentials absent or --local); upload manually and keep the id")

        text_rel = None
        if text.strip():
            target = settings.content_dir / category / "_extracted" / doc_id / f"{stem}.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            text_rel = target.relative_to(settings.root).as_posix()

        doc_path = _find_doc(settings.content_dir, doc_id)
        post = frontmatter.load(doc_path, encoding="utf-8") if doc_path else _new_doc(settings, category, doc_id, topic)
        attachments = [a for a in post.metadata.get("attachments") or [] if a.get("cloudinary_id") != public_id]
        previous = next((a for a in post.metadata.get("attachments") or [] if a.get("cloudinary_id") == public_id), {})
        attachments.append({
            "cloudinary_id": public_id, "kind": kind,
            "description": previous.get("description", PLACEHOLDER_DESC),
            "text_file": text_rel, "collected_on": match["date"],
        })
        post.metadata["attachments"] = attachments
        doc_path = doc_path or settings.content_dir / category / f"{doc_id}.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(frontmatter.dumps(post, sort_keys=False) + "\n", encoding="utf-8")

        done = incoming / "_done" / category
        done.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(done / path.name))
        results.append(IntakeResult(path.name, "ok" if uploaded else "ok-local", "; ".join([f"-> {doc_id}", *notes])))
    return results
