from datetime import date

import pytest
from fakes import make_key

from hukuk_verify.matching import (
    bam_region,
    canonical_chamber,
    compare_dates,
    fold,
    match_rows,
    normalize_number,
    source_chamber_match,
)
from hukuk_verify.models import FieldMatch, OfficialRow


def row(
    chamber: str = "9. Hukuk Dairesi",
    esas: str = "2017/17327",
    karar: str = "2020/14291",
    when: date | None = date(2020, 12, 9),
    ref: str = "1",
) -> OfficialRow:
    return OfficialRow(ref, f"https://x/{ref}", chamber, esas, karar, when)


@pytest.mark.parametrize(
    "raw",
    ["9. HD", "9. Hukuk Dairesi", "Yargıtay 9. Hukuk Dairesi", "yargitay 9.hukuk dairesi"],
)
def test_chamber_spellings_are_one_chamber(raw: str) -> None:
    assert canonical_chamber(raw) == "9 HD"


def test_daire_spellings_and_kinds() -> None:
    assert canonical_chamber("10. D") == canonical_chamber("10. Daire") == "10 D"
    assert canonical_chamber("9. CD") == canonical_chamber("9. Ceza Dairesi") == "9 CD"
    assert len({canonical_chamber(c) for c in ("9. HD", "9. CD", "9. D", "19. HD")}) == 4


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hukuk Genel Kurulu", "HGK"),
        ("Yargıtay Hukuk Genel Kurulu", "HGK"),
        ("HGK", "HGK"),
        ("Ceza Genel Kurulu", "CGK"),
        ("Yargıtay Ceza Genel Kurulu", "CGK"),
        ("İçtihadı Birleştirme Büyük Genel Kurulu", "IBK"),
        ("Yargıtay İçtihadı Birleştirme Büyük Genel Kurulu", "IBK"),
        ("İBK", "IBK"),
    ],
)
def test_named_bodies(raw: str, expected: str) -> None:
    assert canonical_chamber(raw) == expected


def test_empty_chamber_is_none() -> None:
    assert canonical_chamber("") is None


def test_bam_chamber_is_region_plus_daire() -> None:
    raw = "İstanbul Bölge Adliye Mahkemesi 35. Hukuk Dairesi"
    assert canonical_chamber(raw) == "35 HD"
    assert bam_region(raw) == "istanbul"
    assert bam_region("Istanbul Bölge Adliye Mahkemesi 1. Hukuk Dairesi") == "istanbul"
    assert bam_region("Yargıtay 9. Hukuk Dairesi") == ""


def test_fold_is_turkish_aware() -> None:
    assert fold("İSTANBUL") == fold("istanbul") == fold("Istanbul") == "istanbul"
    assert fold("  Şırnak,  Çorum. ") == "sirnak corum"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2017/17327", "2017/17327"),
        ("2017 / 017327", "2017/17327"),
        ("2024/10-389", "2024/389"),
        ("2024/10 - 389", "2024/389"),
    ],
)
def test_normalize_number(raw: str, expected: str) -> None:
    assert normalize_number(raw) == expected


def test_dates_exact_within_three_days_beyond() -> None:
    base = date(2020, 12, 9)
    assert compare_dates(base, base) is FieldMatch.match
    assert compare_dates(base, date(2020, 12, 12)) is FieldMatch.fuzzy
    assert compare_dates(base, date(2020, 12, 6)) is FieldMatch.fuzzy
    assert compare_dates(base, date(2020, 12, 13)) is FieldMatch.mismatch
    assert compare_dates(None, base) is FieldMatch.absent
    assert compare_dates(base, None) is FieldMatch.mismatch  # the site's date was unreadable


def test_no_rows_is_not_in_source() -> None:
    decision = match_rows(make_key(), [])
    assert (decision.kind, decision.row) == ("not_in_source", None)


def test_rows_with_another_ek_are_no_candidates() -> None:
    decision = match_rows(make_key(), [row(esas="2017/17328"), row(karar="2020/1")])
    assert decision.kind == "not_in_source"
    assert decision.matched["rows"] == 2


