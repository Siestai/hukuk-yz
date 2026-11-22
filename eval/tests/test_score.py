"""The eval set and its scorer (`eval/score.py`, tasks 15 and 19): the cases are well formed, the
hand-made fixtures score full marks, and the acceptance table of a run says PASS or FAIL and why."""

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

EVAL = Path(__file__).parents[1]
FIXTURES = EVAL / "fixtures"
CASES = EVAL / "cases"
IDS = ["SB-001", "SB-016", "SB-026"]

spec = importlib.util.spec_from_file_location("eval_score", EVAL / "score.py")
assert spec and spec.loader
score_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score_module)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_answer(name: str) -> dict[str, Any]:
    return load(FIXTURES / name)  # type: ignore[no-any-return]


def test_cases_are_well_formed() -> None:
    paths = sorted(CASES.glob("*.yaml"))
    assert len(paths) == 20
    for path in paths:
        case = score_module.load_case(path)
        assert case["id"] == path.stem
        assert case["question"].strip()
        expected = case["expected"]
        assert expected["status"] in ("definite", "conditional")
        assert expected["topic"]
        assert expected["headline_contains"] and expected["must_cite"]
        assert case["tags"]


@pytest.mark.parametrize(
    ("case", "error"),
    [
        ({"id": "SB-1", "question": "?", "expected": {"status": "definite"}}, "topic"),
        (
            {
                "id": "SB-1",
                "question": "?",
                "expected": {"topic": "ise_iade", "status": "definite"},
                "missing_in_kb": ["4857 m.18"],
            },
            "missing_in_kb",
        ),
        (
            {
                "id": "SB-1",
                "question": "?",
                "expected": {"topic": "ise_iade", "status": "definite", "missing_in_kb": "x"},
            },
            "missing_in_kb",
        ),
        # An unquoted law number is an int in YAML; a künye is always text.
        (
            {
                "id": "SB-1",
                "question": "?",
                "expected": {"topic": "ise_iade", "status": "definite", "must_cite": [5434]},
            },
            "must_cite",
        ),
        (
            {
                "id": "SB-1",
                "question": "?",
                "expected": {"topic": "ise_iade", "status": "definite", "missing_in_kb": [6772]},
            },
            "missing_in_kb",
        ),
    ],
)
def test_a_case_without_its_topic_or_with_missing_in_kb_outside_expected_is_refused(
    tmp_path: Path, case: dict[str, Any], error: str
) -> None:
    path = tmp_path / "SB-1.yaml"
    path.write_text(yaml.safe_dump(case, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        score_module.load_case(path)


@pytest.mark.parametrize("path", sorted(CASES.glob("*.yaml")), ids=lambda p: p.stem)
def test_every_case_scores_an_answer_without_failing(path: Path) -> None:
    case = score_module.load_case(path)
    answer = _fixture_answer("SB-001.answer.json")
    questions = [{"fact_key": key} for key in case["expected"].get("must_ask", [])[:1]]

    metrics = score_module.score(answer, case, {"questions": questions})

    assert {m.name for m in metrics} >= {"must_cite", "must_ask", "must_not", "formal_mode"}
    assert isinstance(score_module.must_cite_metric({}, case).detail, str)
    score_module.must_not_found(answer, case)
    score_module.unread_citations(answer, set())


def test_the_users_own_words_in_the_source_gap_are_not_scanned() -> None:
    case = {"expected": {"must_not": ["düşürüyor"]}}
    words = "İşveren ücretimi düşürüyor"
    answer = {
        "headline": "Kaynak yetersizdir.",
        "source_gap": {"given_facts": [{"key": "olay", "label": "Olay", "value": words}]},
    }

    assert score_module.progressive_found(answer) == []
    assert score_module.must_not_found(answer, case) == []
    # The label is the harness's wording and is still scanned.
    answer["source_gap"]["given_facts"][0]["label"] = words
    assert score_module.must_not_found(answer, case) == ["düşürüyor"]


@pytest.mark.parametrize("case_id", IDS)
def test_every_fixture_answer_gets_full_marks(case_id: str) -> None:
    case = score_module.load_case(CASES / f"{case_id}.yaml")
    scenario = load(FIXTURES / f"{case_id}.scenario.json")
    clarification = score_module.load_clarification(FIXTURES / f"{case_id}.scenario.json")
    for name in (scenario["on_skip"], scenario["on_complete"]):
        metrics = score_module.score(load(FIXTURES / name), case, clarification)
        # `status` is the expected one only for one of the two answers of a scenario.
        measured = [m for m in metrics if m.name != "status"]
        assert all(m.value == 1.0 for m in measured), score_module.render(case_id, metrics)


@pytest.mark.parametrize("case_id", IDS)
def test_one_fixture_answer_has_the_expected_status(case_id: str) -> None:
    case = score_module.load_case(CASES / f"{case_id}.yaml")
    scenario = load(FIXTURES / f"{case_id}.scenario.json")
    statuses = [
        load(FIXTURES / n)["status"] for n in (scenario["on_skip"], scenario["on_complete"])
    ]
    assert case["expected"]["status"] in statuses


def test_scorer_catches_what_it_should() -> None:
    case = score_module.load_case(CASES / "SB-016.yaml")
    clarification = score_module.load_clarification(FIXTURES / "SB-016.scenario.json")
    raw = _fixture_answer("SB-016.answer.json")
    raw["headline"] = "Cevap verilmiyor."
    raw["points"][0]["text"] += " SSİY m.102"
    for point in raw["points"]:
        for citation in point["citations"]:
            citation["ref"] = "9999 m.1"
    for row in raw["holding_map"]["rows"]:
        row["citation"]["ref"] = "9999 m.1"
    for citation in raw["holding_map"]["citations"]:
        citation["ref"] = "9999 m.1"
    raw["disclaimer"] = ""
    by_name = {m.name: m for m in score_module.score(raw, case, clarification)}
    assert by_name["headline"].value == 0.0
    assert by_name["must_not"].value < 1.0
    assert by_name["formal_mode"].value == 0.0
    assert by_name["must_cite"].value < 1.0
    assert by_name["disclaimer"].value == 0.0
    assert by_name["schema"].value == 0.0
    # must_ask cannot be measured without the clarification
    none = {m.name: m for m in score_module.score(_fixture_answer("SB-016.answer.json"), case)}
    assert none["must_ask"].value is None


def test_a_headline_item_is_met_by_any_of_its_alternatives() -> None:
    case = {"expected": {"status": "definite", "headline_contains": ["toplu iş sözleşmesi|TİS"]}}

    def headline(text: str) -> float | None:
        metrics = {m.name: m for m in score_module.score({"headline": text}, case)}
        return metrics["headline"].value

    assert headline("TİS'ten doğan alacak") == 1.0
    assert headline("Toplu iş sözleşmesinden doğan alacak") == 1.0
    assert headline("Sözleşmeden doğan alacak") == 0.0


def cited(*refs: tuple[str, str]) -> dict[str, Any]:
    """An answer whose one point cites (ref, source_id) pairs."""
    return {"points": [{"citations": [{"ref": r, "source_id": s} for r, s in refs]}]}


def test_must_cite_leaves_the_sources_missing_in_the_kb_out_of_the_denominator() -> None:
    case = {
        "expected": {
            "must_cite": ["4857 m.18", "4857 m.17", "HMK m.92/2"],
            "missing_in_kb": ["HMK m.92/2"],
        }
    }

    metric = score_module.must_cite_metric(cited(("4857 m.18/1", "a")), case)

    assert metric.value == 0.5
    assert "4857 m.17" in metric.detail and "HMK" not in metric.detail
    # Nothing left to cite once every wanted source is missing: not measurable.
    case["expected"]["missing_in_kb"] = case["expected"]["must_cite"]
    assert score_module.must_cite_metric(cited(), case).value is None


def test_a_citation_of_a_source_the_run_did_not_read_is_found() -> None:
    answer = cited(("4857 m.18", "statute:4857:m18"), ("4857 m.25", "statute:4857:m25"))

    assert score_module.unread_citations(answer, {"statute:4857:m18"}) == ["4857 m.25"]
    assert score_module.unread_citations(answer, {"statute:4857:m18", "statute:4857:m25"}) == []


def run_row(case_id: str = "SB-001", **changes: Any) -> dict[str, Any]:
    """A case row of a run that meets every threshold."""
    row: dict[str, Any] = {
        "case_id": case_id,
        "expected_topic": "ise_iade",
        "topic": "ise_iade",
        "must_ask": 1.0,
        "must_cite": 1.0,
        "missing_in_kb": [],
        "must_not": [],
        "headline": 1.0,
        "mode": [],
        "unread": [],
        "drops": {"rows": 0, "points": 0, "branches": 0, "sentences": 0, "citations": 0},
        "issue_counts": {},
        "rounds": 1,
        "fallback": False,
        "substantive": True,
        "input_tokens": 1000,
        "output_tokens": 100,
        "cost": 0.1,
        "seconds": 2.0,
        "error": None,
    }
    return row | changes


def twenty(**changes_of: dict[str, Any]) -> list[dict[str, Any]]:
    """Twenty passing rows; `changes_of["SB-003"] = {...}` changes one of them."""
    ids = [f"SB-{n:03d}" for n in range(1, 21)]
    return [run_row(i, **changes_of.get(i.replace("-", "_"), {})) for i in ids]


def test_a_run_that_meets_every_threshold_passes() -> None:
    rows = twenty(SB_001={"must_ask": 0.6, "must_cite": None}, SB_002={"must_cite": 0.4})
    rows[12:] = [r | {"substantive": False, "fallback": True} for r in rows[12:]]

    assert score_module.acceptance(rows) == (True, [])


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        ([run_row(f"SB-{n:03d}", must_ask=0.7) for n in range(1, 21)], "must_ask ortalaması"),
        (twenty(SB_003={"must_ask": 0.4}), "SB-003"),
        ([run_row(f"SB-{n:03d}", must_cite=0.6) for n in range(1, 21)], "must_cite"),
        (twenty(SB_004={"must_not": ["kesin"]}), "must_not"),
        (twenty(SB_005={"mode": ["ediyor"]}), "kip"),
        (twenty(SB_006={"unread": ["4857 m.25"]}), "md.25"),
        ([run_row(f"SB-{n:03d}", substantive=n <= 11) for n in range(1, 21)], "esaslı"),
    ],
)
def test_a_run_below_a_threshold_fails_and_says_which(
    rows: list[dict[str, Any]], reason: str
) -> None:
    passed, reasons = score_module.acceptance(rows)

    assert not passed
    assert any(reason in r for r in reasons), reasons


