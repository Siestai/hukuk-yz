"""The graph (task 17): SB-001 stops at the clarification and goes on after the answers; skipping
gives a conditional answer; the gate drops what it must; what cannot pass ends in the fallback."""

from datetime import date

import pytest
from agent_fakes import (
    INTAKE_SB016,
    M18_1,
    M18_4,
    FakeKb,
    Script,
    answer_all,
    ask,
    draft,
    hit,
    labour_law_hits,
    only,
    row,
    scripted,
    turn,
    unique_thread,
)
from langgraph.checkpoint.memory import InMemorySaver

from agent.api import Graph, RunRequest
from agent.graph import build_graph
from agent.llm import Llm, Models
from agent.nodes import Deps
from hukuk_models import ErrorCode
from hukuk_models.chat import (
    Answer,
    AnswerEvent,
    ClarificationAnswer,
    ClarificationEvent,
    DoneEvent,
    ErrorEvent,
    FactsEvent,
    StepEvent,
)

TODAY = date(2026, 10, 28)


def make_graph(script: Script, kb: FakeKb | None = None) -> Graph:
    model = scripted(script)
    deps = Deps(llm=Llm(Models(model, model)), kb=kb or FakeKb(), today=lambda: TODAY)
    return build_graph(deps, InMemorySaver())


async def test_sb001_stops_at_the_clarification_and_goes_on_after_the_answers() -> None:
    graph = make_graph(Script())
    thread = unique_thread()

    first = await turn(graph, ask(thread))

    assert [type(e).__name__ for e in first] == [
        "StepEvent",
        "FactsEvent",
        "StepEvent",
        "ClarificationEvent",
        "DoneEvent",
    ]
    clarification = only(first, ClarificationEvent).clarification
    assert [q.fact_key for q in clarification.questions] == [
        "isci_sayisi",
        "sozlesme_turu",
        "bildirim_tarihi",
        "onceki_donem",
        "yer_alti",
    ]
    assert clarification.total == 5
    assert not any(isinstance(e, AnswerEvent) for e in first)
    assert (await graph.aget_state({"configurable": {"thread_id": thread}})).next == ("clarify",)
    # The "neden soruyorum" carries the statute the knowledge base resolved, never a made-up one.
    sources = clarification.questions[0].source_refs
    assert [c.ref for c in sources] == ["4857 m.18/1", "4857 m.18/4"]
    assert all(c.source_id == "statute:4857:m18" for c in sources)
    facts = only(first, FactsEvent).facts
    assert {f.key: f.status for f in facts.facts}["kidem"] == "known"

    second = await turn(graph, answer_all(thread))

    answer = only(second, AnswerEvent).answer
    assert [type(e).__name__ for e in second][:2] == ["FactsEvent", "StepEvent"]
    assert only(second, DoneEvent).trace_id
    assert answer.status == "conditional"
    assert answer.applied_law_date == date(2026, 10, 3)
    assert "03.10.2026" in answer.applied_law_text
    assert {c.ref for p in answer.points for c in p.citations} == {"4857 m.18/1"}
    assert answer.points[0].citations[0].quote == M18_1
    assert answer.points[0].citations[0].char_start == len("(1) ")
    assert {i.ref for i in answer.read_sources.items} >= {"4857 m.17", "4857 m.18"}
    assert answer.read_sources.statute_articles == len(answer.read_sources.items)
    assert answer.holding_map.rows[0].citation.ref == "4857 m.18/1"
    assert {c.fact_key for c in answer.fact_chips} == {"kidem", *ANSWERS_KEYS}


ANSWERS_KEYS = {"isci_sayisi", "sozlesme_turu", "bildirim_tarihi", "onceki_donem", "yer_alti"}


async def test_the_search_uses_the_event_date_of_the_answers() -> None:
    kb = FakeKb()
    graph = make_graph(Script(), kb)
    thread = unique_thread()
    await turn(graph, ask(thread))
    await turn(graph, answer_all(thread))

    assert {c["as_of"] for c in kb.calls[-3:]} == {date(2026, 10, 3)}


async def test_skipping_the_questions_gives_a_conditional_answer() -> None:
    graph = make_graph(Script(drafts=[draft("definite", missing=False), draft()]))
    thread = unique_thread()
    await turn(graph, ask(thread))

    events = await turn(graph, RunRequest(thread_id=thread, skip=True))

    answer = only(events, AnswerEvent).answer
    assert answer.status == "conditional"
    assert answer.missing_info
    assert answer.applied_law_date == TODAY
    assert "Olay tarihi bilinmediğinden" in answer.status_note
    unknown = {c.fact_key for c in answer.fact_chips if c.status == "unknown"}
    assert unknown == ANSWERS_KEYS


