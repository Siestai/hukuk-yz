import hashlib
import json
import os
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from hukuk_ingest.detect import detect_type
from hukuk_ingest.extract import extract
from hukuk_ingest.statutes.acts import DEFAULT_ACTS, Registry, load_acts, parse_acts
from hukuk_ingest.statutes.run import SnapshotFile, _file_date, build_records
from hukuk_ingest.statutes.timeline import as_of, find_overlaps, statute_as_of

ACTS = """
[[act]]
law = "9001"
kabul_tarihi = 2003-05-22
yururluk = 2003-06-10
source_url = "https://example.test/9001"

[[act]]
law = "7000"
kabul_tarihi = 2010-03-01
yururluk = 2010-03-10
source_url = "https://example.test/7000"

[[act]]
law = "7001"
kabul_tarihi = 2017-03-01
yururluk = 2017-03-10
source_url = "https://example.test/7001"

[[act]]
law = "7002"
kabul_tarihi = 2019-05-01
yururluk = 2019-06-01
source_url = "https://example.test/7002"

[[act.exception]]
statute = "9001"
article = "Ek 1"
scope = "tüm madde"
yururluk = 2019-09-01
source = "dipnot"

[[act]]
law = "7003"
kabul_tarihi = 2019-06-01
yururluk = 2019-07-01
source_url = "https://example.test/7003"

[[act]]
law = "7004"
kabul_tarihi = 2018-06-01
"""
S0, S1, S2 = date(2016, 1, 1), date(2018, 1, 1), date(2020, 1, 1)


def registry() -> Registry:
    return parse_acts(tomllib.loads(ACTS))


def snapshot_text(articles: dict[str, str]) -> str:
    head = "Kanun Numarası : 9001\nKabul Tarihi : 22/5/2003\n"
    head += "Yayımlandığı Resmî Gazete : Tarih: 10/6/2003 Sayı: 25134\n"
    lines = []
    for no, text in articles.items():
        label = no.replace("Ek ", "Ek Madde ").replace("Geçici ", "Geçici Madde ")
        lines.append(f"{label if ' ' in no else f'Madde {no}'} - {text}")
    return head + "\n".join(lines) + "\n"


def build(*snapshots: tuple[date | None, dict[str, str]]) -> dict[str, dict[str, Any]]:
    files = [
        SnapshotFile(f"Mevzuat/Kanunlar/9001 {i}.pdf", f"{i:064x}", d, snapshot_text(arts))
        for i, (d, arts) in enumerate(snapshots)
    ]
    records, _ = build_records(files, registry())
    assert len(records) == 1
    return {a["article_no"]: a for a in records[0]["articles"]}


def spans(art: dict[str, Any]) -> list[tuple[str | None, str | None]]:
    return [(v["valid_from"], v["valid_to"]) for v in art["versions"]]


def gaps(art: dict[str, Any]) -> list[tuple[str | None, str, str]]:
    return [(g["from"], g["to"], g["reason"]) for g in art["gaps"]]


def test_unchanged_article_runs_from_the_statute_start_with_high_confidence() -> None:
    arts = build(
        (S0, {"1": "Aynı metin."}), (S1, {"1": "Aynı  metin."}), (S2, {"1": "Aynı metin."})
    )
    art = arts["1"]
    assert spans(art) == [("2003-06-10", None)]
    assert art["gaps"] == [] and art["confidence"] == "high"
    assert art["versions"][0]["change_kind"] == "original"
    assert len(art["versions"][0]["evidence"]["snapshots"]) == 3


def test_single_amendment_splits_at_the_in_force_date_of_the_act() -> None:
    old = "(Değişik: 1/3/2010-7000/1 md.) Eski metin burada duruyor."
    new = "(Değişik: 1/3/2010-7000/1 md.) (Değişik: 1/3/2017-7001/5 md.) Yepyeni ve farklı metin."
    art = build((S0, {"1": "A.", "2": old}), (S1, {"1": "A.", "2": new}))["2"]
    assert spans(art) == [("2010-03-10", "2017-03-10"), ("2017-03-10", None)]
    assert art["versions"][1]["amending_ref"] == [
        {"law": "7001", "date": "2017-03-01", "kind": "degisik", "scope": ""}
    ]
    assert art["versions"][1]["change_kind"] == "amended"
    # before the earliest snapshot only the original in-force date is known
    assert gaps(art) == [("2003-06-10", "2010-03-10", "before_earliest_snapshot")]
    assert art["gaps"][0]["known_amendments"][0]["law"] == "7000"
    assert art["confidence"] == "medium"