def test_one_matching_row_verifies() -> None:
    decision = match_rows(
        make_key(), [row(chamber="Yargıtay 9. Hukuk Dairesi", esas="2017/017327")]
    )
    assert decision.kind == "verified"
    assert decision.matched["chamber"] == "match"
    assert decision.matched["decision_date"] == "match"
    assert decision.matched["fuzzy"] == []
    assert decision.matched["site"]["decision_date"] == "2020-12-09"


def test_fuzzy_date_still_verifies_and_is_listed() -> None:
    decision = match_rows(make_key(), [row(when=date(2020, 12, 11))])
    assert decision.kind == "verified"
    assert decision.matched["fuzzy"] == ["decision_date"]


def test_date_beyond_three_days_is_a_mismatch() -> None:
    decision = match_rows(make_key(), [row(when=date(2020, 12, 20))])
    assert decision.kind == "mismatch"
    assert decision.row is not None


def test_other_chamber_is_a_mismatch() -> None:
    assert match_rows(make_key(), [row(chamber="22. Hukuk Dairesi")]).kind == "mismatch"
    assert match_rows(make_key(), [row(chamber="")]).kind == "mismatch"


def test_an_unparseable_official_date_is_a_mismatch_not_absent() -> None:
    decision = match_rows(make_key(), [row(when=None)])
    assert decision.kind == "mismatch"
    assert decision.matched["decision_date"] == "mismatch"
    assert decision.matched["official_date_unparseable"] is True


def test_decision_without_a_date_is_judged_on_ek_and_chamber() -> None:
    decision = match_rows(make_key(decision_date=None), [row()])
    assert decision.kind == "verified"
    assert decision.matched["decision_date"] == "absent"


def test_chamberless_decision_skips_the_chamber() -> None:
    aym = make_key(court="aym", court_level="aym", chamber="")
    decision = match_rows(aym, [row(chamber="")])
    assert (decision.kind, decision.matched["chamber"]) == ("verified", "absent")


def test_hgk_expects_the_genel_kurul() -> None:
    hgk = make_key(court_level="hgk_iddk", chamber="", source_chamber="10")
    assert match_rows(hgk, [row(chamber="Hukuk Genel Kurulu")]).kind == "verified"
    assert match_rows(hgk, [row(chamber="9. Hukuk Dairesi")]).kind == "mismatch"


def test_bam_region_must_agree() -> None:
    key = make_key(court="bam", court_level="bam_bim", chamber="35. HD", bam_region="İstanbul")
    same = row(chamber="Istanbul Bölge Adliye Mahkemesi 35. Hukuk Dairesi")
    other = row(chamber="Ankara Bölge Adliye Mahkemesi 35. Hukuk Dairesi")
    assert match_rows(key, [same]).kind == "verified"
    decision = match_rows(key, [other])
    assert (decision.kind, decision.matched["bam_region"]) == ("mismatch", "mismatch")


def test_several_rows_pick_the_single_exact_one() -> None:
    rows = [row(ref="a", when=date(2020, 12, 11)), row(ref="b"), row(ref="c", chamber="22. HD")]
    decision = match_rows(make_key(), rows)
    assert decision.kind == "verified"
    assert decision.row is not None
    assert decision.row.ref == "b"
    assert "ambiguous" not in decision.matched


def test_several_equally_good_rows_are_ambiguous() -> None:
    decision = match_rows(make_key(), [row(ref="a"), row(ref="b")])
    assert decision.kind == "mismatch"
    assert decision.matched["ambiguous"] is True


def test_source_chamber_is_read_from_the_heading() -> None:
    key = make_key(esas_no="2024/389", source_chamber="10")
    assert (
        source_chamber_match(key, "Hukuk Genel Kurulu 2024/10-389 E. , 2025/12 K.")
        is FieldMatch.match
    )
    assert (
        source_chamber_match(key, "Hukuk Genel Kurulu 2024/389 E. , 2025/12 K.") is FieldMatch.fuzzy
    )
    assert source_chamber_match(make_key(), "anything") is FieldMatch.absent
