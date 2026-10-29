"""The eval runner: `python -m agent.eval eval/cases`.

Runs the agent on every case of the eval set (`eval/cases/*.yaml`), answers its clarification
questions with the facts the case gives (a question the case has no fact for is answered
"Bilmiyorum"), scores the answer with `eval/score.py` and prints one table row per case. Real
models and a real or fixture knowledge base are chosen on the command line; the CI smoke test
runs the same code with fake models.
"""

import argparse
import asyncio
import importlib.util
import json
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml
from langgraph.checkpoint.memory import InMemorySaver

from agent.api import Graph, RunRequest, turn_events
from agent.graph import build_graph
from agent.kb import HttpKbClient, KbClient, KbHit, KbMatch
from agent.llm import Llm, Models
from agent.nodes import Deps
from agent.settings import KbSettings, LlmSettings
from agent.sources import covers, split_ref
from agent.trace import Tracing
from hukuk_models.chat import (
    Answer,
    AnswerEvent,
    CitationRef,
    Clarification,
    ClarificationAnswer,
    ClarificationEvent,
    ErrorEvent,
)

DEFAULT_FIXTURES = Path(__file__).parents[3] / "eval" / "fixtures"


class FixtureKb:
    """A small knowledge base made from the hand-made answers of `eval/fixtures`: every source
    they cite, with the quotes as its text. For runs before the real index (task 14) exists."""

    def __init__(self, directory: Path = DEFAULT_FIXTURES) -> None:
        self._hits: dict[str, KbHit] = {}
        for path in sorted(directory.glob("*.answer.json")):
            answer = Answer.model_validate_json(path.read_text(encoding="utf-8"))
            cited = [c for p in answer.points for c in p.citations]
            cited += [r.citation for r in answer.holding_map.rows]
            for ref in cited:
                self._add(ref)

    def _add(self, ref: CitationRef) -> None:
        if not ref.quote:
            return
        base, sub = split_ref(ref.ref)
        hit = self._hits.setdefault(
            ref.source_id,
            KbHit(
                source_id=ref.source_id,
                category=ref.category,
                title=ref.label.removesuffix(sub),
                ref=base,
                review_status=ref.review_status,
                verification=ref.verification,
                valid_from=ref.valid_from,
                valid_to=ref.valid_to,
            ),
        )
        # The fixtures contain quoted excerpts, not paragraph boundaries. Preserve the
        # literal text and its original offsets; never invent a marker to validate a sub.
        text = ref.quote
        if all(m.text != text for m in hit.matches):
            hit.matches.append(
                KbMatch(
                    chunk_id=f"{ref.source_id}#{len(hit.matches)}",
                    text=text,
                    char_start=ref.char_start,
                    char_end=ref.char_end,
                )
            )

    async def search(
        self,
        q: str,
        *,
        categories: Sequence[str] = (),
        as_of: date | None = None,
        limit: int = 10,
    ) -> list[KbHit]:
        words = {w for w in q.casefold().split() if len(w) > 3}

        def rank(hit: KbHit) -> int:
            text = " ".join(m.text or "" for m in hit.matches).casefold()
            return 100 * covers(hit.ref, q) + sum(w in text for w in words)

        found = [
            h
            for h in self._hits.values()
            if (not categories or h.category in categories)
            and (
                as_of is None
                or (
                    (h.valid_from is None or h.valid_from <= as_of)
                    and (h.valid_to is None or as_of < h.valid_to)
                )
            )
            and rank(h) > 0
        ]
        return sorted(found, key=rank, reverse=True)[:limit]


@dataclass
class CaseResult:
    case_id: str
    answer: dict[str, Any] | None
    metrics: dict[str, float | None]
    score: float
    dropped: int
    fell_back: bool
    input_tokens: int
    output_tokens: int
    cost: float | None
    seconds: float
    error: str | None = None


