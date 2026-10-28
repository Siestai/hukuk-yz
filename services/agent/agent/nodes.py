"""The six nodes of the graph. Each one is orchestration: it takes what the state holds, calls a
pure module (facts, plan, holding, gate) or a model, asks the knowledge base, and writes the
result back. The legal rules live in those modules, not here."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol, TypedDict

from langgraph.config import get_stream_writer
from langgraph.types import interrupt
from pydantic import BaseModel

from agent import prompts
from agent.facts import apply_answers, build_facts, clarification_for, critical_unknown
from agent.gate import GateDrops, check_draft, not_answered, progressive_in
from agent.holding import verify_rows
from agent.kb import KbClient
from agent.llm import Llm
from agent.llm_schemas import DraftOutput, HoldingDraft, IntakeOutput
from agent.plan import Plan, make_plan
from agent.sources import ReadSource, as_read_source, citation, covers, merge, shown, split_ref
from agent.topics import SourceRef, Topic, get_topic, load_topics
from agent.trace import current_trace
from hukuk_models.chat import (
    CaseFacts,
    CitationRef,
    Clarification,
    ClarificationAnswer,
    FactsEvent,
    HoldingRow,
    StepEvent,
)

# The draft is made once more when it fails the gate (docs/tasks/17-agent-v1.md).
DRAFT_ATTEMPTS = 2
# Hits of a free search that are read.
SEARCH_LIMIT = 5

STEP_LABELS = {
    "intake": "Olay kaydediliyor",
    "clarify": "Eksik bilgiler belirleniyor",
    "plan": "Okunacak kaynaklar belirleniyor",
    "retrieve": "Kaynaklar okunuyor",
    "holding_map": "Hüküm haritası çıkarılıyor",
    "draft": "Cevap hazırlanıyor ve atıflar doğrulanıyor",
}


class State(TypedDict, total=False):
    """The graph state: JSON only, so that the Postgres checkpoint can hold it. `facts` and
    `topic` stay across the turns of a thread; the rest is made anew for every question."""

    question: str
    topic: str
    facts: dict[str, Any]
    clarification: dict[str, Any] | None
    plan: dict[str, Any]
    read: list[dict[str, Any]]
    unread: list[str]
    rows: list[dict[str, Any]]
    answer: dict[str, Any] | None
    gate: dict[str, Any]


class Node(Protocol):
    async def __call__(self, state: State) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Deps:
    llm: Llm
    kb: KbClient
    today: Callable[[], date] = date.today


def _step(node: str) -> None:
    get_stream_writer()(StepEvent(node=node, label=STEP_LABELS[node]).model_dump(mode="json"))


def _facts_event(facts: CaseFacts) -> None:
    get_stream_writer()(FactsEvent(facts=facts).model_dump(mode="json"))


def _dumps(items: list[BaseModel]) -> list[dict[str, Any]]:
    return [i.model_dump(mode="json") for i in items]


async def _read_ref(kb: KbClient, ref: SourceRef, as_of: date) -> ReadSource | None:
    """Reads the source `ref` names, in the version in force on `as_of`, with the other
    paragraphs of the article the search returns with it; None when the knowledge base does not
    have it."""
    # The künye of the article, so that the hit holds its other paragraphs too.
    hits = await kb.search(
        split_ref(ref.ref)[0], categories=[ref.category], as_of=as_of, limit=SEARCH_LIMIT
    )
    return next(
        (s for h in hits if covers(h.ref, ref.ref) and (s := as_read_source(h)) is not None), None
    )


async def _question_sources(
    kb: KbClient, topic: Topic, facts: CaseFacts, as_of: date
) -> dict[str, CitationRef]:
    """The citations behind the "neden soruyorum" of the questions that will be asked."""
    wanted = {
        b.ref: b
        for key in critical_unknown(topic, facts)
        if (tf := topic.fact(key)) and tf.question
        for b in tf.question.basis
    }
    found = {}
    for ref, basis in wanted.items():
        if source := await _read_ref(kb, basis, as_of):
            found[ref] = citation(source, sub=split_ref(ref)[1].removeprefix("/") or None)
    return found


def make_nodes(deps: Deps) -> dict[str, Node]:
    trace = current_trace

    async def intake(state: State) -> dict[str, Any]:
        question = state["question"]
        async with trace().node("intake", {"question_chars": len(question)}) as rec:
            _step("intake")
            topics = load_topics()
            previous = state.get("facts")
            earlier = CaseFacts.model_validate(previous) if previous else None
            out = await deps.llm.run(
                "fast",
                IntakeOutput,
                prompts.INTAKE_INSTRUCTIONS,
                prompts.intake_prompt(question, topics, earlier),
            )
            topic = get_topic(out.topic)
            # Facts of another topic are not this question's facts.
            facts = build_facts(
                topic,
                out,
                earlier if state.get("topic") == topic.id else None,
                question=question,
                today=deps.today(),
            )
            sources = await _question_sources(
                deps.kb, topic, facts, facts.event_date or deps.today()
            )
            clarification = clarification_for(topic, facts, sources)
            _facts_event(facts)
            if clarification:
                # Here, not in `clarify`: that node runs again when the user answers.
                _step("clarify")
            rec.output = {
                "topic": topic.id,
                "unknown_critical": critical_unknown(topic, facts),
                "event_date": facts.event_date,
            }
            return {
                "topic": topic.id,
                "facts": facts.model_dump(mode="json"),
                "clarification": clarification.model_dump(mode="json") if clarification else None,
                "plan": {},
                "read": [],
                "unread": [],
                "rows": [],
                "answer": None,
                "gate": {},
            }

    async def clarify(state: State) -> dict[str, Any]:
        async with trace().node("clarify", {"pending": bool(state.get("clarification"))}) as rec:
            if not state.get("clarification"):
                return {}
            clarification = Clarification.model_validate(state["clarification"])
            # The graph stops here; the checkpoint holds the state until the user answers or skips.
            reply = interrupt(clarification.model_dump(mode="json"))
            if reply["skip"]:
                rec.output = {"skipped": True}
                return {}
            answers = [ClarificationAnswer.model_validate(a) for a in reply["answers"]]
            facts = apply_answers(
                get_topic(state["topic"]),
                clarification,
                answers,
                CaseFacts.model_validate(state["facts"]),
            )
            _facts_event(facts)
            rec.output = {"answered": len(answers)}
            return {"facts": facts.model_dump(mode="json")}

    async def plan(state: State) -> dict[str, Any]:
        async with trace().node("plan", {"topic": state["topic"]}) as rec:
            _step("plan")
            made = make_plan(
                get_topic(state["topic"]),
                state["question"],
                CaseFacts.model_validate(state["facts"]),
                deps.today(),
            )
            rec.output = {"as_of": made.as_of, "must_read": [r.ref for r in made.must_read]}
            return {"plan": made.model_dump(mode="json")}

    async def retrieve(state: State) -> dict[str, Any]:
        made = Plan.model_validate(state["plan"])
        async with trace().node("retrieve", {"as_of": made.as_of}) as rec:
            _step("retrieve")
            read: list[ReadSource] = []
            unread = []
            for ref in made.must_read:
                source = await _read_ref(deps.kb, ref, made.as_of)
                if source is None:
                    unread.append(ref.ref)
                else:
                    read = merge(read, [source])
            for query in made.queries:
                hits = await deps.kb.search(query, as_of=made.as_of, limit=SEARCH_LIMIT)
                read = merge(read, [s for h in hits if (s := as_read_source(h)) is not None])
            read = [shown(s) for s in read]
            rec.output = {"read": [s.ref for s in read], "unread": unread}
            return {"read": _dumps(list(read)), "unread": unread}

    async def holding_map(state: State) -> dict[str, Any]:
        topic = get_topic(state["topic"])
        facts = CaseFacts.model_validate(state["facts"])
        read = [ReadSource.model_validate(s) for s in state["read"]]
        applied_on = Plan.model_validate(state["plan"]).as_of
        async with trace().node("holding_map", {"sources": len(read)}) as rec:
            _step("holding_map")
            rows: list[HoldingRow] = []
            dropped = 0
            if read:
                draft = await deps.llm.run(
                    "fast",
                    HoldingDraft,
                    prompts.HOLDING_INSTRUCTIONS,
                    prompts.holding_prompt(topic, facts, read),
                )
                rows, dropped = verify_rows(draft, read, applied_on)
            rec.output = {"rows": len(rows), "dropped": dropped}
            return {"rows": _dumps(list(rows)), "gate": {"rows_dropped": dropped}}

    async def draft(state: State) -> dict[str, Any]:
        topic = get_topic(state["topic"])
        facts = CaseFacts.model_validate(state["facts"])
        read = [ReadSource.model_validate(s) for s in state["read"]]
        rows = [HoldingRow.model_validate(r) for r in state["rows"]]
        made = Plan.model_validate(state["plan"])
        async with trace().node("draft", {"rows": len(rows), "sources": len(read)}) as rec:
            _step("draft")
            drops = GateDrops(rows=state["gate"].get("rows_dropped", 0))
            issues: list[str] = []
            answer = None
            attempts = 0
            for attempt in range(1, DRAFT_ATTEMPTS + 1):
                attempts = attempt
                if not rows:
                    issues = ["doğrulanan hüküm haritası satırı yoktur"]
                    break
                output = await deps.llm.run(
                    "strong",
                    DraftOutput,
                    prompts.DRAFT_INSTRUCTIONS,
                    prompts.draft_prompt(topic, facts, rows, read, state["unread"], issues),
                )
                if forms := progressive_in(output):
                    output = await deps.llm.run(
                        "strong",
                        DraftOutput,
                        prompts.REWRITE_INSTRUCTIONS,
                        f"Yasak biçimler: {', '.join(forms)}\n\n{output.model_dump_json()}",
                    )
                result = check_draft(
                    output,
                    topic=topic,
                    facts=facts,
                    rows=rows,
                    read=read,
                    applied_on=made.as_of,
                    date_assumed=made.as_of_assumed,
                    unread=state["unread"],
                )
                drops.citations += result.drops.citations
                drops.points += result.drops.points
                issues = result.issues
                if result.answer is not None:
                    answer = result.answer
                    break
            fell_back = answer is None
            if answer is None:
                answer = not_answered(
                    topic=topic,
                    facts=facts,
                    rows=rows,
                    read=read,
                    applied_on=made.as_of,
                    date_assumed=made.as_of_assumed,
                    unread=state["unread"],
                )
            gate = {
                "citations_dropped": drops.citations,
                "points_dropped": drops.points,
                "rows_dropped": drops.rows,
                "attempts": attempts,
                "fallback": fell_back,
                "issues": issues,
            }
            rec.output = gate
            return {"answer": answer.model_dump(mode="json") if answer else None, "gate": gate}

    return {
        "intake": intake,
        "clarify": clarify,
        "plan": plan,
        "retrieve": retrieve,
        "holding_map": holding_map,
        "draft": draft,
    }
