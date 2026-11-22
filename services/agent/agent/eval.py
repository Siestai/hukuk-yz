"""The eval runner: `python -m agent.eval eval/cases`.

Runs the agent on every case of the eval set (`eval/cases/*.yaml`), answers its clarification
questions with the facts the case gives (a question the case has no fact for is answered
"Bilmiyorum"), scores the answer with `eval/score.py` and prints the acceptance table (one row per
case, the total, PASS or FAIL against the thresholds of task 19). The result goes to
`eval/results/<date>-<tag>.json` and the table next to it as `.md`.

Budget: `--estimate` prints the expected cost and calls no model; `--budget-usd` is a hard cap,
checked after every model call and before every case. Real models and a real or fixture knowledge
base are chosen on the command line; the CI smoke test runs the same code with fake models. The
exit code is 1 when the run is below the thresholds.
"""

import argparse
import asyncio
import importlib.util
import json
import math
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from pydantic_ai import capture_run_messages
from pydantic_ai.messages import ModelResponse

from agent import llm as llm_module
from agent.api import Graph, RunRequest, turn_events
from agent.graph import build_graph
from agent.kb import HttpKbClient, KbClient, KbHit, KbMatch, Unreadable
from agent.llm import Llm, Models, Tier, _model_name
from agent.llm_schemas import IntakeOutput
from agent.nodes import Deps
from agent.settings import KbSettings, LlmSettings
from agent.sources import covers, split_ref
from agent.trace import NodeRecord, Trace, Tracing, current_record
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
# The turns of a case at most: the question, the clarification, one follow-up clarification
# (an answer that opens a branch asks its facts once, task 19 B2), the answer.
MAX_TURNS = 3
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
    when it fits in what is left. It is charged after every model call; a call is one
    `Llm.run`, with the schema retries Pydantic AI makes inside it, so the cap can be passed by
    at most one such call."""

    cap: float
    per_case: float
    spent: float = 0.0

    @property
    def exceeded(self) -> bool:
        return self.spent > self.cap

    def charge(self, cost: float | None) -> None:
        """A call whose price is unknown cannot be held under the cap: it stops the run."""
        self.spent = self.spent + cost if cost is not None else math.inf
        if self.exceeded:
            raise BudgetExceeded

    def allows_next(self) -> bool:
        return self.spent + self.per_case <= self.cap


class EvalLlm(Llm):
    """The models of an eval run: after every call the spend is charged to the budget, and the
    output of the intake is kept for the case in progress (`--record-intake`). A call that fails
    (the schema retries spent, a provider error) is counted too: its tokens and cost go to the
    trace and the budget before the error goes on."""

    def __init__(self, models: Models, budget: Budget | None = None) -> None:
        super().__init__(models)
        self.budget = budget
        self.intake: dict[str, Any] | None = None

    async def run[T](self, tier: Tier, output_type: type[T], instructions: str, prompt: str) -> T:
        record = current_record()
        before = (record.input_tokens, record.output_tokens, record.cost) if record else None
        with capture_run_messages() as messages:
            try:
                output = await super().run(tier, output_type, instructions, prompt)
            except Exception:
                if record is not None:
                    model = self._models.fast if tier == "fast" else self._models.strong
                    used = [m.usage for m in messages if isinstance(m, ModelResponse)]
                    i, o = sum(u.input_tokens for u in used), sum(u.output_tokens for u in used)
                    record.add_usage(_model_name(model), i, o, llm_module._cost(model, i, o))
                self._charge(record, before)
                raise
        if isinstance(output, IntakeOutput):
            self.intake = output.model_dump(mode="json", exclude_unset=True)
        self._charge(record, before)
        return output

    def _charge(
        self, record: NodeRecord | None, before: tuple[int, int, float | None] | None
    ) -> None:
        if self.budget is None or record is None or before is None:
            return
        tokens = record.input_tokens + record.output_tokens - before[0] - before[1]
        if not tokens:
            return
        priced = record.cost is not None and record.cost != before[2]
        self.budget.charge((record.cost or 0.0) - (before[2] or 0.0) if priced else None)


@dataclass(frozen=True)
class Estimate:
    per_case: float | None
    source: str
    # What every earlier result file spent: the cap of the package is for all rounds.
    earlier_spent: float = 0.0


def _model_names(models: Models) -> dict[str, str]:
    return {"fast": _model_name(models.fast), "strong": _model_name(models.strong)}


def _earlier_costs(results_dir: Path, models: Models) -> tuple[list[float], int, float]:
    """The real cost of every answered case of the earlier runs of the same models, the number
    of result files, and what all of them spent."""
    costs: list[float] = []
    spent = 0.0
    paths = sorted(results_dir.glob("*.json"))
    for path in paths:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        cases = loaded if isinstance(loaded, list) else loaded.get("cases", [])
        cases = [c for c in cases if isinstance(c, dict)]
        spent += sum(c.get("cost") or 0.0 for c in cases)
        if isinstance(loaded, dict) and loaded.get("models") == _model_names(models):
            costs += [
                c["cost"]
                for c in cases
                if c.get("cost") is not None
                and c.get("answer") is not None
                and c.get("error") is None
            ]
    return costs, len(paths), spent


def estimate(results_dir: Path, models: Models) -> Estimate:
    """The cost of one case: the mean real cost of the answered cases of the earlier runs of the
    same models in `results_dir`, otherwise `ASSUMED_TOKENS` at the price of the models
    (genai-prices, as the trace)."""
    costs, files, spent = _earlier_costs(results_dir, models)
    if costs:
        mean = sum(costs) / len(costs)
        return Estimate(mean, f"önceki koşular: {len(costs)} vaka, {files} sonuç dosyası", spent)
    total = 0.0
    for model, tokens in (
        (models.fast, ASSUMED_TOKENS["fast"]),
        (models.strong, ASSUMED_TOKENS["strong"]),
    ):
        price = llm_module._cost(model, *tokens)
        if price is None:
            return Estimate(None, f"fiyat tablosunda yok: {_model_name(model)}", spent)
        total += price
    assumed = ", ".join(f"{t} {i}/{o}" for t, (i, o) in ASSUMED_TOKENS.items())
    source = f"varsayım: vaka başına token (gir/çık) {assumed}, genai-prices fiyatı"
    return Estimate(total, source, spent)


def unpriced(models: Models) -> list[str]:
    """The models genai-prices has no price for: a budget cannot be held with them."""
    return [
        _model_name(m) for m in (models.fast, models.strong) if llm_module._cost(m, 1, 1) is None
    ]


@dataclass
class CaseResult:
    """One case of a run; the keys of a row of `eval/score.py` `render_table`."""

    case_id: str
    trace_id: str
    expected_topic: str | None
    topic: str | None
    # The intake output: the fields the model set, after the schema check of Pydantic AI.
    intake: dict[str, Any] | None
    # The fact keys asked in all clarification rounds, and the number of the rounds.
    asked: list[str]
    rounds: int
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
    """The cases, checked by `eval/score.py` `load_case` before any model is called."""
    score = load_score_module(cases_dir)
    cases = [score.load_case(p) for p in sorted(cases_dir.glob("*.yaml"))]
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


async def _play(
    graph: Graph, trace: Trace, thread_id: str, case: dict[str, Any]
) -> tuple[list[Clarification], Answer | None, str | None]:
    """The turns of a case: the question, then the answers to each clarification round. The
    rounds' questions are returned together."""
    rounds: list[Clarification] = []
    answer: Answer | None = None
    error = None
    request = RunRequest(thread_id=thread_id, text=case["question"])
    for _ in range(MAX_TURNS):
        pending: Clarification | None = None
        async for event in turn_events(graph, request, trace):
            if isinstance(event, ClarificationEvent):
                pending = event.clarification
                rounds.append(pending)
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
    return rounds, answer, error