async def test_unknown_answers_stay_unknown() -> None:
    graph = make_graph(Script())
    thread = unique_thread()
    await turn(graph, ask(thread))
    request = RunRequest(
        thread_id=thread,
        clarification_answers=[ClarificationAnswer(question_id="q1", unknown=True)],
    )

    answer = only(await turn(graph, request), AnswerEvent).answer

    assert answer.status == "conditional"
    assert {c.fact_key: c.status for c in answer.fact_chips}["isci_sayisi"] == "unknown"


async def test_a_citation_to_a_source_that_was_not_read_drops_at_the_gate() -> None:
    unread = {"source_id": "statute:4857:m99", "sub": "1", "quote": None}
    read = {"source_id": "statute:4857:m18", "sub": "1", "quote": M18_1}
    script = Script(
        drafts=[
            draft(
                points=[
                    {"text": "Okunmamış kaynağa dayanan nokta.", "citations": [unread]},
                    {"text": "Okunan kaynağa dayanan nokta.", "citations": [read, unread]},
                ]
            )
        ]
    )
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, ask(thread))

    answer = only(await turn(graph, answer_all(thread)), AnswerEvent).answer

    assert [p.text for p in answer.points] == ["Okunan kaynağa dayanan nokta."]
    assert [c.source_id for c in answer.points[0].citations] == ["statute:4857:m18"]
    gate = (await graph.aget_state({"configurable": {"thread_id": thread}})).values["gate"]
    assert gate["citations_dropped"] == 2
    assert gate["points_dropped"] == 1
    assert not gate["fallback"]


async def test_a_citation_with_a_quote_that_is_not_in_the_source_drops() -> None:
    fabricated = {"source_id": "statute:4857:m18", "sub": "1", "quote": "Bu cümle kanunda yoktur"}
    script = Script(
        drafts=[
            draft(
                points=[
                    {"text": "Uydurma alıntılı nokta.", "citations": [fabricated]},
                    {
                        "text": "Doğru alıntılı nokta.",
                        "citations": [{"source_id": "statute:4857:m18", "quote": M18_4}],
                    },
                ]
            )
        ]
    )
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, ask(thread))

    answer = only(await turn(graph, answer_all(thread)), AnswerEvent).answer

    assert [p.text for p in answer.points] == ["Doğru alıntılı nokta."]
    assert answer.points[0].citations[0].char_start is not None


async def test_a_holding_map_row_with_a_fabricated_quote_drops() -> None:
    script = Script(
        holding={
            "rows": [
                row("statute:4857:m18", "Kanunda hiç yazmayan bir ifade burada"),
                row("statute:4857:m18", M18_4, sub="4"),
                row("statute:4857:m99", M18_4),
            ]
        }
    )
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, ask(thread))

    answer = only(await turn(graph, answer_all(thread)), AnswerEvent).answer

    assert [r.citation.ref for r in answer.holding_map.rows] == ["4857 m.18/4"]
    assert answer.holding_map.rows[0].condition_quote == M18_4
    gate = (await graph.aget_state({"configurable": {"thread_id": thread}})).values["gate"]
    assert gate["rows_dropped"] == 2


async def test_a_progressive_form_is_corrected_once() -> None:
    bad = draft(headline="İşe iade davası açılamıyor.")
    script = Script(drafts=[bad], rewrite=draft())
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, ask(thread))

    answer = only(await turn(graph, answer_all(thread)), AnswerEvent).answer

    assert answer.headline == "İşe iade davası açılamamaktadır."
    assert len(script.of("draft")) == 1
    assert len(script.of("rewrite")) == 1
    assert "açılamıyor" in script.of("rewrite")[0]


async def test_definite_is_refused_while_a_critical_fact_is_unknown() -> None:
    script = Script(drafts=[draft("definite", missing=False), draft()])
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, ask(thread))

    answer = only(await turn(graph, answer_all(thread, q1=None)), AnswerEvent).answer

    assert answer.status == "conditional"
    assert len(script.of("draft")) == 2
    # The second try is told why the first did not pass.
    assert "kritik olgu bilinmezken kesin cevap verilemez: isci_sayisi" in script.of("draft")[1]


