"""Deterministic scorer of the eval set (task 15).

    python eval/score.py ANSWER.json CASE.yaml [--clarification SCENARIO_OR_CLARIFICATION.json]

An `Answer` (hukuk_models.chat) is checked against one case (`eval/cases/*.yaml`). The metrics do
not call a model; a judge for the rest of the quality comes at the end of v1. A metric is 1.0 when
fully met, 0.0 when not, and None when it cannot be measured from the input (`must_ask` without a
clarification). The score is the mean of the measured metrics.

The eval runner (`python -m agent.eval`) puts one row per case into the acceptance table of
`render_table`; `acceptance` checks the thresholds of task 19 over those rows.
"""

import argparse
import json
import math
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from hukuk_models.chat import DISCLAIMER, Answer
from hukuk_models.formal_turkish import progressive_forms

DATE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
# What is the law's own wording or an id, not the answer's: neither "-iyor" nor must_not apply.
QUOTED_KEYS = {"quote", "condition_quote", "source_id"}
NOT_SCANNED_FOR_MODE = QUOTED_KEYS | {"ref", "label"}


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | None
    detail: str = ""


def normalize(text: str) -> str:
    """Lower case with the Turkish dotted/dotless i, single spaces."""
    return " ".join(text.replace("İ", "i").replace("I", "ı").lower().split())


def canonical_ref(ref: str) -> str:
    """A künye as compared: no court name, no date, no punctuation at the end."""
    text = normalize(DATE.sub(" ", ref)).replace("yargıtay ", "")
    return " ".join(text.split()).strip(" ,;.")


def covers(cited: str, wanted: str) -> bool:
    """`cited` is the wanted künye or a part of it ("4857 m.18/1" covers "4857 m.18")."""
    return cited == wanted or cited.startswith((wanted + "/", wanted + " "))


def strings(node: Any, skip: set[str]) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [s for item in node for s in strings(item, skip)]
    if isinstance(node, dict):
        return [s for key, value in node.items() if key not in skip for s in strings(value, skip)]
    return []


def cited_citations(answer: dict[str, Any]) -> list[dict[str, Any]]:
    holding = answer.get("holding_map") or {}
    found = [c for point in answer.get("points", []) for c in point.get("citations", [])]
    found += [row.get("citation") for row in holding.get("rows", []) if row.get("citation")]
    found += holding.get("citations", [])
    found += [c for info in answer.get("missing_info", []) for c in info.get("citations", [])]
    return found


def _fraction(hits: int, total: int) -> float:
    return hits / total if total else 1.0


def must_cite_metric(answer: dict[str, Any], case: dict[str, Any]) -> Metric:
    """The share of the wanted künyeler the answer cites. Those the case lists in
    `expected.missing_in_kb` are not in the knowledge base: a missing source, not an error of
    the agent, so they leave the denominator; None when nothing is left to cite."""
    expected = case["expected"]
    missing = {canonical_ref(m) for m in expected.get("missing_in_kb", [])}
    wanted = [m for m in expected.get("must_cite", []) if canonical_ref(m) not in missing]
    if not wanted:
        return Metric("must_cite", None, "every source is missing_in_kb")
    refs = {canonical_ref(c.get("ref", "")) for c in cited_citations(answer)}
    uncovered = [m for m in wanted if not any(covers(r, canonical_ref(m)) for r in refs)]
    return Metric(
        "must_cite", _fraction(len(wanted) - len(uncovered), len(wanted)), ", ".join(uncovered)
    )


def must_ask_metric(case: dict[str, Any], clarification: dict[str, Any] | None) -> Metric:
    must_ask = case["expected"].get("must_ask", [])
    if clarification is None and must_ask:
        return Metric("must_ask", None, "no clarification given")
    asked = {q.get("fact_key") for q in (clarification or {}).get("questions", [])}
    unasked = [m for m in must_ask if m not in asked]
    return Metric(
        "must_ask", _fraction(len(must_ask) - len(unasked), len(must_ask)), ", ".join(unasked)
    )