def test_two_amendments_in_one_window_leave_a_gap_between_their_in_force_dates() -> None:
    old = "Eski metin burada duruyor."
    new = "(Değişik: 1/5/2019-7002/1 md.; Değişik: 1/6/2019-7003/2 md.) Yepyeni ve farklı metin."
    art = build((S1, {"3": old}), (S2, {"3": new}))["3"]
    assert spans(art) == [("2003-06-10", "2019-06-01"), ("2019-07-01", None)]
    assert gaps(art) == [("2019-06-01", "2019-07-01", "multi_amendment_in_window")]
    assert art["confidence"] == "low"
    assert as_of(art, "2019-06-15")["status"] == "gap"
    assert as_of(art, "2019-06-15")["gap"]["known_amendments"][1]["law"] == "7003"
    assert "version" not in as_of(art, "2019-06-15")


def test_footnote_only_amendment_in_the_window_widens_the_gap() -> None:
    new = "(Değişik: 1/5/2019-7002/1 md.) Yepyeni ve farklı metin.(1)"
    note = "\n––––––––––\n(1) 1/6/2019 tarihli ve 7003 sayılı Kanunun 2 nci maddesiyle değişti.\n"
    art = build((S1, {"3": "Eski metin burada duruyor."}), (S2, {"3": new + note}))["3"]
    assert spans(art) == [("2003-06-10", "2019-06-01"), ("2019-07-01", None)]
    assert gaps(art) == [("2019-06-01", "2019-07-01", "multi_amendment_in_window")]
    assert as_of(art, "2019-06-15")["status"] == "gap"
    unregistered = note.replace("7003", "7999")
    art = build((S1, {"3": "Eski metin burada duruyor."}), (S2, {"3": new + unregistered}))["3"]
    assert gaps(art) == [("2018-01-02", "2020-01-01", "multi_amendment_in_window")]
    assert as_of(art, "2019-06-15")["status"] == "gap"


def test_change_without_a_note_is_a_gap_and_low() -> None:
    art = build(
        (S1, {"4": "Eski metin burada duruyor."}), (S2, {"4": "Yepyeni ve farklı metin yazıldı."})
    )["4"]
    assert spans(art) == [("2003-06-10", "2018-01-02"), ("2020-01-01", None)]
    assert gaps(art) == [("2018-01-02", "2020-01-01", "unexplained_change")]
    assert art["confidence"] == "low"
    # a version evidenced only by a snapshot is valid on the snapshot date, the day after is a gap
    assert as_of(art, S1)["status"] == "found"
    assert as_of(art, "2018-01-02")["status"] == "gap"
    assert as_of(art, S2)["status"] == "found"


def test_unknown_in_force_date_falls_back_to_the_snapshot_dates() -> None:
    new = "(Değişik: 1/6/2018-7004/1 md.) Yepyeni ve farklı metin yazıldı."
    art = build((S0, {"5": "Eski metin burada duruyor."}), (S2, {"5": new}))["5"]
    assert spans(art)[0][1] == "2016-01-02" and spans(art)[1][0] == "2020-01-01"
    assert art["versions"][1]["warnings"] == ["yururluk_unknown"]
    assert art["confidence"] == "low"
    unregistered = "(Değişik: 1/6/2018-7999/1 md.) Yepyeni ve farklı metin yazıldı."
    art = build((S0, {"5": "Eski metin burada duruyor."}), (S2, {"5": unregistered}))["5"]
    assert "yururluk_unknown" in art["warnings"]


def test_article_exception_overrides_the_act_date_and_is_medium() -> None:
    new = "(Ek: 1/5/2019-7002/3 md.) Ek madde metni burada."
    art = build((S1, {"1": "Madde."}), (S2, {"1": "Madde.", "Ek 1": new}))["Ek 1"]
    assert spans(art) == [("2019-09-01", None)]
    assert art["versions"][0]["change_kind"] == "added"
    assert art["confidence"] == "medium"
    assert as_of(art, "2019-08-31")["status"] == "not_in_force"
    assert as_of(art, "2019-09-01")["status"] == "found"


