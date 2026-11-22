"""The eval runner: `python -m agent.eval eval/cases`.

Runs the agent on every case of the eval set (`eval/cases/*.yaml`), answers its clarification
questions with the facts the case gives (a question the case has no fact for is answered
"Bilmiyorum"), scores the answer with `eval/score.py` and prints the acceptance table (one row per
case, the total, PASS or FAIL against the thresholds of task 19). The result goes to
`eval/results/<date>-<tag>.json` and the table next to it as `.md`.

Budget: `--estimate` prints the expected cost and calls no model; `--budget-usd` is a hard cap,
checked after every model call and before every case. Real models and a real or fixture knowledge
base are chosen on the command line; the CI smoke test runs the same code with fake models.
"""

import argparse
import asyncio
import importlib.util
import json
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml
from langgraph.checkpoint.memory import InMemorySaver

from agent.api import Graph, RunRequest, turn_events
from agent.graph import build_graph
from agent.kb import HttpKbClient, KbClient, KbHit, KbMatch, Unreadable
from agent.llm import Llm, Models, Tier, _cost, _model_name
from agent.llm_schemas import IntakeOutput
from agent.nodes import Deps
from agent.settings import KbSettings, LlmSettings
from agent.sources import covers, split_ref
from agent.trace import Trace, Tracing, current_record
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
# The tokens (input, output) of one case by model tier, for an estimate before any real run:
# intake and holding map on the fast model, the draft (and a rewrite) on the strong one.
ASSUMED_TOKENS: dict[Tier, tuple[int, int]] = {"fast": (30_000, 4_000), "strong": (30_000, 6_000)}
DROP_KEYS = ("rows", "points", "branches", "sentences", "citations")


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
                band=ref.band,
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

    async def read_article(self, ref: str, as_of: date) -> list[KbHit]:
        return await self.search(ref, categories=["statute"], as_of=as_of)

    async def read_section(self, ref: str, as_of: date) -> KbHit | Unreadable:
        found = await self.search(ref, categories=["admin_act"], as_of=as_of)
        return next((h for h in found if h.ref == ref), Unreadable("not_found"))


class BudgetExceeded(Exception):
    """The spend passed the cap: no further model call."""


@dataclass
class Budget:
    """The hard cap of a run in USD. `per_case` is the estimate of one case: a case starts only
    when it fits in what is left."""

    cap: float
    per_case: float
    spent: float = 0.0

    @property
    def exceeded(self) -> bool:
        return self.spent > self.cap

    def charge(self, cost: float) -> None:
        self.spent += cost
        if self.exceeded:
            raise BudgetExceeded

    def allows_next(self) -> bool:
        return self.spent + self.per_case <= self.cap


class EvalLlm(Llm):
    """The models of an eval run: after every call the spend is charged to the budget, and the
    output of the intake is kept for the case in progress (`--record-intake`)."""

    def __init__(self, models: Models, budget: Budget | None = None) -> None:
        super().__init__(models)
        self.budget = budget
        self.intake: dict[str, Any] | None = None

    async def run[T](self, tier: Tier, output_type: type[T], instructions: str, prompt: str) -> T:
        record = current_record()
        before = (record.cost or 0.0) if record else 0.0
        output = await super().run(tier, output_type, instructions, prompt)
        if isinstance(output, IntakeOutput):
            self.intake = output.model_dump(mode="json", exclude_unset=True)
        if self.budget is not None and record is not None:
            self.budget.charge((record.cost or 0.0) - before)
        return output


@dataclass(frozen=True)
class Estimate:
    per_case: float | None
    source: str


def _earlier_costs(results_dir: Path) -> tuple[list[float], int]:
    """The real cost of every case of the earlier runs that ended without an error, and the
    number of result files."""
    costs = []
    paths = sorted(results_dir.glob("*.json"))
    for path in paths:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        cases = loaded if isinstance(loaded, list) else loaded.get("cases", [])
        costs += [
            c["cost"]
            for c in cases
            if isinstance(c, dict) and c.get("cost") is not None and c.get("error") is None
        ]
    return costs, len(paths)


def estimate(results_dir: Path, models: Models) -> Estimate:
    """The cost of one case: the mean real cost of the earlier runs in `results_dir`, otherwise
    `ASSUMED_TOKENS` at the price of the models (genai-prices, as the trace)."""
    costs, files = _earlier_costs(results_dir)
    if costs:
        mean = sum(costs) / len(costs)
        return Estimate(mean, f"önceki koşular: {len(costs)} vaka, {files} sonuç dosyası")
    total = 0.0
    for model, tokens in (
        (models.fast, ASSUMED_TOKENS["fast"]),
        (models.strong, ASSUMED_TOKENS["strong"]),
    ):
        price = _cost(model, *tokens)
        if price is None:
            return Estimate(None, f"fiyat tablosunda yok: {_model_name(model)}")
        total += price
    assumed = ", ".join(f"{t} {i}/{o}" for t, (i, o) in ASSUMED_TOKENS.items())
    return Estimate(total, f"varsayım: vaka başına token (gir/çık) {assumed}, genai-prices fiyatı")


