"""Retrieval evaluation against the golden question set.

Metrics: hit@k (an expected document appears in the top k; every expected document for
multi-hop questions), mean reciprocal rank, and no-answer correctness. Because the golden set
is written before the content exists, results are reported over the questions whose expected
documents are already indexed ("covered"), together with the coverage itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from .embedding import Embedder
from .search import search
from .util import load_yaml

TARGET_OVERALL = 0.85
TARGET_P0 = 0.95


def load_golden(path: Path) -> list[dict]:
    return load_yaml(path)


def matches(expected: str, doc_id: str) -> bool:
    return doc_id == expected or doc_id.startswith(expected + "-")


def indexed_ids(conn: psycopg.Connection) -> set[str]:
    return {r["id"] for r in conn.execute("SELECT id FROM documents").fetchall()}


def _present(expected: str, ids: set[str]) -> bool:
    return any(matches(expected, i) for i in ids)


@dataclass
class Outcome:
    id: str
    priority: str
    type: str
    covered: bool
    hit: bool | None = None
    rr: float = 0.0
    top_similarity: float = 0.0
    confidence: str = "none"
    returned: list[str] = field(default_factory=list)


def evaluate(conn: psycopg.Connection, embedder: Embedder | None, questions: list[dict], k: int = 5,
             search_fn=None) -> dict:
    ids = indexed_ids(conn)
    if search_fn is not None:
        conn.close()  # the deployed API is slow; do not hold an idle database connection
    outcomes: list[Outcome] = []
    for q in questions:
        expected = q.get("expected_docs") or []
        is_neg = q["type"] == "no-answer"
        if is_neg:
            covered = True
        elif q["type"] == "multi-hop":
            covered = all(_present(e, ids) for e in expected)
        else:
            covered = any(_present(e, ids) for e in expected)
        if search_fn is not None:
            payload = search_fn(q["question"])  # the deployed API: {"confidence": ..., "results": [...]}
            confidence, results = payload["confidence"], payload["results"]
        else:
            outcome = search(conn, embedder, q["question"], top_k=k)
            confidence, results = outcome.confidence, outcome.results
        returned = [r["document"]["id"] for r in results]
        o = Outcome(q["id"], q["priority"], q["type"], covered, confidence=confidence,
                    returned=returned, top_similarity=max((r["similarity"] for r in results), default=0.0))
        if is_neg:
            o.hit = confidence in ("low", "none")
        elif covered:
            if q["type"] == "multi-hop":
                o.hit = all(any(matches(e, d) for d in returned) for e in expected if _present(e, ids))
            else:
                o.hit = any(matches(e, d) for e in expected for d in returned)
            for rank, d in enumerate(returned, 1):
                if any(matches(e, d) for e in expected):
                    o.rr = 1.0 / rank
                    break
        outcomes.append(o)

    positives = [o for o in outcomes if o.type != "no-answer"]
    covered = [o for o in positives if o.covered]
    p0 = [o for o in covered if o.priority == "P0"]
    neg = [o for o in outcomes if o.type == "no-answer"]

    def rate(items: list[Outcome]) -> float | None:
        return sum(1 for o in items if o.hit) / len(items) if items else None

    summary = {
        "questions": len(questions),
        "answerable": len(positives),
        "covered": len(covered),
        "coverage": len(covered) / len(positives) if positives else 0.0,
        "hit_at_k": rate(covered),
        "hit_at_k_p0": rate(p0),
        "mrr": sum(o.rr for o in covered) / len(covered) if covered else None,
        "no_answer_correct": rate(neg),
        "answered_high": (sum(1 for o in covered if o.hit and o.confidence == "high") / len([o for o in covered if o.hit])) if any(o.hit for o in covered) else None,
        "p0_covered": len(p0),
        "p0_total": sum(1 for o in positives if o.priority == "P0"),
        "k": k,
        "min_top_similarity_answerable": min((o.top_similarity for o in covered if o.hit), default=None),
        "max_top_similarity_no_answer": max((o.top_similarity for o in neg), default=None),
    }
    return {"summary": summary, "outcomes": outcomes}


def passes(summary: dict, strict: bool) -> tuple[bool, list[str]]:
    problems = []
    if summary["hit_at_k"] is not None and summary["hit_at_k"] < TARGET_OVERALL:
        problems.append(f"hit@{summary['k']} {summary['hit_at_k']:.2%} is below {TARGET_OVERALL:.0%}")
    if summary["hit_at_k_p0"] is not None and summary["hit_at_k_p0"] < TARGET_P0:
        problems.append(f"P0 hit@{summary['k']} {summary['hit_at_k_p0']:.2%} is below {TARGET_P0:.0%}")
    if strict and summary["coverage"] < 1.0:
        problems.append(f"coverage {summary['coverage']:.2%}: some expected documents are not indexed")
    return not problems, problems


def markdown_report(result: dict) -> str:
    s = result["summary"]

    def pct(v):
        return "n/a" if v is None else f"{v:.1%}"

    lines = [
        "# Retrieval evaluation", "",
        "| Metric | Value |", "|---|---|",
        f"| Questions | {s['questions']} |",
        f"| Answerable questions with indexed documents (coverage) | {s['covered']} of {s['answerable']} ({pct(s['coverage'])}) |",
        f"| hit@{s['k']} on covered questions | {pct(s['hit_at_k'])} (target {TARGET_OVERALL:.0%}) |",
        f"| hit@{s['k']} on covered P0 questions | {pct(s['hit_at_k_p0'])} (target {TARGET_P0:.0%}), {s['p0_covered']} of {s['p0_total']} P0 covered |",
        f"| Mean reciprocal rank | {pct(s['mrr'])} |",
        f"| Retrieved correctly and answered with high confidence | {pct(s['answered_high'])} |",
        f"| No-answer correctness | {pct(s['no_answer_correct'])} |",
        f"| Lowest top similarity among answered questions | {s['min_top_similarity_answerable']} |",
        f"| Highest top similarity among no-answer questions | {s['max_top_similarity_no_answer']} |",
        "", "## Failures", "", "| Question | Priority | Confidence | Returned documents |", "|---|---|---|---|",
    ]
    for o in result["outcomes"]:
        if o.covered and o.hit is False:
            lines.append(f"| {o.id} | {o.priority} | {o.confidence} | {', '.join(o.returned[:5])} |")
    lines += ["", "## Not yet covered (expected documents missing from the index)", ""]
    lines.append(", ".join(o.id for o in result["outcomes"] if not o.covered) or "None")
    return "\n".join(lines) + "\n"