def test_removed_article_ends_with_a_gap_and_is_not_in_force_afterwards() -> None:
    art = build((S0, {"1": "Kalır.", "6": "Kalkacak madde."}), (S2, {"1": "Kalır."}))["6"]
    assert spans(art) == [("2003-06-10", "2016-01-02")]
    assert gaps(art) == [("2016-01-02", "2020-01-01", "removed_unexplained")]
    assert as_of(art, "2021-01-01")["status"] == "not_in_force"
    assert art["confidence"] == "low"


def test_extra_article_without_a_note_is_unverified_before_the_first_snapshot() -> None:
    art = build((S0, {"1": "Kalır.", "Geçici 1": "Geçici madde metni."}))["Geçici 1"]
    assert spans(art) == [("2016-01-01", None)]
    assert gaps(art) == [("2003-06-10", "2016-01-01", "before_earliest_snapshot")]
    assert "start_unverified" in art["warnings"]
    assert art["confidence"] == "medium"


def test_repealed_article_is_not_in_force_but_returns_the_stub() -> None:
    arts = build((S0, {"1": "Kalır.", "7": "(Mülga: 1/3/2010-7000/1 md.)"}))
    assert arts["7"]["status"] == "repealed"
    result = as_of(arts["7"], "2012-01-01")
    assert result["status"] == "not_in_force" and result["reason"] == "repealed"
    assert result["version"]["text"] == "(Mülga: 1/3/2010-7000/1 md.)"
    assert as_of(arts["7"], "2005-01-01")["status"] == "gap"


def test_repealed_stub_after_other_notes_is_not_in_force_even_with_retained_text() -> None:
    arts = build(
        (
            S0,
            {
                "1": "Kalır.",
                "7": "(Ek: 1/3/2010-7000/1 md.) (Mülga: 1/3/2017-7001/5 md.)",
                "8": "(Ek: 1/3/2010-7000/1 md.) (Mülga:1/3/2017-7001/5 md.) Eski metin kalmış.",
            },
        )
    )
    for no in ("7", "8"):
        assert arts[no]["status"] == "repealed"
        assert as_of(arts[no], "2018-01-01")["status"] == "not_in_force"
    assert "repealed_text_retained" in arts["8"]["versions"][0]["warnings"] or (
        "repealed_text_retained" in arts["8"]["warnings"]
    )


def test_cosmetic_difference_is_one_version_with_uncertain_diff() -> None:
    arts = build((S0, {"1": "Malûl sayılır, işçi."}), (S2, {"1": "Malul sayılır işçi."}))
    assert len(arts["1"]["versions"]) == 1 and arts["1"]["confidence"] == "medium"


def test_undated_snapshot_takes_the_latest_note_date() -> None:
    new = "(Değişik: 1/5/2019-7002/1 md.) Yepyeni ve farklı metin yazıldı."
    files = [
        SnapshotFile(
            "Mevzuat/Kanunlar/9001 a.pdf", "a" * 64, S0, snapshot_text({"1": "Eski metin."})
        ),
        SnapshotFile("Mevzuat/Kanunlar/9001 b.pdf", "b" * 64, None, snapshot_text({"1": new})),
    ]
    records, _ = build_records(files, registry())
    snaps = records[0]["snapshots"]
    assert (snaps[1]["date"], snaps[1]["date_inferred"]) == ("2019-05-01", True)
    assert "snapshot_date_inferred" in snaps[1]["warnings"]
    # the act is in force after the inferred (lower-bound) date: still explained
    art = records[0]["articles"][0]
    assert spans(art) == [("2003-06-10", "2019-06-01"), ("2019-06-01", None)]


def test_periods_never_overlap_and_as_of_is_consistent() -> None:
    arts = build(
        (
            S0,
            {"1": "A.", "2": "(Değişik: 1/3/2010-7000/1 md.) B eski metin.", "3": "C.", "4": "D."},
        ),
        (
            S1,
            {
                "1": "A.",
                "2": "(Değişik: 1/3/2017-7001/5 md.) B yeni metin.",
                "3": "C.",
                "4": "D değişti metin.",
            },
        ),
        (
            S2,
            {
                "1": "A.",
                "2": "(Değişik: 1/5/2019-7002/1 md.) B yine yeni metin.",
                "3": "C.",
                "4": "D.",
            },
        ),
    )
    for art in arts.values():
        assert find_overlaps(art) == []
        for day in (
            date(2001, 1, 1),
            date(2010, 3, 10),
            S0,
            S1,
            date(2019, 6, 1),
            S2,
            date(2030, 1, 1),
        ):
            result = as_of(art, day)
            hits = [
                v
                for v in art["versions"]
                if v["valid_from"] <= day.isoformat()
                and (v["valid_to"] is None or day.isoformat() < v["valid_to"])
            ]
            assert (result["status"] == "found") == (
                len(hits) == 1 and hits[0]["change_kind"] != "repealed"
            )


