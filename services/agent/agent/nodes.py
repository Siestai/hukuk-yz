"""The six nodes of the graph. Each one is orchestration: it takes what the state holds, calls a
pure module (facts, plan, holding, gate) or a model, asks the knowledge base, and writes the
result back. The legal rules live in those modules, not here."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol, TypedDict

from langgraph.config import get_stream_writer
from langgraph.types import interrupt
from pydantic import BaseModel
from pydantic_ai.exceptions import UnexpectedModelBehavior

from agent import prompts
from agent.facts import apply_answers, build_facts, clarification_for, critical_unknown
from agent.gate import (
    SCHEMA_FAILED,
    GateCited,
    GateDrops,
    check_draft,
    cited_by_status,
    draft_texts,
    holding_issue,
    not_answered,
    progressive_in,
    progressive_sentences,
)
from agent.holding import invented_keys, key_feedback, verify_rows
from agent.insufficient import source_gap
from agent.kb import KbClient, Unreadable
from agent.kunye import admin_act_section, mapped
from agent.llm import Llm
from agent.llm_schemas import HoldingDraft, IntakeOutput, draft_output_type
from agent.plan import Plan, make_plan
from agent.sources import (
    ReadSource,
    as_read_source,
    citation,
    covers,
    merge,
    shown,
    split_ref,
    valid_on,
)
from agent.topics import SourceRef, Topic, get_topic, load_topics
from agent.trace import current_trace
from hukuk_models.chat import (
    CaseFacts,
    CitationRef,
    Clarification,
    ClarificationAnswer,
    FactsEvent,
    HoldingRow,
    MissingReason,
    StepEvent,
)

# The draft is made once more when it fails the gate (docs/tasks/17-agent-v1.md); the last one
# loses its "-iyor" sentences instead (task 19). A holding map whose rows depend on keys the
# template does not have is made once more too; then those rows drop.
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

    delivery: dict[str, Any]
    question: str
    topic: str
    facts: dict[str, Any]
    clarification: dict[str, Any] | None
    plan: dict[str, Any]
    read: list[dict[str, Any]]
    unread: list[str]
    missing: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    answer: dict[str, Any] | None
    # The "kaynak yetersiz" content of a fallback (`SourceGap`); None otherwise.
    source_gap: dict[str, Any] | None
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


class Missing(TypedDict):
    """A source that was to be read and was not, for the trace and the source gap."""

    ref: str
    reason: MissingReason


def _missing(ref: str, reason: MissingReason) -> Missing:
    return {"ref": ref, "reason": reason}


async def _read_sections(
    kb: KbClient, ref: str, as_of: date, queries: Sequence[str]
) -> tuple[list[ReadSource], list[Missing]]:
    """The genelge sections `ref` names, each read whole. A künye of the whole act ("2020/8")
    names the sections of it that the search finds for `queries`; every one of them that is not
    read is missing with its own reason, and the act itself when none is read."""
    found = admin_act_section(ref)
    whole_act = found is not None and found.section is None
    wanted = [] if found is None or whole_act else [ref]
    if found is not None and whole_act:
        for query in queries:
            hits = await kb.search(query, categories=["admin_act"], as_of=as_of, limit=SEARCH_LIMIT)
            wanted += [h.ref for h in hits if covers(h.ref, found.act) and h.ref not in wanted]
    sources = []
    missing = []
    for section in wanted:
        read = await kb.read_section(section, as_of)
        if isinstance(read, Unreadable):
            missing.append(_missing(section, read.reason))
        elif (source := as_read_source(read)) is None:
            missing.append(_missing(section, "not_found"))
        elif not valid_on(source, as_of):
            missing.append(_missing(section, "not_in_force"))
        else:
            sources.append(source)
    if whole_act and not sources:
        missing.insert(0, _missing(ref, "not_found"))
    return sources, missing


async def _read_ref(
    kb: KbClient, ref: SourceRef, as_of: date, queries: Sequence[str] = ()
) -> tuple[list[ReadSource], list[Missing]]:
    """Reads the source `ref` names, in the version in force on `as_of`: the whole article or
    genelge section, or the passages of a decision the search returns. The second value names
    what was not read and why; with no source read, `ref` itself is among them."""
    if not mapped(ref):
        return [], [_missing(ref.ref, "unmapped")]
    if ref.category == "admin_act":
        return await _read_sections(kb, ref.ref, as_of, queries)
    # The künye of the article, so that the hit holds its other paragraphs too.
    if ref.category == "statute":
        hits = await kb.read_article(split_ref(ref.ref)[0], as_of)
    else:
        hits = await kb.search(ref.ref, categories=[ref.category], as_of=as_of, limit=SEARCH_LIMIT)
    source = next(
        (
            s
            for h in hits
            if covers(h.ref, ref.ref)
            and (s := as_read_source(h)) is not None
            and valid_on(s, as_of)
        ),
        None,
    )
    return ([source], []) if source is not None else ([], [_missing(ref.ref, "not_found")])


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
        sources, _ = await _read_ref(kb, basis, as_of)
        if sources:
            found[ref] = citation(sources[0], sub=split_ref(ref)[1].removeprefix("/") or None)
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
                "missing": [],
                "rows": [],
                "answer": None,
                "source_gap": None,
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
                today=deps.today(),
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
            missing: list[Missing] = []
            for ref in made.must_read:
                sources, not_read = await _read_ref(deps.kb, ref, made.as_of, made.queries)
                if not sources:
                    unread.append(ref.ref)
                missing += [m for m in not_read if m not in missing]
                read = merge(read, sources)
            for query in made.queries:
                hits = await deps.kb.search(query, as_of=made.as_of, limit=SEARCH_LIMIT)
                read = merge(read, [s for h in hits if (s := as_read_source(h)) is not None])
            truncated = {s.source_id for s in read if shown(s).passages != s.passages}
            read = [shown(s) for s in read]
            for ref in made.must_read:
                if ref.ref not in unread and any(
                    covers(s.ref, ref.ref) and s.source_id in truncated for s in read
                ):
                    unread.append(ref.ref)
                    missing.append(_missing(ref.ref, "truncated"))
            rec.output = {
                "read": [s.ref for s in read],
                "unreviewed": [
                    {"ref": s.ref, "band": s.band} for s in read if s.review_status == "analyzed"
                ],
                "missing_source": missing,
            }
            return {"read": _dumps(list(read)), "unread": unread, "missing": list(missing)}

    async def holding_map(state: State) -> dict[str, Any]:
        topic = get_topic(state["topic"])
        facts = CaseFacts.model_validate(state["facts"])
        read = [ReadSource.model_validate(s) for s in state["read"]]
        applied_on = Plan.model_validate(state["plan"]).as_of
        async with trace().node("holding_map", {"sources": len(read)}) as rec:
            _step("holding_map")
            rows: list[HoldingRow] = []
            dropped = 0
            invented: list[str] = []
            if read:

                async def made(feedback: list[str]) -> HoldingDraft:
                    return await deps.llm.run(
                        "fast",
                        HoldingDraft,
                        prompts.HOLDING_INSTRUCTIONS,
                        prompts.holding_prompt(
                            topic, facts, read, question=state["question"], feedback=feedback
                        ),
                    )

                draft = await made([])
                # Corrected once; the rows that still depend on such a key drop below.
                if invented := invented_keys(draft, facts):
                    draft = await made([key_feedback(invented, facts)])
                rows, dropped = verify_rows(draft, read, applied_on, facts=facts)
            rec.output = {"rows": len(rows), "dropped": dropped, "key_corrected": bool(invented)}
            return {"rows": _dumps(list(rows)), "gate": {"rows_dropped": dropped}}

    async def draft(state: State) -> dict[str, Any]:
        topic = get_topic(state["topic"])
        facts = CaseFacts.model_validate(state["facts"])
        read = [ReadSource.model_validate(s) for s in state["read"]]
        rows = [HoldingRow.model_validate(r) for r in state["rows"]]
        made = Plan.model_validate(state["plan"])
        output_type = draft_output_type(topic, facts)
        async with trace().node("draft", {"rows": len(rows), "sources": len(read)}) as rec:
            _step("draft")
            drops = GateDrops(rows=state["gate"].get("rows_dropped", 0))
            issues: list[str] = []
            issue_counts: dict[str, int] = {}
            answer = None
            attempts = 0
            blocked = holding_issue(rows)
            if blocked:
                code, feedback = blocked
                issues = [feedback]
                issue_counts = {code: 1}
            for attempt in range(1, 1 if blocked else DRAFT_ATTEMPTS + 1):
                attempts = attempt
                try:
                    output = await deps.llm.run(
                        "strong",
                        output_type,
                        prompts.DRAFT_INSTRUCTIONS,
                        prompts.draft_prompt(
                            topic,
                            facts,
                            rows,
                            read,
                            state["unread"],
                            issues,
                            question=state["question"],
                        ),
                    )
                    if forms := progressive_in(output):
                        output = await deps.llm.run(
                            "strong",
                            draft_output_type(topic, facts, original=output),
                            prompts.REWRITE_INSTRUCTIONS,
                            prompts.rewrite_prompt(
                                output.model_dump_json(),
                                forms,
                                progressive_sentences(draft_texts(output)),
                                question=state["question"],
                            ),
                        )
                except UnexpectedModelBehavior:
                    # The typed retries are spent: the honest fallback, not an error turn.
                    issues, issue_counts = [SCHEMA_FAILED], {"draft_schema": 1}
                    break
                result = check_draft(
                    output,
                    topic=topic,
                    facts=facts,
                    rows=rows,
                    read=read,
                    applied_on=made.as_of,
                    date_assumed=made.as_of_assumed,
                    unread=state["unread"],
                    final=attempt == DRAFT_ATTEMPTS,
                )
                drops.citations += result.drops.citations
                drops.points += result.drops.points
                drops.sentences += result.drops.sentences
                drops.branches += result.drops.branches
                issues = result.issues
                issue_counts = result.issue_counts
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
            gap = source_gap(topic, facts, state.get("missing", [])) if fell_back else None
            if answer is not None and gap is not None:
                answer = answer.model_copy(update={"source_gap": gap})
            cited = cited_by_status(answer) if answer else GateCited()
            gate = {
                "citations_dropped": drops.citations,
                "points_dropped": drops.points,
                "rows_dropped": drops.rows,
                "sentences_dropped": drops.sentences,
                "branches_dropped": drops.branches,
                "cited_approved": cited.approved,
                "cited_unreviewed": cited.unreviewed,
                "attempts": attempts,
                "fallback": fell_back,
                "issues": issues,
            }
            rec.output = {k: v for k, v in gate.items() if k != "issues"}
            rec.output["issue_counts"] = issue_counts
            return {
                "answer": answer.model_dump(mode="json") if answer else None,
                "source_gap": gap.model_dump(mode="json") if gap else None,
                "gate": gate,
            }

    return {
        "intake": intake,
        "clarify": clarify,
        "plan": plan,
        "retrieve": retrieve,
        "holding_map": holding_map,
        "draft": draft,
    }