def test_a_case_that_ended_in_an_error_is_its_own_reason() -> None:
    passed, reasons = score_module.acceptance(twenty(SB_007={"error": "kb_unavailable"}))

    assert not passed
    assert any("hata" in r and "SB-007" in r for r in reasons)


def test_a_run_stopped_by_the_budget_fails_with_the_cases_it_did_not_run() -> None:
    passed, reasons = score_module.acceptance(twenty()[:15], not_run=["SB-016", "SB-017"])

    assert not passed
    assert any("SB-016" in r and "SB-017" in r for r in reasons)


def test_the_substantive_threshold_scales_with_the_cases_run() -> None:
    rows = [run_row(f"SB-{n:03d}", substantive=n <= 3) for n in range(1, 6)]

    assert score_module.acceptance(rows) == (True, [])
    assert not score_module.acceptance(rows[:2] + [run_row("SB-009", substantive=False)] * 3)[0]


def test_the_table_has_a_row_per_case_a_total_and_the_verdict() -> None:
    rows = [
        run_row("SB-001"),
        run_row(
            "SB-003",
            expected_topic="calisma_kosulu_degisikligi",
            topic="genel",
            must_cite=None,
            missing_in_kb=["HMK m.92/2"],
            mode=["ediyor"],
            drops={"rows": 1, "points": 2, "branches": 0, "sentences": 3, "citations": 0},
            issue_counts={"progressive": 2},
            rounds=2,
            fallback=True,
            substantive=False,
            cost=None,
        ),
        run_row("SB-005", error="kb_unavailable", substantive=False, must_cite=0.0),
    ]

    table = score_module.render_table(rows, *score_module.acceptance(rows))
    lines = table.splitlines()

    assert lines[0].startswith("| vaka | şablon | must_ask | must_cite | kaynak eksik |")
    sb003 = next(line for line in lines if line.startswith("| SB-003"))
    assert "genel (beklenen calisma_kosulu_degisikligi)" in sb003
    assert "| 1/2/0/3/0 |" in sb003 and "progressive×2" in sb003
    assert "kaynak yetersiz" in sb003 and sb003.endswith("| 2 |")
    assert "hata: kb_unavailable" in next(line for line in lines if line.startswith("| SB-005"))
    total = next(line for line in lines if line.startswith("| toplam"))
    assert "2/3" in total  # templates matched
    assert "esaslı 1/3" in total
    assert "$0.20" in total
    # must_cite over every case (an error is 0) and over the answered ones only.
    assert "| %50 (cevaplı %100) |" in total
    assert "**FAIL**" in table and "kip" in table
