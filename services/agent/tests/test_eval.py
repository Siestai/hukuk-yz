"""The eval runner: the fixture knowledge base, the answers to the questions, and the smoke run
with fake models that CI runs."""

import json
from datetime import date
from pathlib import Path

import pytest
from agent_fakes import INTAKE_SB016, FailingKb, Script, draft, row, scripted

from agent.eval import (
    FixtureKb,
    amain,
    answers_for,
    build_eval_graph,
    render,
    run_eval,
)
from agent.kb import KbUnavailable
from agent.llm import Models
from agent.trace import Tracing
from hukuk_models.chat import Clarification, ClarificationQuestion, QuestionInput

ROOT = Path(__file__).parents[3]
CASES = ROOT / "eval" / "cases"


async def test_the_fixture_knowledge_base_holds_the_sources_the_fixtures_quote() -> None:
    kb = FixtureKb()

    hits = await kb.search("4857 m.18", categories=["statute"], as_of=date(2026, 10, 3))

    assert hits[0].source_id == "statute:4857:m18"
    assert any("Yer altı işlerinde" in (m.text or "") for m in hits[0].matches)
    assert hits[0].ref == "4857 m.18"
    assert hits[0].title == "4857 sayılı İş Kanunu m.18"
    # A source the fixtures cite without a quote has no text to read.
    assert await kb.search("9. HD E.2016/28920 K.2017/17860") == []


def question(i: int, key: str) -> ClarificationQuestion:
    return ClarificationQuestion(
        id=f"q{i}", fact_key=key, text="?", why="!", input=QuestionInput(kind="text")
    )


def test_the_case_answers_the_questions_it_has_facts_for_and_says_unknown_to_the_rest() -> None:
    clarification = Clarification(
        questions=[question(1, "ceza_turu"), question(2, "kendiliginden")], index=1, total=2
    )

    answers = answers_for(clarification, {"ceza_turu": "bildirge"})

    assert [(a.question_id, a.value, a.unknown) for a in answers] == [
        ("q1", "bildirge", False),
        ("q2", None, True),
    ]


async def test_the_smoke_run_scores_the_cases_with_fake_models(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = Script(
        intake=INTAKE_SB016,
        holding={"rows": [row("statute:5510:m102", "tebliğ tarihinden itibaren onbeş gün içinde")]},
        drafts=[
            draft(
                points=[
                    {
                        "text": "Peşin ödeme indirimi onbeş gün içinde uygulanmaktadır.",
                        "citations": [{"source_id": "statute:5510:m102", "sub": "5"}],
                    }
                ],
                headline="İki indirim ayrıdır ve 15 gün ortak şarttır.",
            )
        ],
    )
    model = scripted(script)
    graph = build_eval_graph(Models(model, model), FixtureKb())

    results = await run_eval(graph, Tracing(), CASES, only=["SB-016"])

    assert [r.case_id for r in results] == ["SB-016"]
    result = results[0]
    assert result.answer is not None and result.error is None
    assert result.metrics["schema"] == 1.0
    assert result.metrics["must_ask"] == 1.0
    assert result.metrics["formal_mode"] == 1.0
    assert result.input_tokens > 0
    table = render(results)
    assert table.splitlines()[0].startswith("vaka")
    assert "SB-016" in table.splitlines()[1]

    # Exercise the CLI parser and JSON/table output with the same non-network provider.
    monkeypatch.setattr("agent.eval.Models", lambda fast, strong: Models(model, model))
    monkeypatch.setattr("agent.eval.Tracing.from_settings", lambda settings: Tracing())
    report = tmp_path / "eval.json"
    assert (
        await amain([str(CASES), "--kb", "fixtures", "--case", "SB-016", "--json", str(report)])
        == 0
    )
    saved = json.loads(report.read_text())
    assert [r["case_id"] for r in saved] == ["SB-016"]
    assert saved[0]["metrics"]["schema"] == saved[0]["metrics"]["formal_mode"] == 1.0
    assert saved[0]["error"] is None and saved[0]["cost"] is None
    assert "SB-016" in capsys.readouterr().out


async def test_a_case_that_stops_before_the_gate_is_reported_not_fatal() -> None:
    model = scripted(Script(intake=INTAKE_SB016))
    graph = build_eval_graph(Models(model, model), FailingKb(KbUnavailable("down")))

    results = await run_eval(graph, Tracing(), CASES, only=["SB-016"])

    result = results[0]
    assert result.answer is None and result.error == "kb_unavailable"
    assert (result.dropped, result.fell_back) == (0, False)
    assert "kb_unavailable" in render(results)


async def test_fixture_kb_preserves_literal_quotes_and_original_offsets() -> None:
    from hukuk_models.chat import CitationRef

    kb = FixtureKb()
    ref = CitationRef(
        source_id="statute:test",
        category="statute",
        label="Test m.1/7",
        ref="9999 m.1/7",
        review_status="approved",
        verification="not_applicable",
        quote="Kaynakta bulunan özgün alıntı",
        char_start=20,
        char_end=47,
    )
    kb._add(ref)
    hit = (await kb.search("9999 m.1"))[0]
    assert hit.matches[0].text == ref.quote
    assert hit.matches[0].char_start == ref.char_start
    assert hit.matches[0].text is not None
    assert not hit.matches[0].text.startswith("(7)")


async def test_fixture_kb_uses_the_same_exclusive_valid_to_as_task14() -> None:
    from hukuk_models.chat import CitationRef

    kb = FixtureKb()
    kb._add(
        CitationRef(
            source_id="statute:expired",
            category="statute",
            label="Test m.1",
            ref="9999 m.1",
            review_status="approved",
            verification="not_applicable",
            quote="Kaynakta bulunan özgün alıntı",
            valid_from=date(2020, 1, 1),
            valid_to=date(2026, 10, 3),
        )
    )
    assert await kb.search("9999 m.1", as_of=date(2026, 10, 3)) == []
    assert len(await kb.search("9999 m.1", as_of=date(2026, 10, 2))) == 1