@dataclass
class CaseResult:
    """One case of a run; the keys of a row of `eval/score.py` `render_table`."""

    case_id: str
    trace_id: str
    expected_topic: str | None
    topic: str | None
    # The intake output: the fields the model set, after the schema check of Pydantic AI.
    intake: dict[str, Any] | None
    asked: list[str]
    answer: dict[str, Any] | None
    metrics: dict[str, float | None]
    score: float
    must_ask: float | None
    must_cite: float | None
    missing_in_kb: list[str]
    must_not: list[str]
    headline: float | None
    mode: list[str]
    unread: list[str]
    drops: dict[str, int]
    issue_counts: dict[str, int]
    fallback: bool
    substantive: bool
    input_tokens: int
    output_tokens: int
    cost: float | None
    seconds: float
    error: str | None = None


@dataclass
class EvalRun:
    results: list[CaseResult] = field(default_factory=list)
    # The cases the budget stopped before they started.
    not_run: list[str] = field(default_factory=list)


def load_score_module(cases_dir: Path) -> ModuleType:
    """`eval/score.py` next to the cases folder (it is a script, not a package)."""
    path = cases_dir.resolve().parent / "score.py"
    spec = importlib.util.spec_from_file_location("eval_score", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_cases(cases_dir: Path, only: Sequence[str] = ()) -> list[dict[str, Any]]:
    cases = [
        yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(cases_dir.glob("*.yaml"))
    ]
    return [c for c in cases if not only or c["id"] in only]


def answers_for(clarification: Clarification, facts: dict[str, str]) -> list[ClarificationAnswer]:
    """The case's value for each question, or "Bilmiyorum" where it has none."""
    return [
        ClarificationAnswer(question_id=q.id, value=str(facts[q.fact_key]))
        if q.fact_key in facts
        else ClarificationAnswer(question_id=q.id, unknown=True)
        for q in clarification.questions
    ]


def _issue_counts(trace: Trace) -> dict[str, int]:
    drafts = [r.output.get("issue_counts", {}) for r in trace.records if r.node == "draft"]
    return dict(drafts[-1]) if drafts else {}


async def run_case(
    graph: Graph, llm: EvalLlm, tracing: Tracing, score: ModuleType, case: dict[str, Any]
) -> CaseResult:
    thread_id = f"eval-{case['id']}-{uuid.uuid4().hex[:8]}"
    clarification: Clarification | None = None
    answer: Answer | None = None
    error = None
    llm.intake = None
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
    if llm.budget is not None and llm.budget.exceeded:
        error = "budget_exceeded"
    # A case that stopped before the draft (an error, an unanswered clarification) has no gate.
    state = (await graph.aget_state({"configurable": {"thread_id": thread_id}})).values
    gate = state.get("gate") or {}
    raw = answer.model_dump(mode="json") if answer else None
    # What the run asked: nothing when there was no clarification.
    asked = clarification.model_dump(mode="json") if clarification else {"questions": []}
    scored = score.score(raw, case, asked) if raw is not None else []
    metrics: dict[str, float | None] = {m.name: m.value for m in scored}
    expected = case["expected"]
    read_ids = {s["source_id"] for s in state.get("read", [])}
    return CaseResult(
        case_id=case["id"],
        trace_id=trace.trace_id,
        expected_topic=expected.get("topic"),
        topic=state.get("topic"),
        intake=llm.intake,
        asked=[q["fact_key"] for q in asked["questions"]],
        answer=raw,
        metrics=metrics,
        score=score.total(scored),
        must_ask=score.must_ask_metric(case, asked).value,
        must_cite=score.must_cite_metric(raw or {}, case).value,
        missing_in_kb=list(expected.get("missing_in_kb", [])),
        must_not=score.must_not_found(raw, case) if raw else [],
        headline=metrics.get("headline"),
        mode=score.progressive_found(raw) if raw else [],
        unread=score.unread_citations(raw, read_ids) if raw else [],
        drops={k: gate.get(f"{k}_dropped", 0) for k in DROP_KEYS},
        issue_counts=_issue_counts(trace),
        fallback=gate.get("fallback", False),
        substantive=raw is not None and raw.get("source_gap") is None,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        cost=trace.cost,
        seconds=trace.seconds,
        error=error,
    )


def build_eval_graph(llm: Llm, kb: KbClient) -> Graph:
    return build_graph(Deps(llm=llm, kb=kb), InMemorySaver())


async def run_eval(
    graph: Graph,
    llm: EvalLlm,
    tracing: Tracing,
    cases_dir: Path,
    only: Sequence[str] = (),
) -> EvalRun:
    """The cases in order; with a budget, a case starts only when its estimate fits in what is
    left, and the run stops at the first case the cap stopped."""
    score = load_score_module(cases_dir)
    run = EvalRun()
    cases = load_cases(cases_dir, only)
    for i, case in enumerate(cases):
        budget = llm.budget
        if budget is not None and (budget.exceeded or not budget.allows_next()):
            run.not_run = [c["id"] for c in cases[i:]]
            break
        run.results.append(await run_case(graph, llm, tracing, score, case))
    return run


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    parser.add_argument("--tag", default="eval", help="the name of the run: <date>-<tag>.json")
    parser.add_argument(
        "--results", type=Path, help="where the result goes (default: eval/results)"
    )
    parser.add_argument(
        "--record-intake", type=Path, help="also write the intake output of each case here"
    )
    parser.add_argument(
        "--estimate", action="store_true", help="print the expected cost; call no model"
    )
    parser.add_argument("--budget-usd", type=float, help="hard cap of the run's model spend")
    args = parser.parse_args(argv)

    settings = LlmSettings()
    names = Models(settings.agent_model_fast, settings.agent_model_strong)
    results_dir = args.results or args.cases.resolve().parent / "results"
    cases = load_cases(args.cases, args.case)
    made = estimate(results_dir, names)
    per_case = "?" if made.per_case is None else f"${made.per_case:.3f}"
    total = "?" if made.per_case is None else f"${made.per_case * len(cases):.2f}"
    print(f"tahmin: {len(cases)} vaka × {per_case} = {total} ({made.source})")
    if args.estimate:
        return 0
    budget = None
    if args.budget_usd is not None:
        if made.per_case is None:
            print(f"bütçe tutulamaz: {made.source}", file=sys.stderr)
            return 2
        budget = Budget(cap=args.budget_usd, per_case=made.per_case)

    tracing = Tracing.from_settings(settings)
    kb: KbClient
    if args.kb == "fixtures":
        kb = FixtureKb()
    else:
        kb_settings = KbSettings()
        kb = HttpKbClient(
            kb_settings.app_base_url, kb_settings.kb_service_key, kb_settings.kb_timeout_seconds
        )
    llm = EvalLlm(Models(settings.agent_model_fast, settings.agent_model_strong), budget)
    graph = build_eval_graph(llm, kb)
    try:
        run = await run_eval(graph, llm, tracing, args.cases, args.case)
    finally:
        if isinstance(kb, HttpKbClient):
            await kb.aclose()
        tracing.shutdown()

    score = load_score_module(args.cases)
    rows = [vars(r) for r in run.results]
    passed, reasons = score.acceptance(rows, run.not_run)
    spent = sum(r.cost or 0.0 for r in run.results)
    table = score.render_table(rows, passed, reasons)
    print(table)
    print(f"harcanan: ${spent:.4f}" + (f" / tavan ${budget.cap:.2f}" if budget else ""))
    base = results_dir / f"{date.today().isoformat()}-{args.tag}"
    result = {
        "tag": args.tag,
        "date": date.today().isoformat(),
        "models": {"fast": _model_name(names.fast), "strong": _model_name(names.strong)},
        "kb": args.kb,
        "estimate": {"per_case_usd": made.per_case, "source": made.source},
        "budget_usd": args.budget_usd,
        "spent_usd": spent,
        "passed": passed,
        "reasons": reasons,
        "not_run": run.not_run,
        "cases": rows,
    }
    _write(
        base.with_suffix(".json"),
        json.dumps(result, ensure_ascii=False, indent=1, default=str),
    )
    _write(base.with_suffix(".md"), f"# Eval {args.tag} ({date.today().isoformat()})\n\n{table}\n")
    if args.record_intake:
        for r in run.results:
            if r.intake is not None:
                _write(
                    args.record_intake / f"{r.case_id}.json",
                    json.dumps(r.intake, ensure_ascii=False, indent=1),
                )
    return 0 if not run.not_run and all(r.answer is not None for r in run.results) else 1


def main() -> None:
    sys.exit(asyncio.run(amain(sys.argv[1:])))


if __name__ == "__main__":
    main()
