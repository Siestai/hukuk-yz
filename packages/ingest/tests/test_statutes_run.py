import json
import tomllib
from pathlib import Path
from typing import Any

import pytest
from statute_texts import numbered_style, rule_style
from word_doc import make_doc

from hukuk_ingest.cli import main
from hukuk_ingest.statutes.acts import DEFAULT_ACTS, load_acts, parse_acts
from hukuk_ingest.statutes.laws import LAWS, law_for_file
from hukuk_ingest.statutes.run import PARSER_VERSION, SnapshotFile, build_records, discover

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
    assert all(r["parser_version"] == PARSER_VERSION for r in records)  # the loader keys on it
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


def test_discover_follows_the_law_registry(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "t.txt").write_text(rule_style(), encoding="utf-8")
    names = [
        "1475 sayılı (mülga) İş Kanunu’nun 14. maddesi.pdf",
        "6356 sayılı SENDİKALAR VE TOPLU İŞ SÖZLEŞMESİ KANUNU.pdf",
        "7036 Sayılı İş Mahkemeleri Kanunu.pdf",
        "4447 sayılı İşsizlik Sigortası Kanunu.pdf",  # not in the registry
        "16356 sayılı.pdf",  # 6356 inside another number
    ]
    rows = [
        {"path": f"{STATUTES}/{n}", "sha256": f"{i:064x}", "status": "ok", "text_ref": "t.txt"}
        for i, n in enumerate(names)
    ]
    report = tmp_path / "files.jsonl"
    report.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    found = [f.path.rsplit("/", 1)[-1] for f in discover(report, cache, tmp_path)]
    assert found == names[:3]
    assert [law.number for law in LAWS] == ["1475", "4857", "5510", "6356", "7036"]
    assert law_for_file(names[0]).only_articles == ("14",)  # type: ignore[union-attr]


def test_every_registered_law_has_its_own_act_with_an_in_force_date() -> None:
    registry = load_acts(DEFAULT_ACTS)
    for law in LAWS:
        act = registry.get(law.number, law.kabul_tarihi)
        assert act is not None and act.yururluk is not None, law.number


REPEALED_LAW = """İŞ KANUNU1
Kanun Numarası : 1475
Kabul Tarihi : 25/8/1971
Yayımlandığı Resmî Gazete : Tarih: 1/9/1971 Sayı: 13943
Madde 1-13/E- (Mülga: 22/5/2003/4857/120 md.)
Kıdem tazminatı:
Madde 14 – (Değişik birinci fıkra: 29/7/1983 - 2869/3 md.) Kıdem tazminatı ödenir.
Kanunla veya Cumhurbaşkanlığı kararnamesiyle kurulu kurumlarda bir fon tesis edilir.
2
Fon tesisi ile ilgili hususlar kanunla düzenlenir.
Madde 15-110- (Mülga: 22/5/2003/4857/120 md.)
Ek Madde 1-4- (Mülga: 22/5/2003/4857/120 md.)
Geçici Madde 1-13- (Mülga: 22/5/2003/4857/120 md.)
Ek Geçici Madde 1-(Mülga: 22/5/2003/4857/120 md.)
Madde 111-112- (Mülga: 22/5/2003/4857/120 md.)
1 22/5/2003 tarihli ve 4857 sayılı Kanunun 120 nci maddesiyle, bu Kanunun 14 üncü maddesi hariç
diğer maddeleri yürürlükten kaldırılmıştır.
2 2/7/2018 tarihli ve 700 sayılı KHK’nin 60 ıncı maddesiyle, bu fıkrada yer alan “kanunla”
ibaresinden sonra gelmek üzere “veya Cumhurbaşkanlığı kararnamesiyle” ibaresi eklenmiştir.
"""
REPEALED_ACTS = """
[[act]]
law = "1475"
kabul_tarihi = 1971-08-25
yururluk = 1971-09-01
source_url = "https://example.test/1475"

[[act]]
law = "2869"
kabul_tarihi = 1983-07-29
yururluk = 1983-07-30
source_url = "https://example.test/2869"

[[act]]
law = "4857"
kabul_tarihi = 2003-05-22
yururluk = 2003-06-10
source_url = "https://example.test/4857"

[[act]]
law = "KHK-700"
kabul_tarihi = 2018-07-02
yururluk = 2018-07-09
source_url = "https://example.test/700"
"""


def test_repealed_law_keeps_only_its_surviving_article() -> None:
    name = "Mevzuat/Kanunlar/1475 sayılı (mülga) İş Kanunu’nun 14. maddesi.pdf"
    files = [SnapshotFile(name, "a" * 64, None, REPEALED_LAW)]
    records, _ = build_records(files, parse_acts(tomllib.loads(REPEALED_ACTS)))
    record = records[0]
    assert (record["number"], record["title"], record["header"]["title"]) == (
        "1475",
        "İŞ KANUNU",  # the registry name, not the parsed "İŞ KANUNU1" (glued footnote marker)
        "İŞ KANUNU",
    )
    assert [a["article_no"] for a in record["articles"]] == ["14"]
    article = record["articles"][0]
    assert article["heading"] == "Kıdem tazminatı:"  # printed after the stub `Madde 1-13/E-`
    text = article["versions"][0]["text"]
    # the footnote marker standing on its own line is no text
    assert text.endswith(
        "bir fon tesis edilir.\nFon tesisi ile ilgili hususlar kanunla düzenlenir."
    )
    # the footnote printed after the stubs at the end still belongs to m.14
    assert [f["no"] for f in article["footnotes"]] == [1, 2]
    # the stubs around m.14 are ranges: its numbering is no splitting doubt
    assert not [w for w in article["warnings"] if w.startswith("number_skipped")]
    assert [v["valid_from"] for v in article["versions"]] == ["2018-07-09"]  # KHK-700 footnote
    assert article["confidence"] == "medium"
    snap = record["snapshots"][0]
    assert snap["articles"] == 1 and "only_articles:14" in snap["warnings"]


def test_footnote_of_a_dropped_article_lowers_the_band() -> None:
    """A real article (not a range stub) outside `only_articles` takes a footnote with it: the
    kept article may be the one it speaks about, so it is not passed as clean."""
    text = REPEALED_LAW.replace(
        "Madde 15-110- (Mülga: 22/5/2003/4857/120 md.)", "Madde 15 - Başka bir madde.3"
    )
    text += "3 2/7/2018 tarihli ve 700 sayılı KHK’nin 60 ıncı maddesiyle ibare eklenmiştir.\n"
    name = "Mevzuat/Kanunlar/1475 sayılı (mülga) İş Kanunu’nun 14. maddesi.pdf"
    records, _ = build_records(
        [SnapshotFile(name, "a" * 64, None, text)], parse_acts(tomllib.loads(REPEALED_ACTS))
    )
    (article,) = records[0]["articles"]
    assert article["article_no"] == "14"
    assert "footnote_on_dropped_article" in article["warnings"]
    assert article["confidence"] == "low"
