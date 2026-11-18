"""Loading and validating the curated Markdown content (the Git source of truth)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import frontmatter
from jsonschema import Draft202012Validator, FormatChecker

from .config import Settings, get_settings
from .util import jsonable, load_yaml

PLACEHOLDER = re.compile(r"\[\[.*?\]\]", re.S)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
PHONE = re.compile(r"(?<![\w/])\+?\d[\d ().-]{7,}\d(?![\w/])")
SKIP_DIRS = {"_extracted"}


@dataclass
class ContentDoc:
    meta: dict
    body: str
    path: Path
    errors: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return str(self.meta.get("id", self.path.stem))


def parse_file(path: Path) -> ContentDoc:
    post = frontmatter.load(path, encoding="utf-8")
    return ContentDoc(meta=jsonable(dict(post.metadata)), body=post.content.strip(), path=path)


def iter_content_files(content_dir: Path) -> list[Path]:
    files = []
    for path in sorted(content_dir.rglob("*.md")):
        if path.name.lower() == "readme.md" or any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def load_all(settings: Settings | None = None) -> list[ContentDoc]:
    settings = settings or get_settings()
    docs: list[ContentDoc] = []
    for path in iter_content_files(settings.content_dir):
        try:
            docs.append(parse_file(path))
        except Exception as exc:  # malformed YAML or encoding
            docs.append(ContentDoc(meta={"id": path.stem}, body="", path=path, errors=[f"unreadable: {exc}"]))
    return docs


def load_private(settings: Settings | None = None) -> list[ContentDoc]:
    """Documents of content-private/ (git-ignored): indexed from this machine only, never published."""
    settings = settings or get_settings()
    folder = settings.root / "content-private"
    docs: list[ContentDoc] = []
    if not folder.exists():
        return docs
    for path in iter_content_files(folder):
        try:
            docs.append(parse_file(path))
        except Exception as exc:
            docs.append(ContentDoc(meta={"id": path.stem}, body="", path=path, errors=[f"unreadable: {exc}"]))
    return docs


def load_schema(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return json.loads((settings.schema_dir / "document.schema.json").read_text(encoding="utf-8"))


def load_categories(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return load_yaml(settings.schema_dir / "categories.yml")


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def validate(docs: list[ContentDoc], settings: Settings | None = None) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for the full content set."""
    settings = settings or get_settings()
    validator = Draft202012Validator(load_schema(settings), format_checker=FormatChecker())
    categories = load_categories(settings)
    allowed_domains = {d.lower() for d in categories.get("allowed_email_domains", [])}
    errors: list[str] = []
    warnings: list[str] = []
    ids: dict[str, Path] = {}
    all_ids = {d.id for d in docs}
    root = settings.root

    for doc in docs:
        rel = doc.path.relative_to(root).as_posix() if doc.path.is_relative_to(root) else str(doc.path)
        errors.extend(f"{rel}: {e}" for e in doc.errors)
        if doc.errors:
            continue
        for err in sorted(validator.iter_errors(doc.meta), key=lambda e: list(e.path)):
            where = ".".join(str(p) for p in err.path) or "(front matter)"
            errors.append(f"{rel}: {where}: {err.message}")

        doc_id = doc.id
        if doc_id in ids:
            errors.append(f"{rel}: duplicate id '{doc_id}' (also {ids[doc_id].name})")
        ids[doc_id] = doc.path
        if doc.path.stem != doc_id:
            errors.append(f"{rel}: file name must equal the id '{doc_id}'")
        category = doc.meta.get("category")
        parts = doc.path.relative_to(settings.content_dir).parts if doc.path.is_relative_to(settings.content_dir) else ()
        if parts and category and parts[0] != category:
            errors.append(f"{rel}: stored under '{parts[0]}' but category is '{category}'")

        levels = doc.meta.get("program_level") or []
        if "all" in levels and len(levels) > 1:
            errors.append(f"{rel}: program_level 'all' cannot be combined with other levels")
        vf, vu = doc.meta.get("valid_from"), doc.meta.get("valid_until")
        if vf and vu and vu < vf:
            errors.append(f"{rel}: valid_until precedes valid_from")
        lv = doc.meta.get("last_verified")
        if lv and lv > date.today().isoformat():
            errors.append(f"{rel}: last_verified is in the future")
        for ref in doc.meta.get("related") or []:
            if ref not in all_ids and not ref.startswith("web-"):
                warnings.append(f"{rel}: related id '{ref}' does not exist yet")
        for att in doc.meta.get("attachments") or []:
            tf = att.get("text_file")
            if tf and not (root / tf).exists():
                errors.append(f"{rel}: attachment text_file '{tf}' not found")

        text_blob = doc.body + "\n" + "\n".join(_strings(doc.meta))
        for match in EMAIL.finditer(text_blob):
            if match.group(1).lower() not in allowed_domains:
                errors.append(f"{rel}: email address outside the official domains: {match.group(0)}")
        if PHONE.search(doc.body):
            warnings.append(f"{rel}: contains a phone number; confirm it is an official office line")

        if doc.meta.get("status") == "verified":
            if PLACEHOLDER.search(text_blob):
                errors.append(f"{rel}: status is verified but unresolved [[...]] placeholders remain")
            if not doc.meta.get("verified_by"):
                errors.append(f"{rel}: status is verified but verified_by is empty")
            if doc.meta.get("owner") in (None, "", "unassigned"):
                errors.append(f"{rel}: status is verified but owner is not assigned")
            if len(doc.body) < 40:
                errors.append(f"{rel}: status is verified but the body is empty")
    return errors, warnings
