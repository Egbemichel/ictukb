"""Heading-aware Markdown chunking.

Each chunk is prefixed with the document title and its heading path so that it is
self-contained when retrieved on its own. Tables are split by rows and the header
row is repeated in every piece.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .util import approx_tokens

MAX_TOKENS = 380
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


@dataclass
class Chunk:
    heading_path: str
    content: str
    source: str = "body"


def _sections(body: str) -> list[tuple[str, str]]:
    """Split Markdown into (heading_path, text) sections, ignoring headings inside code fences."""
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, list[str]]] = [("", [])]
    in_fence = False
    for line in body.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else HEADING.match(line)
        if match:
            level, title = len(match.group(1)), match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            sections.append((" > ".join(t for _, t in stack), []))
        else:
            sections[-1][1].append(line)
    return [(path, "\n".join(lines).strip()) for path, lines in sections if "\n".join(lines).strip()]


def _blocks(text: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def _is_table(block: str) -> bool:
    lines = block.splitlines()
    return len(lines) >= 2 and all(line.lstrip().startswith("|") for line in lines)


def _split_table(block: str, max_tokens: int) -> list[str]:
    lines = block.splitlines()
    header, rows = lines[:2], lines[2:]
    pieces, current = [], []
    for row in rows:
        if current and approx_tokens("\n".join(header + current + [row])) > max_tokens:
            pieces.append("\n".join(header + current))
            current = []
        current.append(row)
    if current:
        pieces.append("\n".join(header + current))
    return pieces or [block]


def _split_text(block: str, max_tokens: int) -> list[str]:
    if approx_tokens(block) <= max_tokens:
        return [block]
    sentences = re.split(r"(?<=[.!?])\s+|\n", block)
    pieces, current = [], ""
    for sentence in sentences:
        if current and approx_tokens(current + " " + sentence) > max_tokens:
            pieces.append(current.strip())
            current = ""
        current += (" " if current else "") + sentence
    if current.strip():
        pieces.append(current.strip())
    return pieces


def chunk_markdown(title: str, body: str, max_tokens: int = MAX_TOKENS, source: str = "body") -> list[Chunk]:
    chunks: list[Chunk] = []
    for path, text in _sections(body):
        pieces: list[str] = []
        current = ""
        for block in _blocks(text):
            parts = _split_table(block, max_tokens) if _is_table(block) else _split_text(block, max_tokens)
            for part in parts:
                if current and approx_tokens(current + "\n\n" + part) > max_tokens:
                    pieces.append(current)
                    current = ""
                current = f"{current}\n\n{part}" if current else part
        if current:
            pieces.append(current)
        label = f"{title} | {path}" if path else title
        for piece in pieces:
            chunks.append(Chunk(heading_path=path, content=f"{label}\n\n{piece}", source=source))
    return chunks
