"""Command line interface: ictkb <command>."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings


def _load_and_validate(strict_warnings: bool = False):
    from .content import load_all, validate

    docs = load_all()
    errors, warnings = validate(docs)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    return docs, errors, warnings


def cmd_validate(args: argparse.Namespace) -> int:
    docs, errors, _ = _load_and_validate()
    verified = sum(1 for d in docs if d.meta.get("status") == "verified")
    print(f"{len(docs)} documents checked: {verified} verified, {len(docs) - verified} other, {len(errors)} errors")
    return 1 if errors else 0


def cmd_migrate(_: argparse.Namespace) -> int:
    from .db import connect, migrate

    with connect() as conn:
        applied = migrate(conn)
    print("applied: " + (", ".join(applied) if applied else "nothing to do"))
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    from .content import load_private, validate
    from .db import connect
    from .embedding import get_embedder
    from .indexer import build_index_doc, record_run, run_index

    settings = get_settings()
    docs, errors, _ = _load_and_validate()
    if errors:
        print("Indexing aborted: fix the errors above first.", file=sys.stderr)
        return 1
    started = datetime.now(timezone.utc)
    index_docs = [build_index_doc(d, settings) for d in docs]
    with connect() as conn:
        report = run_index(conn, get_embedder(), index_docs, origin="git", force=args.force)
        record_run(conn, "content", started, report.changed, "ok")
        private = load_private(settings)
        if private:
            perrors, _ = validate(private, settings)
            if perrors:
                for e in perrors:
                    print(f"error: {e}", file=sys.stderr)
                return 1
            private_docs = [build_index_doc(d, settings) for d in private]
            for d in private_docs:
                d.origin = "private"
            preport = run_index(conn, get_embedder(), private_docs, origin="private", force=args.force)
            print(f"[{settings.kb_env}] private: {preport}")
    print(f"[{settings.kb_env}] {report}")
    return 0


def cmd_sync_sheets(args: argparse.Namespace) -> int:
    from .connectors import sheets
    from .db import connect
    from .embedding import get_embedder

    tiers = set(args.tier) if args.tier else None
    with connect() as conn:
        results = sheets.sync_all(conn, get_embedder(), tiers=tiers, name=args.name)
    failed = False
    for name, outcome in results.items():
        print(f"{name}: {outcome}")
        failed |= outcome.startswith("ERROR")
    return 1 if failed else 0


def cmd_crawl(args: argparse.Namespace) -> int:
    from .connectors import web

    if args.dry_run:
        cfg = web.load_config()
        docs = web.build_docs(cfg, web.fetch_items(cfg))
        count = web.write_snapshot(docs, Path(args.out))
        print(f"{count} pages written to {args.out}")
        return 0
    from .embedding import get_embedder

    print(web.crawl(get_embedder()))
    return 0


def cmd_intake(args: argparse.Namespace) -> int:
    from .intake import run_intake

    results = run_intake(dry_run=args.dry_run, local_only=args.local)
    for r in results:
        print(f"{r.status:9} {r.file}  {r.detail}")
    if not results:
        print("No files found in incoming/<category>/")
    return 1 if any(r.status == "rejected" for r in results) else 0


def cmd_reindex(_: argparse.Namespace) -> int:
    from .db import connect
    from .embedding import get_embedder
    from .indexer import reindex_all

    with connect() as conn:
        n = reindex_all(conn, get_embedder())
    print(f"re-embedded {n} chunks")
    return 0


def cmd_freshness(args: argparse.Namespace) -> int:
    from .content import load_all
    from .freshness import stale_from_db, stale_from_files

    stale = stale_from_files(load_all())
    if args.db:
        from .db import connect

        with connect() as conn:
            stale += [s for s in stale_from_db(conn) if s["id"] not in {x["id"] for x in stale}]
    if args.json:
        print(json.dumps(stale, indent=2))
    else:
        for s in stale:
            print(f"{s['id']:45} owner={s['owner']:20} age={s['age_days']}d limit={s['limit_days']}d")
        print(f"{len(stale)} stale documents")
    return 0


def cmd_keys(args: argparse.Namespace) -> int:
    from .db import connect
    from .keys import create_key, list_keys, revoke_key

    with connect() as conn:
        if args.action == "create":
            key_id, key = create_key(conn, args.owner, args.rate_limit)
            print(f"id:  {key_id}\nkey: {key}\nStore the key now; it cannot be shown again.")
        elif args.action == "list":
            for k in list_keys(conn):
                state = "revoked" if k["revoked_at"] else "active"
                print(f"{k['id']}  {k['owner']:25} {state}  last_used={k['last_used_at']}")
        else:
            print("revoked" if revoke_key(conn, args.key_id) else "not found or already revoked")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Mark documents as verified after a human has checked them."""
    import frontmatter

    from .util import today

    settings = get_settings()
    for doc_id in args.ids:
        matches = [p for p in settings.content_dir.rglob(f"{doc_id}.md") if "_extracted" not in p.parts]
        if not matches:
            print(f"{doc_id}: not found", file=sys.stderr)
            return 1
        post = frontmatter.load(matches[0], encoding="utf-8")
        post.metadata.update({"status": "verified", "verified_by": args.by, "last_verified": today().isoformat()})
        if post.metadata.get("owner") in (None, "", "unassigned"):
            post.metadata["owner"] = args.by
        matches[0].write_text(frontmatter.dumps(post, sort_keys=False) + "\n", encoding="utf-8")
    return cmd_validate(args)


