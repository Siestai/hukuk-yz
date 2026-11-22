import json
import os
import tomllib
from pathlib import Path
from typing import Any

import pytest

from hukuk_ingest.admin_acts.run import PARSER_VERSION, build_record, discover
from hukuk_ingest.cli import main
from hukuk_ingest.quality import PAGE_BREAK

ACTS = "Mevzuat/Genelge"
LINE = "Bu satır sayfanın metin katmanı olduğunu göstermeye yetecek kadar uzun bir açıklamadır."
TEXT = PAGE_BREAK.join(
    [
        "Sayı : 51-010.06.02-E.1 01/04/2020\nKonu : İdari Para Cezası Genelgesi\n"
        "1-GENEL AÇIKLAMALAR.......2\n2-DİĞER HUSUSLAR ........2",
        f"GENELGE\n2020/8\n1- GENEL AÇIKLAMALAR\nCezalar açıklanmıştır.\n{LINE}\n"
        "1.1- (Mülga: 09/04/2026 tarihli ve 2026/9 sayılı Genelge)\n"
        "1.2- Bildirim süresi\n(Değişik, 17/09/2021 tarihli ve 2021/32 sayılı Genelge) On gündür.\n"
        "2-DİĞER HUSUSLAR\nBu genelgeye göre işlem yapılır.\n"
        "Bilgi edinilmesini ve gereğini rica ederim.",
    ]
)


def _row(name: str, **overrides: Any) -> dict[str, Any]:
    return {
        "path": f"{ACTS}/{name}",
        "sha256": "a8" * 32,
        "size": 4096,
        "detected_type": "pdf",
        "status": "ok",
        "warnings": [],
        "text_ref": "a8/act.raw.txt",
        **overrides,
    }


def _setup(tmp_path: Path, rows: list[dict[str, Any]]) -> tuple[Path, Path]:
    cache = tmp_path / "cache"
    (cache / "a8").mkdir(parents=True)
    (cache / "a8" / "act.raw.txt").write_text(TEXT, encoding="utf-8")
    report = tmp_path / "files.jsonl"
    report.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return report, cache


def test_discover_keeps_the_current_files_of_the_genelges_in_scope(tmp_path: Path) -> None:
    report, _ = _setup(
        tmp_path,
        [
            _row("2020-08 Genelge İdari Para Cezaları.pdf"),
            _row("2018_38 GENELGE  EMEKLİLİK İŞLEMLERİ.pdf"),
            _row("2020-20 Başka Genelge.pdf"),
            _row("Eskiler/2020-08 Genelge İdari Para Cezaları.pdf"),
            {**_row("x"), "path": "Mevzuat/Kanunlar/2020-08 değil.pdf"},
        ],
    )

    assert [(r["ref"], r["path"]) for r in discover(report)] == [
        ("2018/38", f"{ACTS}/2018_38 GENELGE  EMEKLİLİK İŞLEMLERİ.pdf"),
        ("2020/8", f"{ACTS}/2020-08 Genelge İdari Para Cezaları.pdf"),
    ]


def test_a_record_carries_the_dates_the_document_states() -> None:
    record = build_record({**_row("2020-08 Genelge.pdf"), "ref": "2020/8"}, TEXT)

    assert (record["ref"], record["status"], record["parser_version"]) == (
        "2020/8",
        "ok",
        PARSER_VERSION,
    )
    assert (record["issuer"], record["kind"], record["subject"], record["date"]) == (
        "other",
        "genelge",
        "İdari Para Cezası Genelgesi",
        "2020-04-01",
    )
    assert record["latest_snapshot_date"] == "2026-04-09"  # the newest amendment note
    assert record["file"] == {
        "path": f"{ACTS}/2020-08 Genelge.pdf",
        "sha256": "a8" * 32,
        "size": 4096,
        "detected_type": "pdf",
    }
    by_no = {s["section_no"]: s for s in record["sections"]}
    assert list(by_no) == ["1", "1.1", "1.2", "2"]
    # untouched since the genelge was issued
    assert by_no["1"]["versions"] == [
        {
            "text": f"1- GENEL AÇIKLAMALAR\nCezalar açıklanmıştır.\n{LINE}",
            "heading": "GENEL AÇIKLAMALAR",
            "valid_from": "2020-04-01",
            "valid_to": None,
            "change_kind": "original",
            "amendments": [],
        }
    ]
    assert (by_no["1"]["gaps"], by_no["1"]["warnings"], by_no["1"]["confidence"]) == (
        [],
        [],
        "high",
    )
    assert by_no["1"]["children"] == ["1.1", "1.2"]
    # amended in place: the wording on file holds from the note on, the time before is a gap
    amended = by_no["1.2"]
    assert amended["versions"][0]["valid_from"] == "2021-09-17"
    assert amended["versions"][0]["change_kind"] == "amended"
    assert amended["versions"][0]["amendments"] == [
        {"kind": "amended", "date": "2021-09-17", "ref": "2021/32"}
    ]
    assert amended["gaps"] == [
        {"from": "2020-04-01", "to": "2021-09-17", "reason": "amended_in_place"}
    ]
    assert (amended["warnings"], amended["confidence"]) == (["amended_in_place"], "medium")
    assert by_no["1.1"]["versions"][0]["change_kind"] == "repealed"
    assert by_no["1.1"]["versions"][0]["valid_from"] == "2026-04-09"


