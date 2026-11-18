"""Open one GitHub issue per stale document, assigned to its owner, without creating duplicates.

Usage: python scripts/open_stale_issues.py stale.json   (requires the gh CLI and GH_TOKEN)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

LABEL = "stale-content"
HANDLE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def main(path: str) -> int:
    with open(path, encoding="utf-8") as handle:
        stale = json.load(handle)
    open_titles = {i["title"] for i in json.loads(gh("issue", "list", "--label", LABEL, "--state", "open",
                                                      "--limit", "500", "--json", "title"))}
    created = 0
    for item in stale:
        title = f"Stale content: {item['id']}"
        if title in open_titles:
            continue
        body = (
            f"The document `{item['id']}` (category {item['category']}, tier {item['tier']}) was last verified "
            f"on {item['last_verified']}, {item['age_days']} days ago. The limit for this tier is "
            f"{item['limit_days']} days.\n\nRe-check it against the source, update the content if needed, "
            "and set last_verified to today's date."
        )
        args = ["issue", "create", "--title", title, "--body", body, "--label", LABEL]
        if HANDLE.match(item["owner"]) and item["owner"] != "unassigned":
            args += ["--assignee", item["owner"]]
        try:
            gh(*args)
            created += 1
        except subprocess.CalledProcessError as exc:
            print(f"could not create issue for {item['id']}: {exc.stderr.strip()}", file=sys.stderr)
    print(f"{len(stale)} stale documents, {created} new issues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "stale.json"))