def cmd_post(args: argparse.Namespace) -> int:
    """Post a short-lived message (menu, bus update, announcement) copied from a WhatsApp group."""
    from datetime import date as _date

    from .db import connect
    from .embedding import get_embedder
    from .notes import post_note

    text = Path(args.file).read_text(encoding="utf-8") if args.file else args.text
    if not text:
        print("Provide --text or --file", file=sys.stderr)
        return 1
    on = _date.fromisoformat(args.date) if args.date else None
    until = _date.fromisoformat(args.until) if args.until else None
    with connect() as conn:
        doc_id = post_note(conn, get_embedder(), args.kind, text, args.by, on=on, title=args.title, valid_until=until)
    print(f"posted {doc_id}")
    return 0


def cmd_notes_prune(_: argparse.Namespace) -> int:
    from .db import connect
    from .notes import prune_expired

    with connect() as conn:
        print(f"removed {prune_expired(conn)} expired posts")
    return 0


def cmd_scaffold(args: argparse.Namespace) -> int:
    from .catalog import write_checklist, write_incoming_guides, write_sheet_templates, write_stubs

    created, skipped = write_stubs(force=args.force)
    print(f"stubs: {len(created)} created, {len(skipped)} kept")
    print(f"sheet templates: {len(write_sheet_templates())}")
    print(f"incoming folders: {len(write_incoming_guides())}")
    for path in write_checklist():
        print(f"wrote {path}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from .db import connect
    from .embedding import get_embedder
    from .search import search

    with connect() as conn:
        outcome = search(conn, get_embedder(), args.query, args.top_k)
    print(f"confidence: {outcome.confidence}")
    for r in outcome.results:
        print(f"{r['similarity']:.3f}  {r['document']['id']}  [{r['heading_path']}]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ictkb", description="ICT University knowledge base tools")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="validate content files against the schema").set_defaults(func=cmd_validate)
    sub.add_parser("migrate", help="apply database migrations").set_defaults(func=cmd_migrate)

    s = sub.add_parser("index", help="index content/ into the database")
    s.add_argument("--force", action="store_true", help="re-embed every document")
    s.set_defaults(func=cmd_index)

    s = sub.add_parser("sync-sheets", help="sync Google Sheets into the index")
    s.add_argument("--name")
    s.add_argument("--tier", action="append", choices=["realtime", "daily", "semester", "static"])
    s.set_defaults(func=cmd_sync_sheets)

    s = sub.add_parser("crawl", help="read the university website into the index")
    s.add_argument("--dry-run", action="store_true", help="write Markdown snapshots instead of indexing")
    s.add_argument("--out", default="data/web-snapshot")
    s.set_defaults(func=cmd_crawl)

    s = sub.add_parser("intake", help="upload and register files from incoming/")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--local", action="store_true", help="skip the Cloudinary upload")
    s.set_defaults(func=cmd_intake)

    sub.add_parser("reindex", help="re-embed all chunks after changing the embedding model").set_defaults(func=cmd_reindex)

    s = sub.add_parser("freshness", help="list stale documents")
    s.add_argument("--json", action="store_true")
    s.add_argument("--db", action="store_true", help="include documents known only to the database")
    s.set_defaults(func=cmd_freshness)

    s = sub.add_parser("keys", help="manage API keys")
    ks = s.add_subparsers(dest="action", required=True)
    c = ks.add_parser("create")
    c.add_argument("--owner", required=True)
    c.add_argument("--rate-limit", type=int)
    ks.add_parser("list")
    r = ks.add_parser("revoke")
    r.add_argument("key_id")
    s.set_defaults(func=cmd_keys)

    s = sub.add_parser("verify", help="set documents to verified (after human review)")
    s.add_argument("ids", nargs="+")
    s.add_argument("--by", required=True, help="GitHub handle of the person who checked the content")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("post", help="post a menu, bus update or announcement")
    s.add_argument("kind", choices=["canteen-menu", "bus-update", "announcement", "student-life-post"])
    s.add_argument("--text")
    s.add_argument("--file", help="read the message from a text file")
    s.add_argument("--by", required=True, help="GitHub handle of the person posting")
    s.add_argument("--date", help="day the post applies to (YYYY-MM-DD), default today")
    s.add_argument("--until", help="last valid day (YYYY-MM-DD)")
    s.add_argument("--title", help="short title (bus updates and announcements)")
    s.set_defaults(func=cmd_post)

    sub.add_parser("notes-prune", help="delete expired posts").set_defaults(func=cmd_notes_prune)

    s = sub.add_parser("scaffold", help="generate stubs, sheet templates and the checklist from the catalog")
    s.add_argument("--force", action="store_true", help="overwrite existing stubs")
    s.set_defaults(func=cmd_scaffold)

    s = sub.add_parser("search", help="run a query from the command line")
    s.add_argument("query")
    s.add_argument("--top-k", type=int, default=5)
    s.set_defaults(func=cmd_search)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
