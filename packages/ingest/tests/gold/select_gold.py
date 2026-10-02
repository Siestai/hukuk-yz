"""Seeded selection of the decisions that go into the gold set.

Run on a parser output (`decisions.jsonl`) to list the sha256 values to label by hand:

    uv run python packages/ingest/tests/gold/select_gold.py --decisions <dir>/decisions.jsonl

The parser output is used only to stratify (layout, court) and to over-sample records the parser
was unsure about (warnings, missing fields); the expected values in `decisions_gold.jsonl` are
read from the decision texts, never copied from the parser.
"""

import argparse
import json
import random
from pathlib import Path
from typing import Any

SEED = 20261002
# (stratum name, predicate on a parser record, how many to draw). Strata overlap; a decision
# drawn for one stratum counts for the others it belongs to.
_STRATA: tuple[tuple[str, Any, int], ...] = (
    ("era1_summary_first", lambda r: r["layout"] == "era1_summary_first", 12),
    ("era2_classic", lambda r: r["layout"] == "era2_classic", 12),
    ("era3_two_column", lambda r: r["layout"] == "era3_two_column", 12),
    ("era4_new_template", lambda r: r["layout"] == "era4_new_template", 12),
    ("hgk", lambda r: r["court_level"] == "hgk_iddk" and r["court"] == "yargitay", 6),
    ("bam", lambda r: r["court"] == "bam", 6),
    ("aym", lambda r: r["court"] == "aym", 4),
    ("ibk", lambda r: r["court_level"] == "ibk", 99),  # all of them
    ("danistay", lambda r: r["court"] == "danistay", 2),
    ("foreign", lambda r: r["court"] == "foreign", 3),
    ("abad", lambda r: r["court"] == "abad", 2),
    ("aihm", lambda r: r["court"] == "aihm", 2),
    (
        "hard",
        lambda r: bool(r["warnings"]) or any(m in r["missing"] for m in ("court", "esas_no")),
        10,
    ),
    ("unclassified", lambda r: r["court"] == "", 3),
)


def select(records: list[dict[str, Any]], seed: int = SEED) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    ordered = sorted(records, key=lambda r: r["sha256"])  # input order must not matter
    chosen: dict[str, dict[str, Any]] = {}
    for name, belongs, quota in _STRATA:
        pool = [r for r in ordered if belongs(r)]
        have = sum(1 for r in pool if r["sha256"] in chosen)
        fresh = [r for r in pool if r["sha256"] not in chosen]
        for r in rng.sample(fresh, min(max(quota - have, 0), len(fresh))):
            chosen[r["sha256"]] = {
                "sha256": r["sha256"],
                "stratum": name,
                "issue": r["journal_issue"],
            }
    return sorted(chosen.values(), key=lambda c: c["sha256"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    with args.decisions.open(encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh]
    for c in select([r for r in records if r["status"] == "ok"], args.seed):
        print(json.dumps(c, ensure_ascii=False))


if __name__ == "__main__":
    main()
