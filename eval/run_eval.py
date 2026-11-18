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
    args = parser.parse_args()

    settings = get_settings()
    golden = load_golden(args.golden or settings.root / "eval" / "golden_questions.yml")
    with connect() as conn:
        result = evaluate(conn, get_embedder(), golden, args.k)
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
