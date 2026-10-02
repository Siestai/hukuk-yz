from pathlib import Path
from typing import Any

from app.loaders.decisions import prepare, read_rows
from app.loaders.report import LoadCounts, build_summary, render_markdown, write_report

FIXTURE = Path(__file__).parent / "fixtures" / "decisions_fixture.jsonl"
BANDS = {"high": 7, "medium": 4, "low": 13}


def _summary() -> dict[str, Any]:
    rows, _, total = read_rows(FIXTURE)
    prepared, repeated = prepare(rows, {})
    counts = LoadCounts(total=total, new=len(prepared), skipped_duplicate_sha256=repeated)
    return build_summary(prepared, counts, 2.04, dry_run=True)


def test_counts_and_bands() -> None:
    s = _summary()
    assert (s["total"], s["new"], s["skipped"], s["errors"]) == (25, 24, 1, 0)
    assert s["bands"] == BANDS
    assert sum(sum(b.values()) for b in s["bands_by_court"].values()) == 24
    assert sum(sum(b.values()) for b in s["bands_by_layout"].values()) == 24
    assert s["bands_by_court"]["(boş)"] == {"high": 0, "medium": 0, "low": 1}


def test_reasons_groups_and_normalization_warnings() -> None:
    s = _summary()
    assert dict(s["top_reasons"])["duplicate_same_text"] == 2
    assert s["top_reasons"] == sorted(s["top_reasons"], key=lambda r: -r[1])
    assert s["duplicate_groups"] == {
        "total": 4,
        "by_dup_kind": {"same_text": 1, "excerpt": 1, "different_text": 1, "date_mismatch": 1},
    }
    assert s["normalization_warnings"]["court_missing"] == 1
    assert s["normalization_warnings"]["duplicate_of"] == 1


def test_report_files_are_written(tmp_path: Path) -> None:
    s = _summary()
    write_report(s, tmp_path / "nested")
    assert (tmp_path / "nested" / "load-summary.json").is_file()
    markdown = (tmp_path / "nested" / "load-summary.md").read_text(encoding="utf-8")
    assert markdown == render_markdown(s)
    assert "## Top 15 reasons" in markdown
