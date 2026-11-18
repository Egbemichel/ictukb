"""Website connector: reads the university WordPress site through its public REST API.

The REST API returns clean page content and a modification timestamp, which avoids HTML
scraping of the theme. The crawler honours robots.txt, including Crawl-delay.
"""

from __future__ import annotations

import html
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import robotparser

import frontmatter
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify

from ..chunking import chunk_markdown
from ..config import Settings, get_settings
from ..embedding import Embedder
from ..indexer import IndexDoc, IndexReport, record_run, run_index
from ..util import detect_language, load_yaml, today, with_retries

FIELDS = "id,link,slug,title,date_gmt,modified_gmt,content,type"


def load_config(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return load_yaml(settings.sources_dir / "website.yml")


def html_to_markdown(source: str) -> str:
    soup = BeautifulSoup(source, "html.parser")
    for tag in soup(["script", "style", "svg", "noscript", "form", "iframe", "button", "img", "input", "select"]):
        tag.decompose()
    text = markdownify(str(soup), heading_style="ATX", bullets="-")
    text = re.sub(r"\[et_pb[^\]]*\]|\[/et_pb[^\]]*\]", "", text)
    lines, previous = [], None
    for line in (ln.rstrip() for ln in text.splitlines()):
        if line.strip() and line.strip() == previous:
            continue  # responsive page builders repeat blocks
        lines.append(line)
        previous = line.strip() or previous
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def infer_level(slug: str, title: str) -> list[str]:
    text = f"{slug} {title}".lower()
    if re.search(r"ph\.?d|doctora", text):
        return ["phd"]
    if re.search(r"master|msc|imba|\bmed\b|\bmph\b", text):
        return ["masters"]
    if re.search(r"bachelor|bsc", text):
        return ["bachelor"]
    return ["all"]


def classify(cfg: dict, item: dict) -> dict:
    slug = item["slug"]
    if item["type"] == "post":
        posts = cfg.get("posts", {})
        return {"category": posts.get("category", "announcements"), "tier": posts.get("tier", "daily"),
                "subcategory": "news"}
    for rule in cfg.get("rules", []):
        if re.search(rule["match"], slug):
            return {"category": rule["category"], "tier": rule.get("tier", "semester"),
                    "subcategory": rule.get("subcategory")}
    default = cfg.get("default", {})
    return {"category": default.get("category", "about"), "tier": default.get("tier", "semester"),
            "subcategory": None}


def _client(cfg: dict) -> tuple[httpx.Client, float]:
    base = cfg["base_url"].rstrip("/")
    agent = cfg.get("user_agent", "ictu-kb-crawler")
    parser = robotparser.RobotFileParser()
    delay = float(cfg.get("request_delay_seconds", 20))
    try:
        robots = with_retries(lambda: httpx.get(f"{base}/robots.txt", headers={"User-Agent": agent}, timeout=30)).text
        parser.parse(robots.splitlines())
        if not parser.can_fetch(agent, f"{base}{cfg['api_path']}/pages"):
            raise PermissionError("robots.txt disallows the REST API path")
        delay = max(delay, float(parser.crawl_delay(agent) or 0))
    except httpx.HTTPError:
        pass
    return httpx.Client(headers={"User-Agent": agent}, timeout=60, follow_redirects=True), delay


def fetch_items(cfg: dict) -> list[dict]:
    base = cfg["base_url"].rstrip("/") + cfg["api_path"]
    client, delay = _client(cfg)
    items: list[dict] = []
    posts_cfg = cfg.get("posts", {})
    after = (datetime.now(timezone.utc) - timedelta(days=int(posts_cfg.get("max_age_days", 365)))).strftime("%Y-%m-%dT%H:%M:%S")
    requests = [("pages", {})]
    if posts_cfg.get("enabled", True):
        requests.append(("posts", {"after": after}))
    first = True
    with client:
        for kind, extra in requests:
            page = 1
            while True:
                if not first:
                    time.sleep(delay)
                first = False
                response = with_retries(lambda kind=kind, page=page, extra=extra: client.get(f"{base}/{kind}", params={"per_page": 100, "page": page, "_fields": FIELDS, **extra}))
                response.raise_for_status()
                items.extend(response.json())
                if page >= int(response.headers.get("X-WP-TotalPages", 1)):
                    break
                page += 1
    if posts_cfg.get("enabled", True):
        posts = sorted((i for i in items if i["type"] == "post"), key=lambda i: i["date_gmt"], reverse=True)
        limit = int(posts_cfg.get("max_posts", 30))
        drop = {i["id"] for i in posts[limit:]}
        items = [i for i in items if not (i["type"] == "post" and i["id"] in drop)]
    return items


def build_docs(cfg: dict, items: list[dict]) -> list[IndexDoc]:
    exclude = set(cfg.get("exclude_slugs", []))
    min_chars = int(cfg.get("min_chars", 200))
    docs: list[IndexDoc] = []
    for item in items:
        if item["slug"] in exclude:
            continue
        title = html.unescape(item["title"]["rendered"]).strip()
        body = html_to_markdown(item["content"]["rendered"])
        if len(body) < min_chars:
            continue
        info = classify(cfg, item)
        doc_id = f"web-{item['slug']}"[:120]
        meta = {
            "id": doc_id, "title": title or item["slug"], "category": info["category"],
            "subcategory": info["subcategory"], "program_level": infer_level(item["slug"], title),
            "language": detect_language(body), "source_type": "website", "source_url": item["link"],
            "attachments": [], "freshness_tier": info["tier"], "status": "verified",
            "last_verified": today().isoformat(), "verified_by": "website-crawler",
            "owner": cfg.get("owner", "website"), "tags": ["website"], "related": [],
        }
        if item["type"] == "post":
            meta["valid_from"] = item["date_gmt"][:10]
        docs.append(IndexDoc(id=doc_id, meta=meta, chunks=chunk_markdown(meta["title"], body),
                             origin="web", origin_ref="website"))
    return docs


def write_snapshot(docs: list[IndexDoc], out: Path) -> int:
    """Dry-run helper: write each page as Markdown with front matter for manual inspection."""
    out.mkdir(parents=True, exist_ok=True)
    for d in docs:
        body = "\n\n".join(c.content for c in d.chunks)
        (out / f"{d.id}.md").write_text(frontmatter.dumps(frontmatter.Post(body, **d.meta), sort_keys=False), encoding="utf-8")
    return len(docs)


def crawl(embedder: Embedder) -> IndexReport:
    """Fetch first (slow, rate-limited), then open the database connection for the write."""
    from ..db import connect

    started = datetime.now(timezone.utc)
    try:
        cfg = load_config()
        docs = build_docs(cfg, fetch_items(cfg))
        if not docs:
            raise RuntimeError("The crawl produced no documents; refusing to delete the existing ones")
        with connect() as conn:
            report = run_index(conn, embedder, docs, origin="web", origin_ref="website", statuses=["verified"])
            record_run(conn, "website", started, report.changed, "ok")
        return report
    except Exception as exc:
        with connect() as conn:
            record_run(conn, "website", started, 0, "error", str(exc)[:500])
        raise