def load_score_module(cases_dir: Path) -> ModuleType:
    """`eval/score.py` next to the cases folder (it is a script, not a package)."""
    path = cases_dir.resolve().parent / "score.py"
    spec = importlib.util.spec_from_file_location("eval_score", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def answers_for(clarification: Clarification, facts: dict[str, str]) -> list[ClarificationAnswer]:
    """The case's value for each question, or "Bilmiyorum" where it has none."""
    return [
        ClarificationAnswer(question_id=q.id, value=str(facts[q.fact_key]))
        if q.fact_key in facts
        else ClarificationAnswer(question_id=q.id, unknown=True)
        for q in clarification.questions
    ]


async def run_case(
    graph: Graph, tracing: Tracing, score: ModuleType, case: dict[str, Any]
) -> CaseResult:
    thread_id = f"eval-{case['id']}-{uuid.uuid4().hex[:8]}"
    clarification: Clarification | None = None
    answer: Answer | None = None
    error = None
    with tracing.run(thread_id) as trace:
        request = RunRequest(thread_id=thread_id, text=case["question"])
        for _ in range(2):
            pending: Clarification | None = None
            async for event in turn_events(graph, request, trace):
                if isinstance(event, ClarificationEvent):
                    pending = clarification = event.clarification
                elif isinstance(event, AnswerEvent):
                    answer = event.answer
                elif isinstance(event, ErrorEvent):
                    error = str(event.params.get("reason", event.code))
            if pending is None:
                break
            request = RunRequest(
                thread_id=thread_id,
                clarification_answers=answers_for(pending, case.get("facts") or {}),
            )
    # A case that stopped before the draft (an error, an unanswered clarification) has no gate.
    state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    gate = state.values.get("gate") or {}
    metrics: dict[str, float | None] = {}
    total = 0.0
    if answer is not None:
        raw = answer.model_dump(mode="json")
        scored = score.score(
            raw, case, clarification.model_dump(mode="json") if clarification else None
        )
        metrics = {m.name: m.value for m in scored}
        total = score.total(scored)
    return CaseResult(
        case_id=case["id"],
        answer=answer.model_dump(mode="json") if answer else None,
        metrics=metrics,
        score=total,
        dropped=gate.get("citations_dropped", 0)
        + gate.get("points_dropped", 0)
        + gate.get("rows_dropped", 0),
        fell_back=gate.get("fallback", False),
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        cost=trace.cost,
        seconds=trace.seconds,
        error=error,
    )


def render(results: list[CaseResult]) -> str:
    def cell(value: float | None) -> str:
        return "-" if value is None else f"{value:.2f}"

    header = (
        f"{'vaka':<8}{'puan':>6}{'must_cite':>11}{'must_ask':>10}{'düşen':>7}"
        f"{'token (gir/çık)':>18}{'maliyet $':>11}{'süre s':>8}  not"
    )
    lines = [header]
    for r in results:
        note = r.error or ("kapıdan geçemedi" if r.fell_back else "")
        lines.append(
            f"{r.case_id:<8}{cell(r.score if r.answer else None):>6}"
            f"{cell(r.metrics.get('must_cite')):>11}{cell(r.metrics.get('must_ask')):>10}"
            f"{r.dropped:>7}{f'{r.input_tokens}/{r.output_tokens}':>18}"
            f"{cell(r.cost):>11}{r.seconds:>8.1f}  {note}".rstrip()
        )
    return "\n".join(lines)


def build_eval_graph(models: Models, kb: KbClient) -> Graph:
    return build_graph(Deps(llm=Llm(models), kb=kb), InMemorySaver())


async def run_eval(
    graph: Graph,
    tracing: Tracing,
    cases_dir: Path,
    only: Sequence[str] = (),
) -> list[CaseResult]:
    score = load_score_module(cases_dir)
    results = []
    for path in sorted(cases_dir.glob("*.yaml")):
        case = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not only or case["id"] in only:
            results.append(await run_case(graph, tracing, score, case))
    return results


async def amain(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m agent.eval", description=__doc__.split("\n")[0]
    )
    parser.add_argument("cases", type=Path, help="the folder of the cases, eval/cases")
    parser.add_argument("--case", action="append", default=[], help="only this case id (repeat)")
    parser.add_argument(
        "--kb",
        choices=("http", "fixtures"),
        default="http",
        help="http: /kb/search of `app` (APP_BASE_URL, KB_SERVICE_KEY); fixtures: the cited "
        "sources of eval/fixtures",
    )
    parser.add_argument("--json", type=Path, help="also write the answers and metrics here")
    args = parser.parse_args(argv)

    settings = LlmSettings()
    tracing = Tracing.from_settings(settings)
    kb: KbClient
    if args.kb == "fixtures":
        kb = FixtureKb()
    else:
        kb_settings = KbSettings()
        kb = HttpKbClient(
            kb_settings.app_base_url, kb_settings.kb_service_key, kb_settings.kb_timeout_seconds
        )
    graph = build_eval_graph(Models(settings.agent_model_fast, settings.agent_model_strong), kb)
    try:
        results = await run_eval(graph, tracing, args.cases, args.case)
    finally:
        if isinstance(kb, HttpKbClient):
            await kb.aclose()
        tracing.shutdown()
    print(render(results))
    if args.json:
        args.json.write_text(
            json.dumps([vars(r) for r in results], ensure_ascii=False, indent=1, default=str),
            encoding="utf-8",
        )
    return 0 if all(r.answer is not None for r in results) else 1


def main() -> None:
    sys.exit(asyncio.run(amain(sys.argv[1:])))


if __name__ == "__main__":
    main()
