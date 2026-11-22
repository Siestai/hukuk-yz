"""The eval runner: the fixture knowledge base, the answers to the questions, the smoke run with
fake models that CI runs, the cost estimate and the budget gate (with fake costs)."""

import json
from datetime import date
from pathlib import Path

import pytest
from agent_fakes import INTAKE_SB016, FailingKb, Script, draft, row, scripted

from agent.eval import (
    Budget,
    EvalLlm,
    FixtureKb,
    amain,
    answers_for,
    build_eval_graph,
    estimate,
    load_score_module,
    run_case,
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


SB016_SCRIPT = Script(
    intake=INTAKE_SB016,
    holding={
        "rows": [
            row("statute:5510:m102", "tebliğ tarihinden itibaren onbeş gün içinde"),
            # Not in the text read: sent back once, then dropped with its reason.
            row("statute:5510:m102", "kanunda hiç yazmayan bir ifade"),
        ]
    },
    drafts=[
        draft(
            missing=False,
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


async def test_the_smoke_run_scores_the_cases_with_fake_models(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    model = scripted(SB016_SCRIPT)
    llm = EvalLlm(Models(model, model))
    graph = build_eval_graph(llm, FixtureKb())

    run = await run_eval(graph, llm, Tracing(), CASES, only=["SB-016"])

    assert [r.case_id for r in run.results] == ["SB-016"] and run.not_run == []
    result = run.results[0]
    assert result.answer is not None and result.error is None
    assert result.metrics["schema"] == 1.0
    assert result.must_ask == result.metrics["must_ask"] == 1.0
    assert result.mode == [] and result.unread == [] and result.must_not == []
    assert result.topic == "idari_para_cezasi" and result.trace_id
    assert result.intake == INTAKE_SB016
    assert set(result.drops) == {"rows", "points", "branches", "sentences", "citations"}
    assert result.input_tokens > 0
    # What the retrieve step read, did not read and found missing, and the spend of each node.
    assert set(result.retrieved) == {"read", "unread", "missing"}
    assert "5510 m.102" in result.retrieved["read"]
    assert [n["node"] for n in result.nodes][:2] == ["intake", "clarify"]
    assert sum(n["input_tokens"] for n in result.nodes) == result.input_tokens
    assert {"models", "output_tokens", "cost", "seconds"} <= set(result.nodes[0])
    # Why the holding map dropped its rows, from the trace.
    assert result.rows_dropped_by == {"quote_not_found": 1}

    # The CLI: the table on stdout, the result and the table under --results, the intake
    # output of every case under --record-intake.
    monkeypatch.setattr("agent.eval.Models", lambda fast, strong: Models(model, model))
    monkeypatch.setattr("agent.eval.Tracing.from_settings", lambda settings: Tracing())
    results, intake = tmp_path / "results", tmp_path / "intake"
    argv = [str(CASES), "--kb", "fixtures", "--case", "SB-016", "--tag", "smoke"]
    argv += ["--results", str(results), "--record-intake", str(intake)]
    code = await amain(argv)
    [saved_path] = results.glob("*-smoke.json")
    assert saved_path.name == f"{date.today().isoformat()}-smoke.json"
    saved = json.loads(saved_path.read_text())
    assert [r["case_id"] for r in saved["cases"]] == ["SB-016"]
    assert saved["cases"][0]["metrics"]["formal_mode"] == 1.0
    assert saved["cases"][0]["intake"] == INTAKE_SB016
    assert saved["cases"][0]["error"] is None and saved["cases"][0]["cost"] is None
    assert saved["cases"][0]["retrieved"]["read"] and saved["cases"][0]["nodes"]
    assert saved["not_run"] == [] and isinstance(saved["passed"], bool)
    # A run below the thresholds exits with 1.
    assert code == (0 if saved["passed"] else 1)
    table = saved_path.with_suffix(".md").read_text()
    assert "| SB-016 |" in table and "| toplam |" in table
    assert json.loads((intake / "SB-016.json").read_text()) == INTAKE_SB016
    assert "| SB-016 |" in capsys.readouterr().out


async def test_a_case_that_stops_before_the_gate_is_reported_not_fatal() -> None:
    model = scripted(Script(intake=INTAKE_SB016))
    llm = EvalLlm(Models(model, model))
    graph = build_eval_graph(llm, FailingKb(KbUnavailable("down")))

    run = await run_eval(graph, llm, Tracing(), CASES, only=["SB-016"])

    result = run.results[0]
    assert result.answer is None and result.error == "kb_unavailable"
    assert not result.fallback and not result.substantive
    assert result.must_cite == 0.0


async def test_the_questions_of_a_follow_up_round_count_with_the_first_ones() -> None:
    model = scripted(Script(**vars(SB016_SCRIPT) | {"calls": []}))
    llm = EvalLlm(Models(model, model))
    graph = build_eval_graph(llm, FixtureKb())
    # The answer "bordro_gecersiz" to `fiil` opens the branch of its own facts: a second round.
    case = {
        "id": "SB-900",
        "question": "Bordro geçersiz sayıldı, idari para cezası indirimi uygulanır mı?",
        "facts": {"fiil": "bordro_gecersiz"},
        "expected": {
            "topic": "idari_para_cezasi",
            "status": "definite",
            "must_ask": ["fiil", "tutanakla_teslim", "defter_turu"],
            "must_cite": ["5510 m.102"],
        },
    }

    result = await run_case(graph, llm, Tracing(), load_score_module(CASES), case)

    assert result.rounds == 2
    assert {"fiil", "tutanakla_teslim", "defter_turu"} <= set(result.asked)
    assert result.must_ask == 1.0
    assert result.answer is not None and result.metrics["must_ask"] == 1.0


def flat_cost(monkeypatch: pytest.MonkeyPatch, usd: float) -> None:
    """Every model call costs `usd` (the fake models have no price)."""
    monkeypatch.setattr("agent.llm._cost", lambda model, i, o: usd)


async def test_the_budget_gate_stops_before_a_case_whose_estimate_would_pass_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flat_cost(monkeypatch, 0.1)
    script = Script(**vars(SB016_SCRIPT) | {"calls": []})
    model = scripted(script)
    budget = Budget(cap=1.0, per_case=0.95)
    llm = EvalLlm(Models(model, model), budget)
    graph = build_eval_graph(llm, FixtureKb())

    run = await run_eval(graph, llm, Tracing(), CASES, only=["SB-001", "SB-016", "SB-026"])

    assert [r.case_id for r in run.results] == ["SB-001"]
    assert run.results[0].error is None and run.not_run == ["SB-016", "SB-026"]
    # What the first case spent leaves less than the estimate of the next one.
    assert 0 < budget.spent <= budget.cap < budget.spent + budget.per_case


async def test_the_budget_gate_stops_a_case_at_the_cap_and_calls_no_model_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flat_cost(monkeypatch, 0.4)
    script = Script(**vars(SB016_SCRIPT) | {"calls": []})
    model = scripted(script)
    budget = Budget(cap=0.5, per_case=0.1)
    llm = EvalLlm(Models(model, model), budget)
    graph = build_eval_graph(llm, FixtureKb())

    run = await run_eval(graph, llm, Tracing(), CASES, only=["SB-001", "SB-016"])

    assert len(script.calls) == 2
    assert [r.error for r in run.results] == ["budget_exceeded"]
    assert run.not_run == ["SB-016"]


def earlier(cases: list[dict[str, object]], fast: str = "anthropic:a") -> dict[str, object]:
    return {"models": {"fast": fast, "strong": "anthropic:b"}, "cases": cases}


def test_the_estimate_is_the_mean_real_cost_of_answered_cases_of_earlier_runs_of_the_models(
    tmp_path: Path,
) -> None:
    answered: dict[str, object] = {"answer": {}, "error": None}
    # A run of the old format (no models) and one of another model are not used for the mean.
    (tmp_path / "2026-11-01-old.json").write_text(
        json.dumps([{"case_id": "SB-001", "cost": 0.3, "error": None}])
    )
    (tmp_path / "2026-11-02-other.json").write_text(
        json.dumps(earlier([{"case_id": "SB-001", "cost": 0.9, **answered}], fast="x:y"))
    )
    (tmp_path / "2026-11-03-new.json").write_text(
        json.dumps(
            earlier(
                [
                    {"case_id": "SB-016", "cost": 0.1, **answered},
                    {"case_id": "SB-021", "cost": 0.3, **answered},
                    {"case_id": "SB-024", "cost": None, **answered},
                    {"case_id": "SB-026", "cost": 0.01, "answer": None, "error": "kb_down"},
                ]
            )
        )
    )

    made = estimate(tmp_path, Models("anthropic:a", "anthropic:b"))

    assert made.per_case == pytest.approx(0.2)
    assert "2 vaka" in made.source and "önceki koşu" in made.source
    # What every earlier result file spent, for the cap of all rounds.
    assert made.earlier_spent == pytest.approx(0.3 + 0.9 + 0.1 + 0.3 + 0.01)


def test_without_earlier_runs_the_estimate_prices_assumed_tokens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    priced: list[tuple[str, int, int]] = []

    def cost(model: str, i: int, o: int) -> float | None:
        priced.append((model, i, o))
        return None if model == "x:unknown" else 0.05

    monkeypatch.setattr("agent.llm._cost", cost)

    made = estimate(tmp_path, Models("anthropic:fast", "anthropic:strong"))

    assert made.per_case == pytest.approx(0.1)
    assert {m for m, _, _ in priced} == {"anthropic:fast", "anthropic:strong"}
    assert "varsayım" in made.source
    unknown = estimate(tmp_path, Models("x:unknown", "anthropic:strong"))
    assert unknown.per_case is None and "x:unknown" in unknown.source


async def test_estimate_only_calls_no_model_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_graph(*args: object) -> None:
        raise AssertionError("--estimate builds no graph")

    monkeypatch.setattr("agent.eval.build_eval_graph", no_graph)

    argv = [str(CASES), "--estimate", "--case", "SB-001", "--case", "SB-016"]
    assert await amain([*argv, "--results", str(tmp_path)]) == 0

    out = capsys.readouterr().out
    assert "2 vaka" in out and "varsayım" in out
    assert list(tmp_path.iterdir()) == []


async def test_a_failed_model_call_counts_its_tokens_and_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flat_cost(monkeypatch, 0.1)
    # An intake the schema refuses every time: the call fails after its retries.
    script = Script(intake={"title": "konu yok"})
    model = scripted(script)
    budget = Budget(cap=5.0, per_case=0.1)
    llm = EvalLlm(Models(model, model), budget)
    graph = build_eval_graph(llm, FixtureKb())

    run = await run_eval(graph, llm, Tracing(), CASES, only=["SB-016"])

    result = run.results[0]
    assert len(script.calls) > 1 and result.error is not None
    assert result.input_tokens > 0 and result.cost == pytest.approx(0.1)
    assert budget.spent == pytest.approx(0.1)


async def test_under_a_budget_a_call_without_a_price_stops_the_run() -> None:
    script = Script(**vars(SB016_SCRIPT) | {"calls": []})
    model = scripted(script)
    llm = EvalLlm(Models(model, model), Budget(cap=5.0, per_case=0.1))
    graph = build_eval_graph(llm, FixtureKb())

    run = await run_eval(graph, llm, Tracing(), CASES, only=["SB-001", "SB-016"])

    assert len(script.calls) == 1
    assert [r.error for r in run.results] == ["budget_exceeded"]
    assert run.not_run == ["SB-016"]


async def test_an_exception_in_a_case_is_its_error_and_the_run_goes_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(trace: object) -> dict[str, int]:
        raise RuntimeError("boom")

    monkeypatch.setattr("agent.eval._issue_counts", broken)
    model = scripted(Script(**vars(SB016_SCRIPT) | {"calls": []}))
    llm = EvalLlm(Models(model, model))
    graph = build_eval_graph(llm, FixtureKb())
    seen: list[int] = []

    run = await run_eval(
        graph,
        llm,
        Tracing(),
        CASES,
        only=["SB-001", "SB-016"],
        after_case=lambda r: seen.append(len(r.results)),
    )

    assert [r.error for r in run.results] == ["eval_error: RuntimeError"] * 2
    assert run.results[0].input_tokens > 0
    # An error counts as no citation in the mean over every case; the nodes it ran are kept.
    assert [r.must_cite for r in run.results] == [0.0, 0.0]
    assert run.results[0].nodes and run.results[0].retrieved["read"] == []
    assert seen == [1, 2]


async def test_the_result_is_written_even_when_every_case_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def broken(trace: object) -> dict[str, int]:
        raise RuntimeError("boom")

    model = scripted(Script(**vars(SB016_SCRIPT) | {"calls": []}))
    monkeypatch.setattr("agent.eval._issue_counts", broken)
    monkeypatch.setattr("agent.eval.Models", lambda fast, strong: Models(model, model))
    monkeypatch.setattr("agent.eval.Tracing.from_settings", lambda settings: Tracing())
    argv = [str(CASES), "--kb", "fixtures", "--case", "SB-016", "--results", str(tmp_path)]

    assert await amain([*argv, "--tag", "broken"]) == 1

    [saved] = tmp_path.glob("*-broken.json")
    data = json.loads(saved.read_text())
    assert [c["error"] for c in data["cases"]] == ["eval_error: RuntimeError"]
    assert not data["passed"] and saved.with_suffix(".md").exists()


async def test_a_budget_cannot_be_held_for_a_model_without_a_price(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENT_MODEL_FAST", "x:unknown")
    # An estimate from earlier runs of the model does not make its calls priced.
    earlier_run = tmp_path / "2026-11-01-r0.json"
    earlier_run.write_text(
        json.dumps(
            {
                "models": {"fast": "x:unknown", "strong": "anthropic:claude-sonnet-5-5"},
                "cases": [{"case_id": "SB-001", "cost": 0.2, "answer": {}, "error": None}],
            }
        )
    )

    argv = [str(CASES), "--budget-usd", "1", "--results", str(tmp_path), "--kb", "fixtures"]
    assert await amain(argv) == 2

    assert "x:unknown" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == [earlier_run]


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
