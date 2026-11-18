"""Build CONTRIBUTORS.md from contributors.yml, and check the file.

Usage:
  python scripts/build_contributors.py            write CONTRIBUTORS.md
  python scripts/build_contributors.py --check    fail if the entries are invalid or CONTRIBUTORS.md is out of date
  python scripts/build_contributors.py --check --author LOGIN
                                                  also fail if LOGIN (a pull request author) has no entry
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contributors.yml"
TARGET = ROOT / "CONTRIBUTORS.md"
MATRICULE = re.compile(r"^ICTU\d{8}$")
BOTS = {"dependabot[bot]", "github-actions[bot]"}


def load() -> list[dict]:
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8")) or {}
    return data.get("contributors", [])


def problems(people: list[dict]) -> list[str]:
    found, seen = [], set()
    for p in people:
        who = p.get("name") or "(no name)"
        if not p.get("name"):
            found.append("an entry has no name")
        if not MATRICULE.match(str(p.get("matricule", ""))):
            found.append(f"{who}: matricule must look like ICTU20230000")
        if p.get("matricule") in seen:
            found.append(f"{who}: duplicate matricule")
        seen.add(p.get("matricule"))
        if not p.get("contribution"):
            found.append(f"{who}: contribution is empty")
    return found


def render(people: list[dict]) -> str:
    lines = [
        "# Contributors",
        "",
        "This list is built from `contributors.yml`. Each person who adds to the knowledge base adds one entry",
        "in the same pull request as their work. The full history of changes is also on the",
        "[GitHub contributors page](https://github.com/Egbemichel/ictukb/graphs/contributors).",
        "",
        "| Name | Matricule | GitHub | Contribution | Since |",
        "|------|-----------|--------|--------------|-------|",
    ]
    for p in sorted(people, key=lambda x: str(x["since"]) + x["name"]):
        handle = f"[{p['github']}](https://github.com/{p['github']})" if p.get("github") else "-"
        lines.append(f"| {p['name']} | {p['matricule']} | {handle} | {p['contribution']} | {p['since']} |")
    lines += ["", "To be listed, copy an entry in `contributors.yml`, fill in your own details and keep the file sorted by date of joining.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--author")
    args = ap.parse_args()
    people = load()
    errors = problems(people)
    if args.author and args.author not in BOTS:
        handles = {str(p.get("github", "")).lower() for p in people}
        if args.author.lower() not in handles:
            errors.append(f"pull request author '{args.author}' is not in contributors.yml: add an entry with your name, matricule and GitHub login")
    text = render(people)
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != text:
            errors.append("CONTRIBUTORS.md is out of date: run python scripts/build_contributors.py")
        for e in errors:
            print("error:", e)
        return 1 if errors else 0
    if errors:
        for e in errors:
            print("error:", e)
        return 1
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET.name} ({len(people)} contributors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