async def test_a_draft_that_cannot_pass_twice_ends_in_the_not_answered_answer() -> None:
    script = Script(drafts=[draft("definite", missing=False)])
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, ask(thread))

    answer = only(await turn(graph, answer_all(thread, q1=None)), AnswerEvent).answer

    assert answer.headline == "Doğrulanmış kaynakla cevap verilemedi."
    assert answer.status == "conditional"
    assert answer.holding_map.rows
    assert Answer.model_validate(answer.model_dump()) == answer
    gate = (await graph.aget_state({"configurable": {"thread_id": thread}})).values["gate"]
    assert gate["fallback"] and gate["attempts"] == 2


async def test_no_verified_row_ends_in_an_error() -> None:
    script = Script(holding={"rows": [row("statute:4857:m18", "Kanunda hiç yazmayan ifade")]})
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, ask(thread))

    events = await turn(graph, answer_all(thread))

    error = only(events, ErrorEvent)
    assert error.code == ErrorCode.answer_not_verified
    assert not any(isinstance(e, AnswerEvent) for e in events)
    assert script.of("draft") == []


async def test_a_topic_with_all_facts_known_does_not_stop() -> None:
    script = Script(
        intake={
            **INTAKE_SB016,
            "facts": [
                *INTAKE_SB016["facts"],
                {"key": "ceza_turu", "value": "bildirge", "status": "known"},
                {"key": "kendiliginden", "value": "Kendiliğinden verildi", "status": "known"},
            ],
        },
        holding={"rows": [row("statute:5510:m102", "tebliğ tarihinden itibaren onbeş gün içinde")]},
        drafts=[
            draft(
                "definite",
                missing=False,
                points=[
                    {
                        "text": "Peşin ödeme indirimi uygulanmaktadır.",
                        "citations": [{"source_id": "statute:5510:m102", "sub": "5"}],
                    }
                ],
            )
        ],
    )
    circular = hit(
        "admin:2020-8", "2020/8", "SGK Genelgesi 2020/8", "Genelge metni", category="admin_act"
    )
    graph = make_graph(script, FakeKb([*labour_law_hits(), circular]))

    events = await turn(graph, ask(unique_thread()))

    assert not any(isinstance(e, ClarificationEvent) for e in events)
    assert only(events, AnswerEvent).answer.status == "definite"
    assert [e.node for e in events if isinstance(e, StepEvent)] == [
        "intake",
        "plan",
        "retrieve",
        "holding_map",
        "draft",
    ]


async def test_a_new_question_in_a_thread_keeps_the_facts_of_the_same_topic() -> None:
    graph = make_graph(Script())
    thread = unique_thread()
    await turn(graph, ask(thread))
    await turn(graph, answer_all(thread))

    again = await turn(graph, ask(thread))

    assert not any(isinstance(e, ClarificationEvent) for e in again)
    facts = only(again, FactsEvent).facts
    assert {f.key: f.status for f in facts.facts}["isci_sayisi"] == "known"
    assert only(again, AnswerEvent).answer.applied_law_date == date(2026, 10, 3)


async def test_unread_sources_are_named_to_the_draft() -> None:
    script = Script()
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, ask(thread))
    await turn(graph, answer_all(thread))

    assert "9. HD E.2016/28920 K.2017/17860" in script.of("draft")[0]
    assert "Okunamayan kaynaklar" in script.of("draft")[0]


async def test_the_models_are_called_in_the_order_of_the_graph() -> None:
    script = Script()
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, ask(thread))
    await turn(graph, answer_all(thread))

    assert [k for k, _ in script.calls] == ["intake", "holding", "draft"]


async def test_truncated_required_text_constrains_the_answer_and_cannot_support_a_quote() -> None:
    from agent.sources import MAX_SOURCE_CHARS

    kb = FakeKb(
        [
            hit(
                "statute:4857:m18",
                "4857 m.18",
                "4857 sayılı İş Kanunu m.18",
                f"(1) {M18_1}",
                "x" * MAX_SOURCE_CHARS,
                f"(4) {M18_4}",
            ),
        ]
    )
    script = Script(
        holding={"rows": [row("statute:4857:m18", M18_1), row("statute:4857:m18", M18_4)]}
    )
    graph = make_graph(script, kb)
    thread = unique_thread()
    await turn(graph, ask(thread))
    events = await turn(graph, answer_all(thread))
    answer = only(events, AnswerEvent).answer
    state = (await graph.aget_state({"configurable": {"thread_id": thread}})).values
    assert "4857 m.18" in state["unread"]
    assert answer.status == "conditional"
    assert "4857 m.18" in answer.status_note
    assert len(answer.holding_map.rows) == 1
    assert state["gate"]["rows_dropped"] == 1
    assert M18_4 not in script.of("holding")[0]


