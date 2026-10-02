import json
import os
from pathlib import Path
from typing import Any

import pytest

from hukuk_ingest import cli
from hukuk_ingest.cli import main, scan
from hukuk_ingest.pipeline import FileResult, process_file

DRIVE = Path(__file__).resolve().parents[3] / "data" / "drive"
needs_drive = pytest.mark.skipif(not DRIVE.is_dir(), reason="data/drive not available")


def _run(
    root: Path, tmp_path: Path, *extra: str, workers: int = 2, code: int = 1
) -> list[dict[str, Any]]:
    """Run `scan` into tmp_path/report with a tmp_path/cache text cache; return files.jsonl rows."""
    out = tmp_path / "report"
    argv = ["scan", str(root), "--out", str(out), "--text-cache", str(tmp_path / "cache")]
    assert main([*argv, "--workers", str(workers), *extra]) == code
    return [json.loads(line) for line in (out / "files.jsonl").read_text("utf-8").splitlines()]


def test_scan_reports_type_status_and_reason_per_file(corpus: Path, tmp_path: Path) -> None:
    rows = {r["path"]: r for r in _run(corpus, tmp_path)}
    got = {p: (r["detected_type"], r["status"], r["reason"]) for p, r in rows.items()}
    assert got == {
        "text.pdf": ("pdf", "ok", None),
        "scan.pdf": ("pdf", "needs_ocr", "no_text_layer"),
        "a.docx": ("docx", "ok", None),
        "b.udf": ("udf", "ok", None),
        "sheet.xlsx": ("xlsx_xlsm", "skipped", "type_xlsx_xlsm"),
        "legacy.pdf": ("doc", "unsupported", "legacy_doc"),
        "stub.pdf": ("html", "rejected", "html_stub"),
        "pic.jpg": ("image", "needs_ocr", "image"),
        "note.txt": ("text", "ok", None),
        "Thumbs.db": ("unknown", "skipped", "type_unknown"),
        "broken.pdf": ("pdf", "error", "exception"),
    }
    assert rows["legacy.pdf"]["extension_mismatch"] is True
    assert rows["b.udf"]["signed"] is True
    assert rows["broken.pdf"]["error"]


def test_scan_writes_clean_text_to_cache(corpus: Path, tmp_path: Path) -> None:
    rows = {r["path"]: r for r in _run(corpus, tmp_path)}
    ref = Path(rows["text.pdf"]["text_ref"])
    clean = (tmp_path / "cache" / ref.with_suffix("").with_suffix(".clean.txt")).read_text("utf-8")
    assert "İşçinin kıdem" in clean
    assert "\r" not in clean


def test_scan_writes_summary_with_counts_and_errors(corpus: Path, tmp_path: Path) -> None:
    _run(corpus, tmp_path, workers=1)
    out = tmp_path / "report"
    summary = json.loads((out / "summary.json").read_text("utf-8"))
    assert summary["files"] == 11
    assert [e["path"] for e in summary["errors"]] == ["broken.pdf"]
    assert summary["type_status"]["pdf"] == {"ok": 1, "needs_ocr": 1, "error": 1}
    assert "Type x status" in (out / "summary.md").read_text(encoding="utf-8")


def test_scan_second_run_uses_cache_and_force_bypasses(corpus: Path, tmp_path: Path) -> None:
    assert not any(r["cached"] for r in _run(corpus, tmp_path))
    second = _run(corpus, tmp_path)
    assert {r["path"] for r in second if not r["cached"]} == {"broken.pdf"}  # errors are retried
    assert not any(r["cached"] for r in _run(corpus, tmp_path, "--force"))


def test_scan_exits_zero_without_errors(tmp_path: Path) -> None:
    root = tmp_path / "c"
    root.mkdir()
    (root / "a.txt").write_text("işçi ve işveren", encoding="utf-8")
    _run(root, tmp_path, workers=1, code=0)


def test_scan_skips_text_cache_inside_scanned_dir(tmp_path: Path) -> None:
    root = tmp_path / "c"
    root.mkdir()
    (root / "a.txt").write_text("işçi ve işveren", encoding="utf-8")
    argv = ["scan", str(root), "--out", str(tmp_path / "o"), "--text-cache", str(root / ".cache")]
    main(argv)
    main(argv)
    rows = (tmp_path / "o" / "files.jsonl").read_text("utf-8").splitlines()
    assert [json.loads(r)["path"] for r in rows] == ["a.txt"]


def _crash_on_marked_file(path: Path, root: Path, cache_dir: Path, force: bool) -> FileResult:
    if path.name.startswith("crash"):
        os._exit(13)  # simulates a pdfium segfault / OOM kill
    return process_file(path, root, cache_dir, force)


def test_scan_worker_crash_is_pinned_on_its_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "c"
    root.mkdir()
    for i in range(6):
        (root / f"ok{i}.txt").write_text("işçi ve işveren " * 5, encoding="utf-8")
    (root / "crash.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(cli, "process_file", _crash_on_marked_file)
    results, summary = scan(root, tmp_path / "out", tmp_path / "cache", workers=2, force=False)
    by_path = {r.path: r for r in results}
    assert (by_path["crash.txt"].status, by_path["crash.txt"].reason) == ("error", "worker_crash")
    assert all(by_path[f"ok{i}.txt"].status == "ok" for i in range(6))
    assert len(summary["errors"]) == 1


def test_main_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["scan", str(tmp_path / "missing"), "--out", str(tmp_path / "o")])
    assert exc.value.code == 2


def test_main_rejects_zero_workers(corpus: Path, tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["scan", str(corpus), "--out", str(tmp_path / "o"), "--workers", "0"])
    assert exc.value.code == 2


@needs_drive
def test_scan_real_decision_sample_is_extracted(tmp_path: Path) -> None:
    picked = sorted((DRIVE / "Yargi_Kararlari_Arsivi").rglob("*.pdf"))[::400][:12]
    sample = tmp_path / "sample"
    sample.mkdir()
    for i, p in enumerate(picked):
        os.symlink(p, sample / f"{i}.pdf")  # symlinks: nothing from the corpus is copied
    rows = _run(sample, tmp_path, code=0)
    assert len(rows) == len(picked)
    assert all(r["status"] in {"ok", "rejected", "unsupported"} for r in rows)


@needs_drive
def test_scan_real_mevzuat_scans_and_images_need_ocr(tmp_path: Path) -> None:
    wanted = {
        "Diğer mevzuat/e defter ibraz zorunluluğu.jpg": "image",
        "Diğer mevzuat/Yabancı Uyruklu çalışanlar.pdf": "no_text_layer",
        "Genelge/2021-38 Genelge Elektronik Tebligat işlemleri.pdf": "partial_text_layer",
    }
    sample = tmp_path / "sample"
    sample.mkdir()
    for i, rel in enumerate(wanted):
        os.symlink(DRIVE / "Mevzuat" / rel, sample / f"{i}{Path(rel).suffix}")
    rows = _run(sample, tmp_path, code=0)
    assert sorted(r["reason"] for r in rows) == sorted(wanted.values())
    assert all(r["status"] == "needs_ocr" for r in rows)
