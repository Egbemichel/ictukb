"""Run the golden question set against the configured index.

Usage: python eval/run_eval.py [--k 5] [--strict] [--report eval/reports/latest.md]
Exit status is non-zero when the targets are not met on the covered questions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ictkb.config import get_settings
from ictkb.db import connect
from ictkb.embedding import get_embedder
from ictkb.evaluation import evaluate, load_golden, markdown_report, passes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--strict", action="store_true", help="also fail when expected documents are missing")
    parser.add_argument("--golden", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--api", default=None, help="evaluate a deployed API instead of the local search")
    parser.add_argument("--key", default=None, help="API key for --api")
    args = parser.parse_args()

    settings = get_settings()
    golden = load_golden(args.golden or settings.root / "eval" / "golden_questions.yml")
    search_fn = None
    if args.api:
        import time

        import httpx

        def search_fn(question: str) -> dict:
            time.sleep(1.1)  # stay under the per-key rate limit
            for attempt in range(6):
                try:
                    r = httpx.post(f"{args.api.rstrip('/')}/v1/search", json={"query": question, "top_k": args.k},
                                   headers={"X-API-Key": args.key}, timeout=90)
                except httpx.TransportError:
                    time.sleep(5 * (attempt + 1))
                    continue
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(8 * (attempt + 1))
                    continue
                r.raise_for_status()
                return r.json()
            raise RuntimeError("the API did not answer")

    with connect() as conn:
        result = evaluate(conn, None if args.api else get_embedder(), golden, args.k, search_fn)
    report = markdown_report(result)
    print(report)
    target = args.report or settings.root / "eval" / "reports" / "latest.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8")
    ok, problems = passes(result["summary"], args.strict)
    for p in problems:
        print(f"FAIL: {p}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