def test_find_overlaps_detects_intersections() -> None:
    bad = {
        "versions": [{"valid_from": "2010-01-01", "valid_to": "2012-01-01"}],
        "gaps": [{"from": "2011-01-01", "to": "2013-01-01"}],
    }
    assert len(find_overlaps(bad)) == 1


def test_statute_as_of_reports_unknown_articles() -> None:
    record = {"articles": [{"article_no": "1", "versions": [], "gaps": []}]}
    assert statute_as_of(record, "99", "2020-01-01") == {"status": "unknown_article"}
    assert statute_as_of(record, "1", "2020-01-01") == {"status": "not_in_force"}


def test_open_start_gap_covers_everything_before_its_end() -> None:
    art = {
        "versions": [{"valid_from": "2016-01-01", "valid_to": None, "change_kind": "original"}],
        "gaps": [{"from": None, "to": "2016-01-01", "reason": "before_earliest_snapshot"}],
    }
    assert as_of(art, date(1990, 1, 1))["status"] == "gap"


def test_file_date_comes_from_the_name() -> None:
    assert _file_date("Eskiler/5510 tarih 04.10.2017.pdf") == date(2017, 10, 4)
    assert _file_date("1.5.5510 (27.09.2016).doc") == date(2016, 9, 27)
    assert _file_date("4857 sayılı İş Kanunu 13.05.2016 .docx") == date(2016, 5, 13)
    assert _file_date("4857 sayılı İş Kanunu.pdf") is None


# --- golden set against the real snapshots -----------------------------------------------------

RAW = Path(os.environ.get("HUKUK_RAW_DIR", Path(__file__).parents[3] / "data" / "drive"))
GOLDEN = Path(__file__).parent / "fixtures" / "statutes" / "golden.toml"


def _real_files(raw: Path) -> list[SnapshotFile]:
    by_sha: dict[str, SnapshotFile] = {}
    for path in sorted((raw / "Mevzuat" / "Kanunlar").rglob("*")):
        if not path.is_file() or not any(n in path.name for n in ("4857", "5510")):
            continue
        out = extract(path, detect_type(path))
        if out.status != "ok" or not out.text:
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha not in by_sha:
            rel = path.relative_to(raw).as_posix()
            by_sha[sha] = SnapshotFile(rel, sha, _file_date(rel), out.text)
    return list(by_sha.values())


def _flat(text: str) -> str:
    return " ".join(text.split())


@pytest.mark.skipif(
    not (RAW / "Mevzuat" / "Kanunlar").is_dir() or not GOLDEN.is_file(),
    reason="needs the raw corpus (data/drive) and tests/fixtures/statutes/golden.toml",
)
def test_golden_queries_against_the_real_snapshots() -> None:
    records, _ = build_records(_real_files(RAW), load_acts(DEFAULT_ACTS))
    by_number = {r["number"]: r for r in records}
    queries = tomllib.loads(GOLDEN.read_text(encoding="utf-8"))["query"]
    failures = []
    for q in queries:
        record = by_number.get(q["statute"])
        result: dict[str, Any] = (
            statute_as_of(record, q["article"], q["as_of"])
            if record
            else {"status": "unknown_article"}
        )
        label = f"{q['statute']} m.{q['article']} @ {q['as_of']}"
        if result["status"] != q["expect"]:
            failures.append(f"{label}: expected {q['expect']}, got {result['status']}")
            continue
        text = _flat(result.get("version", {}).get("text", ""))
        if q["expect"] == "found" and "contains" in q and _flat(q["contains"]) not in text:
            failures.append(f"{label}: missing {q['contains']!r}")
        if "not_contains" in q and _flat(q["not_contains"]) in text:
            failures.append(f"{label}: unexpected {q['not_contains']!r}")
    assert not failures, json.dumps(failures, ensure_ascii=False, indent=2)