async def test_question_text_is_not_in_structured_logs(caplog) -> None:  # type: ignore[no-untyped-def]
    import logging

    from agent.logging_setup import JsonFormatter

    caplog.set_level(logging.INFO)
    graph = make_graph(Script())
    question = "PRIVATE_QUESTION_SENTINEL 5 ay kıdem"
    await turn(graph, RunRequest(thread_id=unique_thread(), text=question))
    records = [r for r in caplog.records if r.name.startswith("agent")]
    assert records
    serialized = "\n".join(JsonFormatter().format(r) for r in records)
    assert question not in serialized
    assert "PRIVATE_QUESTION_SENTINEL" not in serialized
    assert '"question_chars"' in serialized


async def test_an_expired_required_source_is_unread_even_if_kb_returns_it(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from agent.nodes import _read_ref
    from agent.topics import SourceRef

    kb = FakeKb()
    expired = hit(
        "statute:4857:m18", "4857 m.18", "4857 sayılı İş Kanunu m.18", M18_1, valid_to=TODAY
    )

    async def stale_search(*args, **kwargs):  # type: ignore[no-untyped-def]
        return [expired]

    monkeypatch.setattr(kb, "search", stale_search)
    assert await _read_ref(kb, SourceRef(ref="4857 m.18", category="statute"), TODAY) is None


@pytest.mark.parametrize("location", ["draft", "title"])
async def test_gate_feedback_stays_internal_and_logs_only_safe_issue_counts(
    caplog: pytest.LogCaptureFixture, location: str
) -> None:
    import logging

    from agent.logging_setup import JsonFormatter

    sentinel = "PRIVATE_12345678901_calisiyor"
    caplog.set_level(logging.INFO)
    script = Script(drafts=[draft(headline=sentinel)] if location == "draft" else [draft()])
    if location == "title":
        script.intake = {**script.intake, "title": sentinel}
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, RunRequest(thread_id=thread, text=f"Bildirim hakkında {sentinel}"))
    events = await turn(graph, RunRequest(thread_id=thread, skip=True))
    assert only(events, AnswerEvent).answer.headline == "Doğrulanmış kaynakla cevap verilemedi."
    assert sentinel in script.of("draft")[1]
    if location == "draft":
        assert sentinel in script.of("rewrite")[0]
    logs = "\n".join(JsonFormatter().format(r) for r in caplog.records)
    assert sentinel not in logs
    records = [
        r for r in caplog.records if r.name == "agent.trace" and r.getMessage() == "node draft"
    ]
    assert len(records) == 1
    output = records[0].fields["output"]  # type: ignore[attr-defined]
    assert "issues" not in output
    assert output["issue_counts"] == {"progressive_form": 1}
    assert output["fallback"] and output["attempts"] == 2


async def test_holding_rejection_logs_counts_and_keeps_private_text_out(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    from agent.logging_setup import JsonFormatter

    sentinel = "PRIVATE_12345678901_calisiyor"
    informal = row("statute:4857:m18", M18_1)
    informal["condition"] = sentinel
    script = Script(holding={"rows": [informal, row("statute:4857:m18", M18_4)]})
    caplog.set_level(logging.INFO)
    graph = make_graph(script)
    thread = unique_thread()
    await turn(graph, ask(thread))
    events = await turn(graph, RunRequest(thread_id=thread, skip=True))
    answer = only(events, AnswerEvent).answer
    assert answer.headline == "İşe iade davası açılamamaktadır."
    assert len(answer.holding_map.rows) == 1
    assert sentinel not in "\n".join(JsonFormatter().format(r) for r in caplog.records)
    records = [r for r in caplog.records if r.name == "agent.trace"]
    outputs = {r.getMessage(): r.fields["output"] for r in records}  # type: ignore[attr-defined]
    assert outputs["node holding_map"] == {"rows": 1, "dropped": 1}
    assert outputs["node draft"]["issue_counts"] == {}
    assert outputs["node draft"]["rows_dropped"] == 1
    assert outputs["node draft"]["fallback"] is False
