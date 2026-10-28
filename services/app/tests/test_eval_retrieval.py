"""The retrieval eval's scoring and its question set (task 14); no database."""

import json

from app.eval.retrieval import DEFAULT_FILE, matches, recall, report

STATUTE = {"category": "statute", "ref": "4857 m.18"}
DECISION = {"category": "decision", "chamber": "9. HD", "esas": "2016/28920", "karar": "2017/17860"}
HIT = {"category": "decision", "ref": "Yargıtay 9. HD, E. 2016/28920 K. 2017/17860, 09.11.2017"}


def test_matching() -> None:
    assert matches(STATUTE, {"category": "statute", "ref": "4857 m.18"})
    assert not matches(STATUTE, {"category": "statute", "ref": "4857 m.180"})
    assert not matches(STATUTE, {"category": "decision", "ref": "4857 m.18"})
    assert matches(DECISION, HIT)
    other = {"category": "decision", "ref": "Yargıtay 9. HD, E. 2016/289200 K. 2017/17860"}
    assert not matches(DECISION, other)
    nineteenth = {"category": "decision", "ref": "Yargıtay 19. HD, E. 2016/28920 K. 2017/17860"}
    assert not matches(DECISION, nineteenth)


def test_recall_counts_the_expected_sources_in_the_first_k() -> None:
    results = [
        {"category": "statute", "ref": "4857 m.5"},
        HIT,
        {"category": "statute", "ref": "4857 m.18"},
    ]
    assert recall([STATUTE, DECISION], results, 2) == 0.5
    assert recall([STATUTE, DECISION], results, 3) == 1.0
    assert recall([], results, 3) == 1.0


def test_report_lists_recall_and_misses() -> None:
    lines = report([{"id": "Q1", "expected": [STATUTE]}], [[]])
    assert lines[0] == "recall@5: 0.000 (1 questions)"
    assert "  Q1: 4857 m.18" in lines


def test_the_question_set_is_well_formed() -> None:
    questions = json.loads(DEFAULT_FILE.read_text(encoding="utf-8"))
    assert len(questions) == 15
    assert len({q["id"] for q in questions}) == 15
    for q in questions:
        assert q["question"] and q["expected"]
        for e in q["expected"]:
            assert e["category"] in {"statute", "decision"}
            assert (e["category"] == "statute" and e["ref"]) or e["esas"] and e["karar"]
