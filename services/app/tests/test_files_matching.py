"""Candidates and ranking of the matches of an uploaded file (task 13a). No database: the rows
are built by hand; `test_worker.py` covers the queries."""

import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.files.matching import (
    SAME_CASE,
    SAME_DATE,
    SAME_NAME,
    SAME_REF,
    SAME_TITLE,
    Row,
    Subject,
    previous_version,
    reason_for,
    ref_key,
    similar_files,
)
from app.files.store import LocalFileStore

NOW = datetime(2026, 10, 12, tzinfo=UTC)


def row(
    n: int,
    *,
    name: str | None = None,
    title: str | None = None,
    doc_type: str | None = "genelge",
    ref: str | None = None,
    doc_date: date | None = None,
    previous: Row | None = None,
    archived: bool = False,
    approved: bool = True,
    text_key: str | None = None,
) -> Row:
    return Row(
        uuid.UUID(int=n),
        previous.id if previous else None,
        name,
        title,
        doc_type,
        ref,
        doc_date,
        NOW + timedelta(hours=n),
        archived,
        approved,
        text_key,
    )


def subject(**kwargs: object) -> Subject:
    values: dict[str, object] = {
        "id": uuid.UUID(int=999),
        "supersedes_id": None,
        "doc_types": frozenset({"genelge"}),
        "official_ref": None,
        "title": None,
        "name": None,
        "doc_date": None,
    }
    if "doc_type" in kwargs:
        kind = kwargs.pop("doc_type")
        values["doc_types"] = frozenset({kind} if kind else ())
    return Subject(**{**values, **kwargs})  # type: ignore[arg-type]


def test_references_agree_across_case_spacing_and_punctuation() -> None:
    assert ref_key("2024/5") == ref_key(" 2024 - 5 ") == "20245"
    assert ref_key("E-72044944-640") == ref_key("e 72044944 640")
    assert ref_key(None) == ""


def test_the_strongest_reason_wins() -> None:
    target = row(1, name="2024-5 Genelge.pdf", title="Prim desteği", ref="2024/5")
    assert reason_for(subject(official_ref="2024-5"), target) == SAME_REF
    assert reason_for(subject(title="PRİM DESTEĞİ"), target) == SAME_TITLE
    assert reason_for(subject(name="2024-5 genelge.UDF"), target) == SAME_NAME
    assert reason_for(subject(official_ref="2024/6", name="x.pdf"), target) is None
    assert reason_for(subject(official_ref="2024/6"), target, same_case=True) == SAME_CASE


def test_a_reference_counts_only_within_the_same_type() -> None:
    target = row(1, doc_type="genel_yazi", ref="2024/5")
    assert reason_for(subject(official_ref="2024/5", doc_type="genelge"), target) is None


def test_a_wrong_type_typed_by_the_user_does_not_hide_the_detected_one() -> None:
    target = row(1, doc_type="karar", ref="2021/5 E., 2021/7 K.")
    both = subject(doc_types=frozenset({"kanun", "karar"}), official_ref="2021/5 E., 2021/7 K.")
    assert reason_for(both, target) == SAME_REF
    typed_only = subject(doc_type="kanun", official_ref="2021/5 E., 2021/7 K.")
    assert reason_for(typed_only, target) is None


def test_type_and_date_make_a_candidate_for_the_text_comparison() -> None:
    target = row(1, doc_date=date(2024, 5, 1))
    assert reason_for(subject(doc_date=date(2024, 5, 1)), target) == SAME_DATE
    assert reason_for(subject(doc_date=date(2024, 5, 2)), target) is None
    assert reason_for(subject(doc_type=None, doc_date=date(2024, 5, 1)), target) is None


def test_the_previous_version_is_the_newest_of_the_chain_not_the_old_candidate() -> None:
    v1 = row(1, name="a.pdf", ref="2024/5")
    v2 = row(2, name="a.pdf", ref="2024/5", previous=v1)
    rows = {r.id: r for r in (v1, v2)}
    found = previous_version(subject(), rows, {v1.id: SAME_REF})
    assert found == {"file_id": str(v2.id), "reason": SAME_REF}


def test_a_chain_whose_head_is_archived_or_pending_falls_back_to_the_newest_usable() -> None:
    v1 = row(1)
    v2 = row(2, previous=v1)
    v3 = row(3, previous=v2, approved=False)
    rows = {r.id: r for r in (v1, v2, v3)}
    assert previous_version(subject(), rows, {v1.id: SAME_NAME}) == {
        "file_id": str(v2.id),
        "reason": SAME_NAME,
    }
    v2_archived = row(2, previous=v1, archived=True)
    rows = {r.id: r for r in (v1, v2_archived)}
    assert previous_version(subject(), rows, {v1.id: SAME_NAME}) == {
        "file_id": str(v1.id),
        "reason": SAME_NAME,
    }
    only_archived = {v1.id: row(1, archived=True)}
    assert previous_version(subject(), only_archived, {v1.id: SAME_NAME}) is None


def test_a_pending_file_and_a_date_match_are_never_the_previous_version() -> None:
    pending = row(1, approved=False)
    dated = row(2)
    rows = {r.id: r for r in (pending, dated)}
    assert previous_version(subject(), rows, {pending.id: SAME_REF, dated.id: SAME_DATE}) is None


def test_a_version_the_user_chose_is_not_second_guessed() -> None:
    target = row(1)
    chosen = subject(supersedes_id=target.id)
    assert previous_version(chosen, {target.id: target}, {target.id: SAME_REF}) is None


def test_the_stronger_reason_and_then_the_newer_upload_is_offered_first() -> None:
    by_name = row(5, name="a.pdf")
    by_ref = row(1, ref="2024/5")
    newer_ref = row(2, ref="2024/5")
    rows = {r.id: r for r in (by_name, by_ref, newer_ref)}
    reasons = {by_name.id: SAME_NAME, by_ref.id: SAME_REF, newer_ref.id: SAME_REF}
    found = previous_version(subject(), rows, reasons)
    assert found == {"file_id": str(newer_ref.id), "reason": SAME_REF}


def test_similar_files_are_the_candidates_whose_text_scores_over_the_threshold(
    tmp_path: Path,
) -> None:
    store = LocalFileStore(tmp_path)
    text = " ".join(
        f"madde {n} gereğince işçi {n} numaralı işyerinde çalışmaya devam eder" for n in range(50)
    )
    same = store.put_text("a" * 64, "BAŞKA KAYNAK\n" + text.replace(" gereğince ", "\ngereğince\n"))
    other = store.put_text(
        "b" * 64, " ".join(f"tamamen farklı {n} sigorta primi borcu {n}" for n in range(50))
    )
    a = row(1, text_key=same)
    b = row(2, text_key=other)
    c = row(3)  # no text
    d = row(4, text_key="text/" + "c" * 64 + ".txt")  # the file is gone
    rows = {r.id: r for r in (a, b, c, d)}
    reasons = {r.id: SAME_NAME for r in rows.values()}
    found = similar_files(store, text, rows, reasons, set())
    assert [m["file_id"] for m in found] == [str(a.id)]
    assert found[0]["score"] >= 0.9
    assert found[0]["reason"] == SAME_NAME
    assert similar_files(store, text, rows, reasons, {a.id}) == []