def _failed(case: dict[str, Any], trace: Trace, llm: EvalLlm, error: str) -> CaseResult:
    """A case the runner itself failed on: what it spent, nothing scored."""
    expected = case["expected"]
    return CaseResult(
        case_id=case["id"],
        trace_id=trace.trace_id,
        expected_topic=expected.get("topic"),
        topic=None,
        intake=llm.intake,
        asked=[],
        rounds=0,
        answer=None,
        metrics={},
        score=0.0,
        must_ask=None,
        must_cite=None,
        missing_in_kb=list(expected.get("missing_in_kb", [])),
        must_not=[],
        headline=None,
        mode=[],
        unread=[],
        drops=dict.fromkeys(DROP_KEYS, 0),
        issue_counts={},
        fallback=False,
        substantive=False,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        cost=trace.cost,
        seconds=trace.seconds,
        error=error,
    )


async def run_case(
    graph: Graph, llm: EvalLlm, tracing: Tracing, score: ModuleType, case: dict[str, Any]
) -> CaseResult:
    """One case. An exception of the runner (scoring, reading the state) is the case's error,
    not the end of the run."""
    thread_id = f"eval-{case['id']}-{uuid.uuid4().hex[:8]}"
    llm.intake = None
    with tracing.run(thread_id) as trace:
        try:
            rounds, answer, error = await _play(graph, trace, thread_id, case)
            if llm.budget is not None and llm.budget.exceeded:
                error = "budget_exceeded"
            state = (await graph.aget_state({"configurable": {"thread_id": thread_id}})).values
            return _scored(case, trace, llm, score, state, rounds, answer, error)
        except Exception as exc:
            if llm.budget is not None and llm.budget.exceeded:
                return _failed(case, trace, llm, "budget_exceeded")
            return _failed(case, trace, llm, f"eval_error: {type(exc).__name__}")


