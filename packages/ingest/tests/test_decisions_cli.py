import json
from pathlib import Path
from typing import Any

from conftest import era1_text, era2_text, era3_text, era4_text, foreign_text

from hukuk_ingest.cli import main
from hukuk_ingest.pipeline import cache_base

ARCHIVE = "Yargi_Kararlari_Arsivi"


def _write_report(tmp_path: Path, texts: dict[str, str]) -> tuple[Path, Path]:
    """A task-03 style scan report and text cache holding the given `{path: text}` decisions."""
    cache = tmp_path / "cache"
    rows: list[dict[str, Any]] = []
    for i, (path, text) in enumerate(texts.items()):
        sha = f"{i:02x}" + "ab" * 31
        base = cache_base(cache, sha)
        base.parent.mkdir(parents=True, exist_ok=True)
        base.with_suffix(".clean.txt").write_text(text, encoding="utf-8")
        rows.append({"path": path, "sha256": sha, "status": "ok", "detected_type": "pdf"})
    rows += [
        {"path": f"{ARCHIVE}/9.Sayı-X/stub.pdf", "sha256": "ff" * 32, "status": "rejected"},
        {"path": "Mevzuat/Kanunlar/4857.pdf", "sha256": "ee" * 32, "status": "ok"},
    ]
    report = tmp_path / "files.jsonl"
    report.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return report, cache


def _texts() -> dict[str, str]:
    return {
        f"{ARCHIVE}/1.Sayı-Yargı Kararları (37)/a.pdf": era1_text(),
        f"{ARCHIVE}/20.Sayı-Yargı Kararları (77)/b.pdf": era2_text(),
        f"{ARCHIVE}/45.Sayı-Yargı Kararları (73)/c.pdf": era3_text(),
        f"{ARCHIVE}/80.Sayı-Yargı Kararları (76)/d.pdf": era4_text(),
        f"{ARCHIVE}/10.Sayı-Yargı Kararları (72)/e.pdf": foreign_text(),
    }


def _parse(
    tmp_path: Path, report: Path, cache: Path, *extra: str, code: int = 0
) -> list[dict[str, Any]]:
    out = tmp_path / "out"
    argv = ["decisions", "parse", "--scan-report", str(report), "--text-cache", str(cache)]
    assert main([*argv, "--out", str(out), *extra]) == code
    lines = (out / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_parse_writes_one_row_per_archive_decision(tmp_path: Path) -> None:
    report, cache = _write_report(tmp_path, _texts())
    rows = _parse(tmp_path, report, cache, "--workers", "2")
    assert len(rows) == 5  # the rejected stub and the Mevzuat file are not decisions
    by_layout = {r["layout"]: r for r in rows}
    assert set(by_layout) == {
        "era1_summary_first",
        "era2_classic",
        "era3_two_column",
        "era4_new_template",
        "foreign_article",
    }
    row = by_layout["era2_classic"]
    assert (row["journal_issue"], row["court"], row["chamber"], row["esas_no"]) == (
        20,
        "yargitay",
        "9. HD",
        "2011/12345",
    )
    assert row["verification"] == "unverified"
    assert row["source_path"].startswith(ARCHIVE)


def test_issue_filter_selects_one_issue(tmp_path: Path) -> None:
    report, cache = _write_report(tmp_path, _texts())
    rows = _parse(tmp_path, report, cache, "--workers", "1", "--issue", "80")
    assert [r["journal_issue"] for r in rows] == [80]


def test_summary_files_have_the_requested_sections(tmp_path: Path) -> None:
    report, cache = _write_report(tmp_path, _texts())
    _parse(tmp_path, report, cache, "--workers", "1")
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert summary["decisions"] == 5
    assert summary["fill"]["overall"]["esas_no"] == {"applicable": 4, "filled": 4}  # foreign: n/a
    assert summary["fill"]["by_layout"]["era3_two_column"]["chamber"] == {
        "applicable": 1,
        "filled": 1,
    }
    assert summary["courts"]["Yargıtay daire"] == 4
    assert summary["agents_courts"]["BAM"] == 297
    assert summary["layout_by_issue_range"]["era4_new_template"] == {"76-90": 1}
    assert summary["layout_unknown"] == []
    markdown = (tmp_path / "out" / "summary.md").read_text(encoding="utf-8")
    for heading in ("Layout x issue range", "Field fill", "Courts vs AGENTS.md", "Top 20 warnings"):
        assert heading in markdown


def test_unknown_layout_critical_gaps_and_duplicates_are_listed(tmp_path: Path) -> None:
    texts = _texts()
    texts[f"{ARCHIVE}/21.Sayı-X/dup.pdf"] = era2_text()  # same court/chamber/E/K as b.pdf
    texts[f"{ARCHIVE}/22.Sayı-X/odd.pdf"] = "Etiketsiz bir metin.\nİkinci satır."
    report, cache = _write_report(tmp_path, texts)
    _parse(tmp_path, report, cache, "--workers", "1")
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert len(summary["layout_unknown"]) == 1
    assert [m["missing"] for m in summary["critical_missing"]] == [
        ["court", "esas_no", "karar_no", "decision_date"]
    ]
    (dup,) = summary["duplicate_candidates"]
    assert dup["key"] == ["yargitay", "9. HD", "2011/12345", "2012/6789"]
    assert len(dup["refs"]) == 2


def test_a_failing_file_becomes_an_error_row_and_does_not_stop_the_run(tmp_path: Path) -> None:
    report, cache = _write_report(tmp_path, _texts())
    victim = cache_base(cache, "00" + "ab" * 31).with_suffix(".clean.txt")
    victim.unlink()  # the cached text vanished
    rows = _parse(tmp_path, report, cache, "--workers", "1", code=1)
    assert len(rows) == 5
    (error,) = [r for r in rows if r["status"] == "error"]
    assert "FileNotFoundError" in error["error"]
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert len(summary["errors"]) == 1