def _own_wording(answer: dict[str, Any]) -> dict[str, Any]:
    """The answer without the values of `source_gap.given_facts`: those are the user's own
    words, repeated back, not the answer's."""
    gap = answer.get("source_gap")
    if not isinstance(gap, dict) or not gap.get("given_facts"):
        return answer
    facts = [{k: v for k, v in f.items() if k != "value"} for f in gap["given_facts"]]
    return answer | {"source_gap": gap | {"given_facts": facts}}


def must_not_found(answer: dict[str, Any], case: dict[str, Any]) -> list[str]:
    text = normalize(" ".join(strings(_own_wording(answer), QUOTED_KEYS)))
    return [m for m in case["expected"].get("must_not", []) if normalize(m) in text]


def progressive_found(answer: dict[str, Any]) -> list[str]:
    """The "-iyor" forms of the answer's own wording (md. 24)."""
    return progressive_forms(strings(_own_wording(answer), NOT_SCANNED_FOR_MODE))


def unread_citations(answer: dict[str, Any], read_ids: set[str]) -> list[str]:
    """The künyeler the answer cites from a source not in `read_ids`, the sources the run read
    (the graph state `read`, md. 25)."""
    return [
        c.get("ref", "?") for c in cited_citations(answer) if c.get("source_id") not in read_ids
    ]


def score(
    answer: dict[str, Any], case: dict[str, Any], clarification: dict[str, Any] | None = None
) -> list[Metric]:
    expected = case["expected"]
    metrics: list[Metric] = []

    try:
        Answer.model_validate(answer)
        metrics.append(Metric("schema", 1.0))
    except ValidationError as exc:
        metrics.append(
            Metric("schema", 0.0, f"{exc.error_count()} errors: {exc.errors()[0]['msg']}")
        )

    metrics.append(
        Metric(
            "status",
            float(answer.get("status") == expected["status"]),
            f"{answer.get('status')} (expected {expected['status']})",
        )
    )

    headline = normalize(answer.get("headline", ""))
    wanted = expected.get("headline_contains", [])
    # "toplu iş sözleşmesi|TİS": an item is met by any of its alternatives.
    missing = [w for w in wanted if not any(normalize(a) in headline for a in w.split("|"))]
    metrics.append(
        Metric("headline", _fraction(len(wanted) - len(missing), len(wanted)), ", ".join(missing))
    )

    metrics.append(must_cite_metric(answer, case))
    cited = cited_citations(answer)

    # Cheap by design: `Answer` already requires this of a valid answer; here it also holds for
    # answers that fail the schema, so the two metrics fail independently.
    read = {c.get("source_id") for c in answer.get("read_sources", {}).get("items", [])}
    unread = [c.get("ref", "?") for c in cited if c.get("source_id") not in read]
    metrics.append(
        Metric(
            "citation_validity",
            _fraction(len(cited) - len(unread), len(cited)) if cited else 0.0,
            ", ".join(unread) if cited else "no citations",
        )
    )

    metrics.append(must_ask_metric(case, clarification))

    found = must_not_found(answer, case)
    must_not = expected.get("must_not", [])
    metrics.append(
        Metric("must_not", _fraction(len(must_not) - len(found), len(must_not)), ", ".join(found))
    )

    progressive = progressive_found(answer)
    metrics.append(Metric("formal_mode", float(not progressive), ", ".join(progressive)))

    metrics.append(Metric("disclaimer", float(answer.get("disclaimer") == DISCLAIMER)))
    return metrics


