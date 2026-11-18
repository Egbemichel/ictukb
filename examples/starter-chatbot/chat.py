"""Starter retrieval-augmented chatbot. Replace generate() with the language model of your choice."""

from __future__ import annotations

from kb_client import search

NOT_KNOWN = "I do not have that information. Please ask the relevant office."


def build_prompt(question: str, results: list[dict]) -> str:
    context = "\n\n".join(
        f"[{i}] {r['document']['title']} (verified {r['document']['last_verified']})\n{r['text']}"
        for i, r in enumerate(results, 1)
    )
    return (
        "Answer the student's question using only the sources below. "
        "If they do not contain the answer, say so. Cite sources as [n].\n\n"
        f"Sources:\n{context}\n\nQuestion: {question}"
    )


def generate(prompt: str) -> str:
    """Call your language model here and return its text. This stub echoes the prompt."""
    return prompt


def answer(question: str) -> str:
    found = search(question, top_k=5)
    if found["confidence"] != "high":
        return NOT_KNOWN
    reply = generate(build_prompt(question, found["results"]))
    if any(r["document"]["stale"] for r in found["results"]):
        reply += "\n\nNote: some of this information may be out of date."
    return reply


if __name__ == "__main__":
    while True:
        print(answer(input("> ")))
