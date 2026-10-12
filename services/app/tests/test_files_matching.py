"""Candidates and ranking of the matches of an uploaded file (task 13a). The rules and the
ranking run on hand-built rows; the candidate query and the version chain need the database."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.files.matching import (
    SAME_NAME,
    SAME_REF,
    SAME_TITLE,
    Row,
    Subject,
    _candidates,
    _ranked,
    previous_version,
    reason_for,
    ref_key,
    similar_files,
)
from app.files.store import LocalFileStore
from app.models.common import DocumentType, IngestFile, IngestJob, IngestKind, ReviewStatus

Factory = async_sessionmaker[AsyncSession]
NOW = datetime(2026, 10, 12, tzinfo=UTC)


def row(
    n: int,
    *,
    name: str | None = None,
    title: str | None = None,
    doc_type: str | None = "genelge",
    ref: str | None = None,
    text_key: str | None = None,
) -> Row:
    return Row(uuid.UUID(int=n), name, title, doc_type, ref, NOW + timedelta(hours=n), text_key)


def subject(**kwargs: object) -> Subject:
    values: dict[str, object] = {
        "id": uuid.UUID(int=999),
        "supersedes_id": None,
        "doc_types": frozenset({"genelge"}),
        "official_ref": None,
        "title": None,
        "name": None,
    }
    if "doc_type" in kwargs:
        kind = kwargs.pop("doc_type")
        values["doc_types"] = frozenset({kind} if kind else ())
    return Subject(**{**values, **kwargs})  # type: ignore[arg-type]


async def add(factory: Factory, *, previous: IngestFile | None = None, **fields: Any) -> IngestFile:
    """A stored file row (with a job of its own)."""
    async with factory() as session:
        job = IngestJob(kind=IngestKind.upload)
        session.add(job)
        await session.flush()
        n = uuid.uuid4().hex
        file = IngestFile(
            job_id=job.id,
            path=n,
            sha256=n * 2,
            size=1,
            storage_key=n,
            supersedes_id=previous.id if previous else None,
            **{"review_status": ReviewStatus.approved, **fields},
        )
        session.add(file)
        await session.commit()
        return file


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


def test_a_reference_counts_only_within_the_same_type() -> None:
    target = row(1, doc_type="genel_yazi", ref="2024/5")
    assert reason_for(subject(official_ref="2024/5", doc_type="genelge"), target) is None


def test_a_wrong_type_typed_by_the_user_does_not_hide_the_detected_one() -> None:
    target = row(1, doc_type="karar", ref="2021/5 E., 2021/7 K.")
    both = subject(doc_types=frozenset({"kanun", "karar"}), official_ref="2021/5 E., 2021/7 K.")
    assert reason_for(both, target) == SAME_REF
    typed_only = subject(doc_type="kanun", official_ref="2021/5 E., 2021/7 K.")
    assert reason_for(typed_only, target) is None


async def test_the_previous_version_is_the_newest_of_the_chain_not_the_old_candidate(
    kb_factory: Factory,
) -> None:
    v1 = await add(kb_factory, original_name="a.pdf", doc_type=DocumentType.genelge)
    v2 = await add(kb_factory, previous=v1, original_name="b.pdf")
    async with kb_factory() as db:
        found = await previous_version(db, subject(), {v1.id: row(1)}, {v1.id: SAME_REF})
    assert found == {"file_id": str(v2.id), "reason": SAME_REF}


async def test_an_archived_head_of_the_chain_is_skipped(kb_factory: Factory) -> None:
    v1 = await add(kb_factory)
    v2 = await add(kb_factory, previous=v1)
    await add(kb_factory, previous=v2, archived_at=NOW)
    async with kb_factory() as db:
        found = await previous_version(db, subject(), {v1.id: row(1)}, {v1.id: SAME_NAME})
    assert found == {"file_id": str(v2.id), "reason": SAME_NAME}


async def test_a_version_the_user_chose_is_not_second_guessed(kb_factory: Factory) -> None:
    target = await add(kb_factory)
    chosen = subject(supersedes_id=target.id)
    async with kb_factory() as db:
        assert (
            await previous_version(db, chosen, {target.id: row(1)}, {target.id: SAME_REF}) is None
        )
        assert await previous_version(db, subject(), {}, {}) is None


def test_the_stronger_reason_and_then_the_newer_upload_is_offered_first() -> None:
    by_name = row(5, name="a.pdf")
    by_ref = row(1, ref="2024/5")
    newer_ref = row(2, ref="2024/5")
    rows = {r.id: r for r in (by_name, by_ref, newer_ref)}
    reasons = {by_name.id: SAME_NAME, by_ref.id: SAME_REF, newer_ref.id: SAME_REF}
    assert _ranked(rows, reasons) == [newer_ref.id, by_ref.id, by_name.id]


async def test_candidates_come_from_the_database_by_ref_title_and_name(
    kb_factory: Factory,
) -> None:
    ref = await add(kb_factory, doc_type=DocumentType.genelge, official_ref="2024-5")
    wrong_type = await add(kb_factory, doc_type=DocumentType.kanun, official_ref="2024/5")
    title = await add(kb_factory, title="Prim Desteği ve Sigorta")
    name = await add(kb_factory, original_name="Ödeme  Genelgesi.PDF")
    archived = await add(kb_factory, original_name="Ödeme Genelgesi.pdf", archived_at=NOW)
    await add(kb_factory, doc_type=DocumentType.genelge, official_ref="2024/6", title="Başka")
    wanted = subject(
        official_ref="2024/5", title="PRİM DESTEĞİ ve sigorta", name="ödeme genelgesi.udf"
    )
    async with kb_factory() as db:
        found = await _candidates(db, wanted, set())
        assert set(found) == {ref.id, title.id, name.id}
        assert wrong_type.id not in found and archived.id not in found
        assert (await _candidates(db, wanted, {ref.id})).keys() == {title.id, name.id}
        assert await _candidates(db, subject(), set()) == {}
    reasons = {rid: reason_for(wanted, r) for rid, r in found.items()}
    assert reasons == {ref.id: SAME_REF, title.id: SAME_TITLE, name.id: SAME_NAME}


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
    found = similar_files(store, text, rows, reasons)
    assert [m["file_id"] for m in found] == [str(a.id)]
    assert found[0]["score"] >= 0.9
    assert found[0]["reason"] == SAME_NAME
