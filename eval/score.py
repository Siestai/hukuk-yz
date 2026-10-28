"""Deterministic scorer of the eval set (task 15).

    python eval/score.py ANSWER.json CASE.yaml [--clarification SCENARIO_OR_CLARIFICATION.json]

An `Answer` (hukuk_models.chat) is checked against one case (`eval/cases/*.yaml`). The metrics do
not call a model; a judge for the rest of the quality comes at the end of v1. A metric is 1.0 when
fully met, 0.0 when not, and None when it cannot be measured from the input (`must_ask` without a
clarification). The score is the mean of the measured metrics.
"""

import argparse
import json
import re
import sys
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
    missing = [w for w in wanted if normalize(w) not in headline]
    metrics.append(
        Metric("headline", _fraction(len(wanted) - len(missing), len(wanted)), ", ".join(missing))
    )

    cited = cited_citations(answer)
    refs = {canonical_ref(c.get("ref", "")) for c in cited}
    must_cite = expected.get("must_cite", [])
    uncovered = [m for m in must_cite if not any(covers(r, canonical_ref(m)) for r in refs)]
    metrics.append(
        Metric(
            "must_cite",
            _fraction(len(must_cite) - len(uncovered), len(must_cite)),
            ", ".join(uncovered),
        )
    )

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

    must_ask = expected.get("must_ask", [])
    if clarification is None and must_ask:
        metrics.append(Metric("must_ask", None, "no clarification given"))
    else:
        asked = {q.get("fact_key") for q in (clarification or {}).get("questions", [])}
        unasked = [m for m in must_ask if m not in asked]
        metrics.append(
            Metric(
                "must_ask",
                _fraction(len(must_ask) - len(unasked), len(must_ask)),
                ", ".join(unasked),
            )
        )

    text = normalize(" ".join(strings(answer, QUOTED_KEYS)))
    found = [m for m in expected.get("must_not", []) if normalize(m) in text]
    must_not = expected.get("must_not", [])
    metrics.append(
        Metric("must_not", _fraction(len(must_not) - len(found), len(must_not)), ", ".join(found))
    )

    progressive = progressive_forms(strings(answer, NOT_SCANNED_FOR_MODE))
    metrics.append(Metric("formal_mode", float(not progressive), ", ".join(progressive)))

    metrics.append(Metric("disclaimer", float(answer.get("disclaimer") == DISCLAIMER)))
    return metrics


def total(metrics: list[Metric]) -> float:
    measured = [m.value for m in metrics if m.value is not None]
    return sum(measured) / len(measured) if measured else 0.0


def load_case(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
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