def test_a_missing_date_and_ocr_text_lower_the_band() -> None:
    undated = TEXT.replace("Sayı : 51-010.06.02-E.1 01/04/2020\n", "")
    row = {**_row("2020-08 Genelge.pdf", warnings=["ocr"]), "ref": "2020/8"}

    record = build_record(row, undated)

    first = record["sections"][0]
    assert (record["date"], record["ocr"]) == (None, True)
    assert first["versions"][0]["valid_from"] is None
    assert first["warnings"] == ["issue_date_unknown", "ocr_text"]
    assert first["confidence"] == "low"


def test_a_file_without_usable_text_gives_no_sections() -> None:
    row = {**_row("2020-08 Genelge.pdf", status="needs_ocr", text_ref=None), "ref": "2020/8"}

    record = build_record(row, None)

    assert (record["status"], record["sections"]) == ("needs_ocr", [])


def test_a_file_that_names_another_genelge_is_not_split() -> None:
    record = build_record({**_row("2018_38 GENELGE.pdf"), "ref": "2018/38"}, TEXT)

    assert (record["status"], record["document_ref"], record["sections"]) == (
        "ref_mismatch",
        "2020/8",
        [],
    )


def test_cli_writes_the_records_and_reports_each_genelge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report, cache = _setup(
        tmp_path,
        [
            _row("2020-08 Genelge.pdf"),
            _row("2018_38 GENELGE.pdf", status="needs_ocr", text_ref=None, sha256="b9" * 32),
        ],
    )
    out = tmp_path / "out"

    code = main(
        ["admin-acts", "--scan-report", str(report), "--text-cache", str(cache), "--out", str(out)]
    )

    records = [
        json.loads(line)
        for line in (out / "admin-acts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [(r["ref"], r["status"], len(r["sections"])) for r in records] == [
        ("2018/38", "needs_ocr", 0),
        ("2020/8", "ok", 4),
    ]
    printed = capsys.readouterr().out
    assert "2018/38: needs_ocr, no sections" in printed
    assert "2020/8: 4 sections, bands {'high': 2, 'medium': 2, 'low': 0}" in printed
    assert "pages without text (needs_ocr) []" in printed
    assert code == 1  # a genelge without sections is not done


def test_cli_names_the_genelge_the_scan_report_lacks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report, cache = _setup(tmp_path, [_row("2020-08 Genelge.pdf")])

    code = main(
        [
            "admin-acts",
            "--scan-report",
            str(report),
            "--text-cache",
            str(cache),
            "--out",
            str(tmp_path / "out"),
        ]
    )

    assert "not in the scan report: 2018/38" in capsys.readouterr().out
    assert code == 1


# --- golden set against the real files ---------------------------------------------------------

RAW = Path(os.environ.get("HUKUK_RAW_DIR", Path(__file__).parents[3] / "data" / "drive"))
GOLDEN = Path(__file__).parent / "fixtures" / "admin_acts" / "golden.toml"


@pytest.mark.skipif(not (RAW / ACTS).is_dir(), reason="needs the raw corpus (data/drive)")
def test_golden_sections_of_the_real_genelges(tmp_path: Path) -> None:
    """Scan the files as `hukuk-ingest scan` does (text layer only), split them, and compare the
    section count and the golden section texts line by line."""
    root, scan_out = tmp_path / "raw", tmp_path / "scan"
    cache, out = tmp_path / "cache", tmp_path / "out"
    (root / ACTS).mkdir(parents=True)
    for path in (RAW / ACTS).iterdir():
        if path.name.startswith(("2018_38", "2020-08")):
            (root / ACTS / path.name).symlink_to(path)
    assert main(["scan", str(root), "--out", str(scan_out), "--text-cache", str(cache)]) == 0
    report = scan_out / "files.jsonl"

    code = main(
        ["admin-acts", "--scan-report", str(report), "--text-cache", str(cache), "--out", str(out)]
    )

    assert code == 0
    records = {
        r["ref"]: r
        for r in map(
            json.loads, (out / "admin-acts.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    for act in tomllib.loads(GOLDEN.read_text(encoding="utf-8"))["act"]:
        record = records[act["ref"]]
        assert record["date"] == act["date"]
        assert len(record["sections"]) == act["sections"]
        assert record["toc_unmatched"] == []
        assert record["pages_without_text"] == []
        texts = {s["section_no"]: s["versions"][0]["text"] for s in record["sections"]}
        for section in act["section"]:
            assert texts[section["no"]] == section["text"], f"{act['ref']} m.{section['no']}"