def _scored(
    case: dict[str, Any],
    trace: Trace,
    llm: EvalLlm,
    score: ModuleType,
    state: dict[str, Any],
    rounds: list[Clarification],
    answer: Answer | None,
    error: str | None,
) -> CaseResult:
    # A case that stopped before the draft (an error, an unanswered clarification) has no gate.
    gate = state.get("gate") or {}
    raw = answer.model_dump(mode="json") if answer else None
    # What the run asked in all rounds: nothing when there was no clarification.
    asked = {"questions": [q.model_dump(mode="json") for c in rounds for q in c.questions]}
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
        rounds=len(rounds),
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
    *,
    run: EvalRun | None = None,
    after_case: Callable[[EvalRun], object] | None = None,
) -> EvalRun:
    """The cases in order; with a budget, a case starts only when its estimate fits in what is
    left, and the run stops at the first case the cap stopped. The results go into `run` (a
    caller that keeps it has them if the run is cut); `after_case` sees it after every case."""
    score = load_score_module(cases_dir)
    run = run if run is not None else EvalRun()
    cases = load_cases(cases_dir, only)
    for i, case in enumerate(cases):
        budget = llm.budget
        if budget is not None and (budget.exceeded or not budget.allows_next()):
            run.not_run = [c["id"] for c in cases[i:]]
            break
        run.results.append(await run_case(graph, llm, tracing, score, case))
        if after_case is not None:
            after_case(run)
    return run


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


async def amain(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m agent.eval",
        description=__doc__.split("\n")[0],
        epilog="exit: 0 PASS with every case answered; 1 FAIL, an unanswered case or a case the "
        "budget stopped; 2 a budget with a model genai-prices has no price for",
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
    print(f"önceki sonuç dosyalarının harcaması: ${made.earlier_spent:.2f}")
    if args.estimate:
        return 0
    budget = None
    if args.budget_usd is not None:
        if missing := unpriced(names):
            print(f"bütçe tutulamaz, fiyat tablosunda yok: {', '.join(missing)}", file=sys.stderr)
            return 2
        assert made.per_case is not None  # the models are priced
        budget = Budget(cap=args.budget_usd, per_case=made.per_case)

    score = load_score_module(args.cases)
    base = results_dir / f"{date.today().isoformat()}-{args.tag}"

    def save(run: EvalRun) -> tuple[bool, str]:
        """The result and its table, written after every case and at the end."""
        rows = [vars(r) for r in run.results]
        passed, reasons = score.acceptance(rows, run.not_run)
        table = score.render_table(rows, passed, reasons)
        result = {
            "tag": args.tag,
            "date": date.today().isoformat(),
            "models": _model_names(names),
            "kb": args.kb,
            "estimate": {"per_case_usd": made.per_case, "source": made.source},
            "budget_usd": args.budget_usd,
            "spent_usd": sum(r.cost or 0.0 for r in run.results),
            "earlier_spent_usd": made.earlier_spent,
            "passed": passed,
            "reasons": reasons,
            "not_run": run.not_run,
            "cases": rows,
        }
        _write(
            base.with_suffix(".json"),
            json.dumps(result, ensure_ascii=False, indent=1, default=str),
        )
        _write(base.with_suffix(".md"), f"# Eval {args.tag} ({result['date']})\n\n{table}\n")
        if args.record_intake:
            for r in run.results:
                if r.intake is not None:
                    _write(
                        args.record_intake / f"{r.case_id}.json",
                        json.dumps(r.intake, ensure_ascii=False, indent=1),
                    )
        return passed, table

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
    run = EvalRun()
    try:
        await run_eval(graph, llm, tracing, args.cases, args.case, run=run, after_case=save)
    finally:
        if isinstance(kb, HttpKbClient):
            await kb.aclose()
        tracing.shutdown()
        # Whatever ran is kept, also when the run was cut.
        passed, table = save(run)
    print(table)
    spent = sum(r.cost or 0.0 for r in run.results)
    cap = f" / tavan ${budget.cap:.2f}" if budget else ""
    print(f"harcanan: ${spent:.4f}{cap}; önceki sonuç dosyaları: ${made.earlier_spent:.2f}")
    answered = all(r.answer is not None for r in run.results)
    return 0 if passed and answered and not run.not_run else 1


def main() -> None:
    sys.exit(asyncio.run(amain(sys.argv[1:])))


if __name__ == "__main__":
    main()
