import pytest

from hukuk_ingest import quality
from hukuk_ingest.quality import PAGE_BREAK, Verdict, judge, measure

GOOD = "İşçinin kıdem tazminatı için bir yıl çalışması gerekir ve bu süre ile ilgili madde " * 4
BAD = "xkq zzt brm plv wnd " * 15


def _verdict(*pages: str) -> Verdict:
    return judge(measure(PAGE_BREAK.join(pages), len(pages)))


@pytest.mark.parametrize("text", ["", "\r\n" * 100])
def test_judge_page_without_visible_text_has_no_text_layer(text: str) -> None:
    verdict = judge(measure(text, 1))
    assert (verdict.ok, verdict.reason) == (False, "no_text_layer")


def test_judge_zero_pages_has_no_text_layer() -> None:
    verdict = judge(measure("", 0))
    assert (verdict.ok, verdict.reason) == (False, "no_text_layer")


def test_judge_sound_text_is_ok_without_warnings() -> None:
    assert _verdict(GOOD, GOOD) == Verdict(True)


@pytest.mark.parametrize(
    "text",
    ["bo印dlgle料le ııla kunılaıı " * 40, "xkq zzt brm plv wnd " * 60],
    ids=["cjk", "no_function_words"],
)
def test_judge_broken_layer_is_bad_ocr(text: str) -> None:
    verdict = judge(measure(text, 1))
    assert (verdict.ok, verdict.reason) == (False, "bad_ocr_layer")


@pytest.mark.parametrize("junk", ["Привет мир", "مرحبا بالعالم", "bo印dlgle"])
def test_judge_foreign_script_share_is_bad_ocr(junk: str) -> None:
    verdict = judge(measure(GOOD + junk * 3, 1))
    assert (verdict.ok, verdict.reason) == (False, "bad_ocr_layer")


def test_judge_quoted_foreign_text_is_not_bad_ocr() -> None:
    assert judge(measure(GOOD * 10 + "Привет мир", 1)).ok


def test_judge_borderline_stopword_ratio_warns() -> None:
    words = ["madde"] * 3 + ["işçi", "tazminat", "hak", "dava", "süre", "ücret"] * 10 + ["x"] * 3
    verdict = judge(measure((" ".join(words) + " ") * 3, 1))
    assert verdict == Verdict(True, warnings=("borderline_quality",))


def test_judge_numbers_only_page_warns_too_little_text() -> None:
    verdict = judge(measure("1234567890 " * 20, 1))
    assert verdict == Verdict(True, warnings=("too_little_text",))


def test_judge_interior_empty_pages_are_partial_text_layer() -> None:
    verdict = _verdict(GOOD, "", GOOD)  # 1 of 3 pages scanned
    assert (verdict.ok, verdict.reason) == (False, "partial_text_layer")


def test_judge_trailing_blank_page_only_warns() -> None:
    assert _verdict(GOOD, "") == Verdict(True, warnings=("empty_pages",))


def test_judge_few_interior_empty_pages_only_warn() -> None:
    assert _verdict(GOOD, "", *[GOOD] * 5) == Verdict(True, warnings=("empty_pages",))  # 1/7


def test_judge_weak_page_warns_but_passes() -> None:
    verdict = _verdict(GOOD * 3, GOOD * 3, GOOD * 3, BAD)
    assert verdict == Verdict(True, warnings=("weak_page_text",))


def test_measure_counts_empty_and_interior_empty_pages() -> None:
    q = measure(PAGE_BREAK.join([GOOD, "", GOOD, ""]), 4)
    assert (q.empty_pages, q.interior_empty_pages) == (2, 1)


def test_fingerprint_tracks_thresholds_and_stopwords(monkeypatch: pytest.MonkeyPatch) -> None:
    before = quality.fingerprint()
    monkeypatch.setattr(quality, "BAD_OCR_RATIO", 0.04)
    assert quality.fingerprint() != before
    monkeypatch.undo()
    monkeypatch.setattr(quality, "STOPWORDS", quality.STOPWORDS | {"zzz"})
    assert quality.fingerprint() != before
    monkeypatch.undo()
    assert quality.fingerprint() == before