# The acceptance thresholds of task 19 (proposal, Orhan's approval).
MUST_ASK_MEAN = 0.8
MUST_ASK_FLOOR = 0.5
MUST_CITE_MEAN = 0.7
# At least 12 of the 20 cases get a substantive answer, not "kaynak yetersiz".
SUBSTANTIVE_SHARE = 12 / 20


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _measured(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [r[key] for r in rows if r[key] is not None]


def acceptance(rows: list[dict[str, Any]], not_run: Sequence[str] = ()) -> tuple[bool, list[str]]:
    """Whether the rows of a run meet the thresholds, and the reasons where they do not. A row
    is the eval runner's result of one case; a case the budget stopped is in `not_run`."""
    reasons = []
    if not_run:
        reasons.append(f"koşulmayan vaka (bütçe tavanı): {', '.join(not_run)}")
    if failed := [r["case_id"] for r in rows if r["error"]]:
        reasons.append(f"hata ile biten vaka: {', '.join(failed)}")
    ask = _mean(_measured(rows, "must_ask"))
    if ask is not None and ask < MUST_ASK_MEAN:
        reasons.append(f"must_ask ortalaması {_percent(ask)} < {_percent(MUST_ASK_MEAN)}")
    low = [
        r["case_id"] for r in rows if r["must_ask"] is not None and r["must_ask"] < MUST_ASK_FLOOR
    ]
    if low:
        reasons.append(f"must_ask < {_percent(MUST_ASK_FLOOR)}: {', '.join(low)}")
    cite = _mean(_measured(rows, "must_cite"))
    if cite is not None and cite < MUST_CITE_MEAN:
        reasons.append(
            f"must_cite (missing_in_kb hariç) ortalaması {_percent(cite)} "
            f"< {_percent(MUST_CITE_MEAN)}"
        )
    for key, label in (
        ("must_not", "must_not ihlali"),
        ("mode", "kip ihlali"),
        ("unread", "md.25 okunmamış kaynağa atıf"),
    ):
        bad = [r["case_id"] for r in rows if r[key]]
        if bad:
            reasons.append(f"{label}: {', '.join(bad)}")
    substantive = sum(r["substantive"] for r in rows)
    needed = math.ceil(SUBSTANTIVE_SHARE * len(rows))
    if substantive < needed:
        reasons.append(f"esaslı cevap {substantive}/{len(rows)} < {needed}")
    return not reasons, reasons


def _must_cite_cell(rows: list[dict[str, Any]]) -> str:
    """The mean over every case (the acceptance threshold; an error is 0) and over the answered
    cases only."""
    answered = [r for r in rows if not r["error"]]
    every, only = _mean(_measured(rows, "must_cite")), _mean(_measured(answered, "must_cite"))
    return f"{_percent(every)} (cevaplı {_percent(only)})"


def _percent(value: float | None) -> str:
    """A share in the Turkish way: %80."""
    return "-" if value is None else f"%{value * 100:.0f}"


def _answer_kind(row: dict[str, Any]) -> str:
    if row["error"]:
        return f"hata: {row['error']}"
    return "esaslı" if row["substantive"] else "kaynak yetersiz"


def _topic_cell(row: dict[str, Any]) -> str:
    topic, wanted = row["topic"] or "-", row["expected_topic"]
    return topic if wanted is None or topic == wanted else f"{topic} (beklenen {wanted})"


DROP_KEYS = ("rows", "points", "branches", "sentences", "citations")
TABLE_HEADER = (
    "vaka",
    "şablon",
    "must_ask",
    "must_cite",
    "kaynak eksik",
    "must_not",
    "başlık",
    "kip",
    "md.25",
    "düşen (satır/nokta/dal/cümle/atıf)",
    "kapı sorunları",
    "cevap",
    "token (gir/çık)",
    "maliyet $",
    "süre s",
    "netleştirme turu",
)


def _line(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def render_table(rows: list[dict[str, Any]], passed: bool, reasons: list[str]) -> str:
    """The markdown acceptance table of a run: one row per case, the total and the verdict."""
    lines = [_line(list(TABLE_HEADER)), _line(["---"] * len(TABLE_HEADER))]
    for r in rows:
        issues = ", ".join(f"{code}×{n}" for code, n in sorted(r["issue_counts"].items()))
        lines.append(
            _line(
                [
                    r["case_id"],
                    _topic_cell(r),
                    _percent(r["must_ask"]),
                    _percent(r["must_cite"]),
                    str(len(r["missing_in_kb"])),
                    str(len(r["must_not"])),
                    _percent(r["headline"]),
                    str(len(r["mode"])),
                    str(len(r["unread"])),
                    "/".join(str(r["drops"].get(k, 0)) for k in DROP_KEYS),
                    issues or "-",
                    _answer_kind(r),
                    f"{r['input_tokens']}/{r['output_tokens']}",
                    "-" if r["cost"] is None else f"{r['cost']:.4f}",
                    f"{r['seconds']:.1f}",
                    str(r["rounds"]),
                ]
            )
        )
    matched = sum(r["expected_topic"] is None or r["topic"] == r["expected_topic"] for r in rows)
    cost = sum(r["cost"] or 0.0 for r in rows)
    lines.append(
        _line(
            [
                "toplam",
                f"{matched}/{len(rows)} eşleşti",
                _percent(_mean(_measured(rows, "must_ask"))),
                _must_cite_cell(rows),
                str(sum(len(r["missing_in_kb"]) for r in rows)),
                str(sum(len(r["must_not"]) for r in rows)),
                _percent(_mean(_measured(rows, "headline"))),
                str(sum(len(r["mode"]) for r in rows)),
                str(sum(len(r["unread"]) for r in rows)),
                "/".join(str(sum(r["drops"].get(k, 0) for r in rows)) for k in DROP_KEYS),
                "-",
                f"esaslı {sum(r['substantive'] for r in rows)}/{len(rows)}",
                f"{sum(r['input_tokens'] for r in rows)}/{sum(r['output_tokens'] for r in rows)}",
                f"${cost:.2f}",
                f"{sum(r['seconds'] for r in rows):.1f}",
                str(sum(r["rounds"] for r in rows)),
            ]
        )
    )
    lines.append("")
    lines.append("**PASS**" if passed else "**FAIL**")
    lines += [f"- {reason}" for reason in reasons]
    return "\n".join(lines)


def total(metrics: list[Metric]) -> float:
    measured = [m.value for m in metrics if m.value is not None]
    return sum(measured) / len(measured) if measured else 0.0


TEXT_LISTS = ("headline_contains", "must_cite", "missing_in_kb", "must_ask", "must_not")


def load_case(path: Path) -> dict[str, Any]:
    """A case file: `expected.topic` names the template the case falls into, and the sources the
    knowledge base lacks are listed in `expected.missing_in_kb` (task 19)."""
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    expected = loaded.get("expected")
    if not isinstance(expected, dict) or not isinstance(expected.get("topic"), str):
        raise ValueError(f"{path.name}: expected.topic names the template of the case")
    if "missing_in_kb" in loaded:
        raise ValueError(f"{path.name}: missing_in_kb is a list under expected")
    for key in TEXT_LISTS:
        items = expected.get(key, [])
        # An unquoted law number ("- 5434") loads as an int and would fail the scoring later.
        if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
            raise ValueError(f"{path.name}: expected.{key} is a list of text (quote numbers)")
    return loaded


def load_clarification(path: Path) -> dict[str, Any]:
    """The clarification of a scenario file (`{"clarification": ...}`) or of a file holding one."""
    loaded = json.loads(path.read_text(encoding="utf-8"))
    clarification = loaded.get("clarification", loaded)
    assert isinstance(clarification, dict)
    return clarification


def render(case_id: str, metrics: list[Metric]) -> str:
    lines = [f"{case_id}"]
    for m in metrics:
        value = "n/a" if m.value is None else f"{m.value:.2f}"
        lines.append(f"  {m.name:<18}{value:>5}  {m.detail}".rstrip())
    lines.append(f"  {'score':<18}{total(metrics):>5.2f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("answer", type=Path)
    parser.add_argument("case", type=Path)
    parser.add_argument(
        "--clarification", type=Path, help="scenario or clarification JSON (must_ask)"
    )
    args = parser.parse_args(argv)
    case = load_case(args.case)
    answer = json.loads(args.answer.read_text(encoding="utf-8"))
    clarification = load_clarification(args.clarification) if args.clarification else None
    print(render(case["id"], score(answer, case, clarification)))


if __name__ == "__main__":
    main(sys.argv[1:])
