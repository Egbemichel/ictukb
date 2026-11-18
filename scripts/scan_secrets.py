"""Fail when likely secrets are present in tracked text files.

The repository is public and Git history is permanent, so credentials must never be committed.
Personal data rules (email domains, phone numbers) are enforced by "ictkb validate".
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "database URL with password": re.compile(r"postgres(?:ql)?://[^\s:/@]+:(?!ictkb@|password@|<)[^\s@]{4,}@(?!localhost|127\.0\.0\.1|db[:/])"),
    "ictkb API key": re.compile(r"ictkb_[A-Za-z0-9_-]{30,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "assigned secret": re.compile(
        r"(?i)\b(cohere_api_key|cloudinary_api_secret|admin_token|api_secret|secret_key)\s*[=:]\s*['\"]?(?!test-|<|\$\{|changeme|\s)[A-Za-z0-9_\-]{16,}"
    ),
}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".xlsx", ".docx", ".ico", ".lock"}
SKIP_NAMES = {".env.example", "scan_secrets.py"}


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        files = [ROOT / line for line in out.splitlines() if line]
        if files:
            return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    skip_dirs = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "incoming"}
    return [p for p in ROOT.rglob("*") if p.is_file() and not (set(p.relative_to(ROOT).parts) & skip_dirs)]


def main() -> int:
    findings = []
    for path in tracked_files():
        if path.suffix.lower() in SKIP_SUFFIX or path.name in SKIP_NAMES or path.name == ".env":
            if path.name == ".env":
                findings.append((path, 0, "a populated .env file is tracked"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((path, number, label))
    for path, number, label in findings:
        print(f"{path.relative_to(ROOT)}:{number}: possible {label}", file=sys.stderr)
    if findings:
        print(f"{len(findings)} possible secret(s) found. Remove them and rotate the credential.", file=sys.stderr)
        return 1
    print("no secrets found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
