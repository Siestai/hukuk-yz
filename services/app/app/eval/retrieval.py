"""Retrieval eval (task 14): recall@5 and recall@10 of `/kb/search` on the question set.

    python -m app.eval.retrieval [--file PATH] [--limit N]

Per question, recall@k is the share of its expected sources found among the first k results; the
report is the mean over the questions, plus the misses. Scoring is a pure function (`recall`).
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.db import make_engine, make_session_factory
from app.embeddings import make_embedder
from app.search import search
from app.settings import get_settings

DEFAULT_FILE = Path(__file__).parents[4] / "eval" / "retrieval" / "questions.json"
KS = (5, 10)


def matches(expected: dict[str, Any], result: dict[str, Any]) -> bool:
    """Does the search result stand for the expected source? A statute by its `ref`; a decision
    by the chamber and the esas and karar numbers in its `ref`."""
    if result["category"] != expected["category"]:
        return False
    ref = result.get("ref") or ""
    if expected["category"] == "statute":
        return bool(ref == expected["ref"])
    return bool(
        f"{expected['chamber']}," in ref
        and f"E. {expected['esas']} " in f"{ref} "
        and f"K. {expected['karar']}" in ref
    )


def recall(expected: Sequence[dict[str, Any]], results: Sequence[dict[str, Any]], k: int) -> float:
    if not expected:
        return 1.0
    top = results[:k]
    return sum(any(matches(e, r) for r in top) for e in expected) / len(expected)


def report(
    questions: Sequence[dict[str, Any]], ranked: Sequence[Sequence[dict[str, Any]]]
) -> list[str]:
    lines: list[str] = []
    for k in KS:
        mean = sum(recall(q["expected"], r, k) for q, r in zip(questions, ranked, strict=True))
        lines.append(f"recall@{k}: {mean / len(questions):.3f} ({len(questions)} questions)")
    lines.append("misses at the last k:")
    for q, r in zip(questions, ranked, strict=True):
        missed = [e for e in q["expected"] if not any(matches(e, x) for x in r[: KS[-1]])]
        for e in missed:
            label = (
                e["ref"]
                if e["category"] == "statute"
                else (f"{e['chamber']} E. {e['esas']} K. {e['karar']}")
            )
            lines.append(f"  {q['id']}: {label}")
    return lines


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    embedder = make_embedder(settings)
    if embedder is None:
        print("OPENAI_API_KEY is not set: the questions cannot be embedded")
        return 2
    questions = json.loads(Path(args.file).read_text(encoding="utf-8"))
    engine = make_engine(settings.database_url)
    ranked: list[list[dict[str, Any]]] = []
    try:
        factory = make_session_factory(engine)
        for q in questions:
            async with factory() as session:
                found = await search(
                    session,
                    embedder,
                    q=q["question"],
                    include_unreviewed=settings.kb_search_include_unreviewed,
                    limit=args.limit,
                )
            ranked.append([r.model_dump(mode="json") for r in found.results])
    finally:
        await engine.dispose()
    print("\n".join(report(questions, ranked)))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--file", default=str(DEFAULT_FILE))
    parser.add_argument("--limit", type=int, default=KS[-1])
    return asyncio.run(_run(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
