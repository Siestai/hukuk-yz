import json
from pathlib import Path
from typing import Any

import pytest
from statute_texts import numbered_style, rule_style
from word_doc import make_doc

from hukuk_ingest.cli import main
from hukuk_ingest.statutes.run import discover

STATUTES = "Mevzuat/Kanunlar"
ACTS = """
[[act]]
law = "9001"
kabul_tarihi = 2003-05-22
yururluk = 2003-06-10
source_url = "https://example.test/9001"

[[act]]
law = "7036"
kabul_tarihi = 2017-10-12
"""


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Scan report + text cache + raw dir: a PDF-style text, a duplicate of it, and a legacy
    `.doc` that the old scan report marked unsupported."""
    cache, raw = tmp_path / "cache", tmp_path / "raw"
    (cache / "aa").mkdir(parents=True)
    (raw / STATUTES / "Eskiler").mkdir(parents=True)
    (cache / "aa" / "one.raw.txt").write_text(rule_style(), encoding="utf-8")
    (cache / "aa" / "two.raw.txt").write_text(numbered_style(), encoding="utf-8")
    doc_text = rule_style().replace("9001", "9004").replace("\n", "\r")
    (raw / STATUTES / "Eskiler" / "5510 tarih 01.02.2016.doc").write_bytes(
        make_doc([(doc_text, False)])
    )
    rows: list[dict[str, Any]] = [
        {
            "path": f"{STATUTES}/4857 sayılı 05.03.2018.pdf",
            "sha256": "a1" * 32,
            "status": "ok",
            "text_ref": "aa/one.raw.txt",
        },
        {
            "path": f"{STATUTES}/Eskiler/4857 sayılı 05.03.2018.pdf",
            "sha256": "a1" * 32,
            "status": "ok",
            "text_ref": "aa/one.raw.txt",
        },
        {
            "path": f"{STATUTES}/5510 tarih 01.01.2020.pdf",
            "sha256": "b2" * 32,
            "status": "ok",
            "text_ref": "aa/two.raw.txt",
        },
        {
            "path": f"{STATUTES}/Eskiler/5510 tarih 01.02.2016.doc",
            "sha256": "c3" * 32,
            "status": "unsupported",
            "reason": "legacy_doc",
            "text_ref": None,
        },
        {
            "path": f"{STATUTES}/5510 scan 01.01.2020.pdf",
            "sha256": "d4" * 32,
            "status": "needs_ocr",
            "text_ref": None,
        },
        {
            "path": "Yargi_Kararlari_Arsivi/4857.pdf",
            "sha256": "e5" * 32,
            "status": "ok",
            "text_ref": "aa/one.raw.txt",
        },
    ]
    report = tmp_path / "files.jsonl"
    report.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    acts = tmp_path / "acts.toml"
    acts.write_text(ACTS, encoding="utf-8")
    return report, cache, raw


def test_discover_merges_duplicates_and_reads_legacy_docs(tmp_path: Path) -> None:
    report, cache, raw = _setup(tmp_path)
    files = discover(report, cache, raw)
    assert [f.path.rsplit("/", 1)[-1] for f in files] == [
        "4857 sayılı 05.03.2018.pdf",  # the copy under Eskiler/ is a duplicate (same sha256)
        "5510 tarih 01.01.2020.pdf",
        "5510 tarih 01.02.2016.doc",
    ]
    assert files[0].duplicates == [f"{STATUTES}/Eskiler/4857 sayılı 05.03.2018.pdf"]
    assert files[2].text.startswith("DENEME KANUNU")
    assert "Kanun Numarası" in files[2].text


def test_cli_writes_jsonl_and_report(tmp_path: Path) -> None:
    report, cache, raw = _setup(tmp_path)
    out = tmp_path / "out"
    code = main(
        [
            "statutes",
            "--scan-report",
            str(report),
            "--text-cache",
            str(cache),
            "--raw-dir",
            str(raw),
            "--acts",
            str(tmp_path / "acts.toml"),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    records = [json.loads(x) for x in (out / "statutes.jsonl").read_text("utf-8").splitlines()]
    assert [r["number"] for r in records] == ["9001", "9002", "9004"]
    nine = records[0]
    assert nine["latest_snapshot_date"] == "2018-03-05"
    assert nine["snapshots"][0]["duplicates"]
    assert [a["article_no"] for a in nine["articles"]][:2] == ["1", "2"]
    for rec in records:
        for art in rec["articles"]:
            assert art["confidence"] in {"high", "medium", "low"}
            assert "––––" not in art["versions"][-1]["text"]
    summary = json.loads((out / "statutes-report.json").read_text("utf-8"))
    assert summary["laws"][0]["overlaps"] == []
    assert summary["act_pairs"]["registry_without_yururluk"] == 1
    missing = summary["act_pairs"]["missing_in_registry"]
    assert ["2008-04-17", "5754"] in missing and ["2017-10-12", "7036"] not in missing
    text = (out / "statutes-report.md").read_text("utf-8")
    assert "Son snapshot tarihi" in text and "2018-03-05" in text


def test_cli_rejects_a_missing_report(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["statutes", "--scan-report", str(tmp_path / "nope.jsonl"), "--out", str(tmp_path)])
