import copy
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kb import (
    StaleExtraction,
    approve_extraction,
    approve_statute_article,
    article_as_of,
    format_amending_ref,
    publish_batch,
    publish_decision,
    publish_statute_article,
    queue,
    reject_extraction,
    statute_is_published,
    unpublished_statute_articles,
)
from app.loaders import statutes as statute_loader
from app.loaders.decisions import load, prepare, read_rows
from app.loaders.report import LoadCounts
from app.loaders.statutes_report import StatuteCounts
from app.models.common import (
    Court,
    Extraction,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
    Verification,
)
from app.models.decision import Decision
from app.models.statute import Statute, StatuteArticle, StatuteArticleVersion
from app.models.user import AppUser
from hukuk_ingest.statutes.timeline import statute_as_of
from hukuk_models import ReviewFilters

FIXTURE = Path(__file__).parent / "fixtures" / "decisions_fixture.jsonl"


@pytest.fixture
async def kb_loaded(
    kb_factory: async_sessionmaker[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    """`kb_factory` with the decision fixture loaded as review-queue rows."""
    rows, _, _ = read_rows(FIXTURE)
    prepared, _ = prepare(rows, {})
    await load(kb_factory, prepared, LoadCounts())
    return kb_factory


async def _extraction(session: AsyncSession, journal_page: int) -> Extraction:
    rows = (await session.execute(select(Extraction))).scalars().all()
    return next(e for e in rows if e.fields["journal_page"] == journal_page)


def _review(
    extraction: Extraction,
    reviewer: AppUser,
    decision: ReviewDecision,
    edits: dict[str, Any] | None = None,
) -> Review:
    return Review(
        extraction_id=extraction.id, reviewer_id=reviewer.id, decision=decision, edits=edits
    )


async def test_publish_copies_fields_and_overlays_edits(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction = await _extraction(session, 10)
        review = _review(
            extraction, reviewer, ReviewDecision.edit, {"outcome": "onama", "chamber": "10. HD"}
        )
        session.add(review)
        await session.flush()
        decision_id = await publish_decision(session, extraction.id, review.id)
        await session.commit()

        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert decision.court is Court.yargitay
        assert (decision.chamber, decision.outcome) == ("10. HD", "onama")
        assert (decision.esas_no, decision.karar_no) == ("2003/2518", "2003/15276")
        assert decision.decision_date == date(2003, 9, 23)
        assert decision.full_text == extraction.fields["full_text"]
        assert decision.editorial_summary == extraction.fields["editorial_summary"]
        assert decision.related_articles == extraction.fields["related_articles"]
        assert (decision.source_id, decision.extraction_id, decision.review_id) == (
            extraction.source_id,
            extraction.id,
            review.id,
        )
        assert decision.verification is Verification.unverified
        source = await session.get(Source, extraction.source_id)
        assert source is not None
        assert source.status is RecordStatus.approved


async def test_empty_fields_become_null(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction = await _extraction(session, 18)  # no esas_no
        review = _review(extraction, reviewer, ReviewDecision.approve)
        session.add(review)
        await session.flush()
        decision_id = await publish_decision(session, extraction.id, review.id)
        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert decision.esas_no is None


async def test_a_rejected_review_does_not_publish(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction = await _extraction(session, 10)
        review = _review(extraction, reviewer, ReviewDecision.reject)
        session.add(review)
        await session.flush()
        with pytest.raises(ValueError, match="rejected"):
            await publish_decision(session, extraction.id, review.id)


async def test_a_source_is_published_once(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction = await _extraction(session, 10)
        review = _review(extraction, reviewer, ReviewDecision.approve)
        session.add(review)
        await session.flush()
        await publish_decision(session, extraction.id, review.id)
        with pytest.raises(ValueError, match="analyzed"):
            await publish_decision(session, extraction.id, review.id)


async def test_a_review_of_another_extraction_is_refused(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction, other = await _extraction(session, 10), await _extraction(session, 12)
        review = _review(other, reviewer, ReviewDecision.approve)
        session.add(review)
        await session.flush()
        with pytest.raises(ValueError, match="does not belong"):
            await publish_decision(session, extraction.id, review.id)


async def test_a_decision_without_a_court_cannot_be_published(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction = await _extraction(session, 21)  # court is empty
        review = _review(extraction, reviewer, ReviewDecision.approve)
        session.add(review)
        await session.flush()
        with pytest.raises(ValueError, match="court"):
            await publish_decision(session, extraction.id, review.id)


async def test_a_live_key_collision_is_an_integrity_error(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        first, second = await _extraction(session, 13), await _extraction(session, 30)
        for extraction in (first, second):  # the same_text pair shares its key
            review = _review(extraction, reviewer, ReviewDecision.approve)
            session.add(review)
            await session.flush()
            if extraction is first:
                await publish_decision(session, extraction.id, review.id)
        with pytest.raises(IntegrityError):
            await publish_decision(session, second.id, review.id)


# --- queue and the writes after a review ------------------------------------------------------


async def _first_high(session: AsyncSession) -> uuid.UUID:
    rows = (await session.execute(queue("high", ReviewFilters(), "sha256"))).all()
    first: uuid.UUID = rows[0].id
    return first


async def _count(session: AsyncSession, model: Any) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_the_queue_in_sha256_order_resumes_after_a_cursor(
    kb_loaded: async_sessionmaker[AsyncSession],
) -> None:
    async with kb_loaded() as session:
        rows = (await session.execute(queue(None, ReviewFilters(), "sha256"))).all()
        assert [r.sha256 for r in rows] == sorted(r.sha256 for r in rows)
        assert len(rows) > 3
        after = (
            await session.execute(queue(None, ReviewFilters(), "sha256", rows[2].sha256))
        ).all()
        assert [r.id for r in after] == [r.id for r in rows[3:]]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            "INSERT INTO extraction (file_id, source_id, parser_name, parser_version, fields, "
            "confidence, warnings) SELECT file_id, source_id, parser_name, 'next', fields, "
            "confidence, warnings FROM extraction WHERE id = :id",
            "newer extraction",
        ),
        (
            "UPDATE extraction SET confidence = jsonb_set(confidence, '{band}', '\"medium\"') "
            "WHERE id = :id",
            "band high",
        ),
        (
            "UPDATE source SET status = 'rejected' "
            "WHERE id = (SELECT source_id FROM extraction WHERE id = :id)",
            "no longer in review",
        ),
    ],
    ids=["newer extraction", "other band", "source left review"],
)
async def test_a_batch_rechecks_the_extraction_under_the_lock(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser, change: str, reason: str
) -> None:
    async with kb_loaded() as session:
        extraction_id = await _first_high(session)  # what the reviewer saw ...
        await session.execute(text(change), {"id": extraction_id})  # ... then the state moved on
        result = await publish_batch(session, [extraction_id], reviewer.id, "high")
        assert (result.published, result.conflicts) == (0, [])
        [(failed_id, message)] = result.failed
        assert failed_id == extraction_id
        assert reason in message
        assert (await _count(session, Review), await _count(session, Decision)) == (0, 0)


async def test_an_unknown_reviewer_is_a_failure_not_a_conflict(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction_id = await _first_high(session)
        with pytest.raises(ValueError, match="fk_review_reviewer_id_app_user"):
            await approve_extraction(session, extraction_id, uuid.uuid4())
        result = await publish_batch(session, [extraction_id], uuid.uuid4(), "high")
        assert (result.published, result.conflicts) == (0, [])
        assert "fk_review_reviewer_id_app_user" in result.failed[0][1]
        assert await _count(session, Review) == 0
        # the session is still usable: the same record goes through with a real reviewer
        assert (await publish_batch(session, [extraction_id], reviewer.id, "high")).published == 1


async def test_a_live_key_collision_stays_an_integrity_error(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        first, second = await _extraction(session, 13), await _extraction(session, 30)
        await approve_extraction(session, first.id, reviewer.id)
        with pytest.raises(IntegrityError):
            await approve_extraction(session, second.id, reviewer.id)
        assert await _count(session, Review) == 1


async def test_reject_marks_the_source_once(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction_id = await _first_high(session)
        review_id = await reject_extraction(session, extraction_id, reviewer.id, "kopya")
        review = await session.get(Review, review_id)
        assert review is not None
        assert (review.decision, review.note) == (ReviewDecision.reject, "kopya")
        status = (
            await session.execute(
                select(Source.status)
                .join(Extraction, Extraction.source_id == Source.id)
                .where(Extraction.id == extraction_id)
            )
        ).scalar_one()
        assert status is RecordStatus.rejected
        with pytest.raises(StaleExtraction, match="no longer in review"):
            await reject_extraction(session, extraction_id, reviewer.id, "tekrar")
        assert await _count(session, Decision) == 0


# --- statutes (task 11b; fixtures in conftest) ---------------------------------------------------

Factory = async_sessionmaker[AsyncSession]
ExtractionIds = Callable[[str], Awaitable[dict[str, uuid.UUID]]]  # the fixture of conftest
A18_TEXT = "Madde 18 yeni metin."


async def _versions(factory: Factory, article_no: str) -> list[StatuteArticleVersion]:
    async with factory() as session:
        return list(
            (
                await session.execute(
                    select(StatuteArticleVersion)
                    .join(StatuteArticle)
                    .where(StatuteArticle.article_no == article_no)
                    .order_by(StatuteArticleVersion.valid_from, StatuteArticleVersion.recorded_at)
                )
            )
            .scalars()
            .all()
        )


async def _total(factory: Factory, model: Any) -> int:
    async with factory() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_publishing_an_article_writes_the_statute_the_article_and_a_row_per_version(
    kb_factory: Factory,
    statutes_loaded: dict[str, uuid.UUID],
    reviewer: AppUser,
    statute_record: dict[str, Any],
) -> None:
    async with kb_factory() as session:
        review_id, article_id = await approve_statute_article(
            session, statutes_loaded["18"], reviewer.id
        )
        await session.commit()
        statute = (await session.execute(select(Statute))).scalar_one()
        assert (statute.number, statute.kind.value, statute.full_title) == (
            "4857",
            "kanun",
            "İŞ KANUNU",
        )
        assert (statute.rg_date, statute.rg_number, statute.short_name) == (
            date(2003, 6, 10),
            "25134",
            None,
        )
        article = await session.get(StatuteArticle, article_id)
        assert article is not None
        assert (article.statute_id, article.article_no, article.ordinal) == (statute.id, "18", 18)
        extraction = await session.get(Extraction, statutes_loaded["18"])
        assert extraction is not None
        source = await session.get(Source, extraction.source_id)
        assert source is not None
        assert source.status is RecordStatus.approved
        assert statute.source_id == source.id

    first, second = await _versions(kb_factory, "18")  # the gap before 2016-05-13 has no row
    assert (first.valid_from, first.valid_to) == (date(2016, 5, 13), date(2018, 1, 1))
    assert (second.valid_from, second.valid_to) == (date(2018, 1, 1), None)
    assert (first.text, second.text) == ("Madde 18 eski metin.", A18_TEXT)
    assert (first.change_kind.value, second.change_kind.value) == ("amended", "amended")
    assert first.heading == "Feshin geçerli sebebe dayandırılması"
    assert (first.amending_ref, second.amending_ref) == ("6552 (10/9/2014)", "7036 (12/10/2017)")
    assert (first.confidence, second.confidence) == ("high", "medium")
    assert second.warnings == ["exception_effective"]
    assert second.footnotes == [{"marker": "1", "text": "Dipnot metni."}]
    assert second.evidence["basis"] == "exception"
    assert second.evidence["snapshot_dates"] == ["2016-05-13", "2026-04-22"]
    wanted = statute_record["articles"][0]["versions"][1]["amending_ref"]
    assert second.evidence["amendments"] == wanted
    for v in (first, second):
        assert (v.source_id, v.extraction_id, v.review_id) == (
            source.id,
            statutes_loaded["18"],
            review_id,
        )
        assert (v.recorded_by, v.superseded_at) == (str(reviewer.id), None)


async def test_a_second_article_reuses_the_statute(
    kb_factory: Factory, statutes_published: dict[str, uuid.UUID]
) -> None:
    assert await _total(kb_factory, Statute) == 1
    assert await _total(kb_factory, StatuteArticle) == 3
    assert await _total(kb_factory, StatuteArticleVersion) == 5  # 2 + 2 + 1, gaps have no row


async def test_republishing_the_live_extraction_changes_nothing(
    kb_factory: Factory, statutes_published: dict[str, uuid.UUID]
) -> None:
    async with kb_factory() as session:
        review_id = (
            await session.execute(
                select(Review.id).where(Review.extraction_id == statutes_published["18"])
            )
        ).scalar_one()
        before = (await session.execute(select(StatuteArticleVersion.id))).scalars().all()
        await publish_statute_article(session, statutes_published["18"], review_id)
        await session.commit()
        after = (await session.execute(select(StatuteArticleVersion.id))).scalars().all()
    assert sorted(after) == sorted(before)
    assert all(v.superseded_at is None for v in await _versions(kb_factory, "18"))


async def _newer_a18(
    factory: Factory, record: dict[str, Any], extraction_ids: ExtractionIds
) -> uuid.UUID:
    """Load a second parser version of the statute in which the text of article 18 changed."""
    newer = copy.deepcopy(record)
    newer["parser_version"] = "2"
    newer["articles"][0]["versions"][1]["text"] = "Madde 18 değişmiş metin."
    await statute_loader.load(factory, statute_loader.prepare([newer]), {}, StatuteCounts())
    return (await extraction_ids("2"))["18"]


async def test_a_newer_extraction_supersedes_the_live_rows_and_deletes_nothing(
    kb_factory: Factory,
    statutes_published: dict[str, uuid.UUID],
    extraction_ids: ExtractionIds,
    statute_record: dict[str, Any],
    reviewer: AppUser,
) -> None:
    newer = await _newer_a18(kb_factory, statute_record, extraction_ids)
    async with kb_factory() as session:
        await approve_statute_article(session, newer, reviewer.id)
        await session.commit()
        assert (await article_as_of(session, "4857", "18", date(2020, 1, 1)))["version"][
            "text"
        ] == ("Madde 18 değişmiş metin.")
    rows = await _versions(kb_factory, "18")
    assert len(rows) == 4
    live = [v for v in rows if v.superseded_at is None]
    assert {v.extraction_id for v in live} == {newer}
    assert {v.extraction_id for v in rows if v.superseded_at is not None} == {
        statutes_published["18"]
    }
    assert await _total(kb_factory, StatuteArticle) == 3  # the article row is the same
    assert len([v for v in await _versions(kb_factory, "Ek 2") if v.superseded_at]) == 0


async def test_an_extraction_older_than_the_live_one_is_refused(
    kb_factory: Factory,
    statutes_published: dict[str, uuid.UUID],
    extraction_ids: ExtractionIds,
    statute_record: dict[str, Any],
    reviewer: AppUser,
) -> None:
    newer = await _newer_a18(kb_factory, statute_record, extraction_ids)
    async with kb_factory() as session:
        await approve_statute_article(session, newer, reviewer.id)
        await session.commit()
    async with kb_factory() as session:
        with pytest.raises(StaleExtraction):
            await approve_statute_article(session, statutes_published["18"], reviewer.id)
        await session.commit()
    live = [v for v in await _versions(kb_factory, "18") if v.superseded_at is None]
    assert {v.extraction_id for v in live} == {newer}


async def test_publish_statute_article_refuses_what_it_cannot_publish(
    kb_factory: Factory,
    statutes_loaded: dict[str, uuid.UUID],
    kb_loaded: Factory,
    reviewer: AppUser,
) -> None:
    async with kb_factory() as session:
        decision = (
            (await session.execute(select(Extraction).where(Extraction.parser_name == "decisions")))
            .scalars()
            .first()
        )
        assert decision is not None
        a18 = statutes_loaded["18"]
        reject = Review(extraction_id=a18, reviewer_id=reviewer.id, decision=ReviewDecision.reject)
        edit = Review(
            extraction_id=a18,
            reviewer_id=reviewer.id,
            decision=ReviewDecision.edit,
            edits={"x": 1},
        )
        wrong = Review(
            extraction_id=decision.id, reviewer_id=reviewer.id, decision=ReviewDecision.approve
        )
        session.add_all([reject, edit, wrong])
        await session.flush()
        with pytest.raises(ValueError, match="rejected"):
            await publish_statute_article(session, a18, reject.id)
        with pytest.raises(ValueError, match="edits"):
            await publish_statute_article(session, a18, edit.id)
        with pytest.raises(ValueError, match="not a statute article"):
            await publish_statute_article(session, decision.id, wrong.id)
        with pytest.raises(ValueError, match="does not belong"):
            await publish_statute_article(session, a18, wrong.id)
    assert await _total(kb_factory, StatuteArticleVersion) == 0


async def test_a_timeline_without_versions_is_not_published(
    kb_factory: Factory, statute_record: dict[str, Any], reviewer: AppUser
) -> None:
    empty = copy.deepcopy(statute_record)
    empty["articles"][3]["versions"] = []
    await statute_loader.load(kb_factory, statute_loader.prepare([empty]), {}, StatuteCounts())
    async with kb_factory() as session:
        extraction_id = (
            await session.execute(
                select(Extraction.id).where(Extraction.fields["article_no"].as_string() == "5")
            )
        ).scalar_one()
        with pytest.raises(ValueError, match="no version"):
            await approve_statute_article(session, extraction_id, reviewer.id)
    assert await _total(kb_factory, Review) == 0


async def test_unpublished_articles_are_listed_by_band_and_newest_extraction(
    kb_factory: Factory,
    statutes_loaded: dict[str, uuid.UUID],
    extraction_ids: ExtractionIds,
    statute_record: dict[str, Any],
    reviewer: AppUser,
) -> None:
    async def ids(band: str) -> set[uuid.UUID]:
        async with kb_factory() as session:
            rows = await session.execute(unpublished_statute_articles(band))  # type: ignore[arg-type]
            return set(rows.scalars().all())

    assert await ids("high") == {statutes_loaded["Geçici 1"], statutes_loaded["5"]}
    assert await ids("low") == {statutes_loaded["Ek 2"]}
    async with kb_factory() as session:
        await approve_statute_article(session, statutes_loaded["Geçici 1"], reviewer.id)
        await session.commit()
    assert await ids("high") == {statutes_loaded["5"]}
    newer = await _newer_a18(kb_factory, statute_record, extraction_ids)
    assert await ids("medium") == {newer}  # not the version 1 extraction of the same article


async def test_statute_extractions_are_not_in_the_decision_queue(
    kb_factory: Factory, statutes_published: dict[str, uuid.UUID], kb_loaded: Factory
) -> None:
    async with kb_factory() as session:
        for status in ("pending", "approved", "all"):
            rows = (await session.execute(queue(None, ReviewFilters(), status=status))).all()
            assert not {r.id for r in rows} & set(statutes_published.values()), status


def _db_shape(result: dict[str, Any]) -> dict[str, Any]:
    """A result of the pure `as_of` in the shape of the database path: the amending acts of the
    version as their label, and the acts themselves in `evidence.amendments`."""
    out = copy.deepcopy(result)
    if "version" in out:
        v = out["version"]
        v["evidence"] = {**v["evidence"], "amendments": v["amending_ref"]}
        v["amending_ref"] = format_amending_ref(v["amending_ref"])
    return out


def _probe_dates(article: dict[str, Any]) -> set[date]:
    edges: set[date] = {date(1990, 1, 1), date(2099, 1, 1)}
    marks = [v[k] for v in article["versions"] for k in ("valid_from", "valid_to")]
    marks += [g[k] for g in article["gaps"] for k in ("from", "to")]
    marks.append(article["latest_snapshot_date"])
    for mark in filter(None, marks):
        day = date.fromisoformat(mark)
        edges |= {day - timedelta(days=1), day, day + timedelta(days=1)}
    return edges


async def test_the_database_query_mirrors_the_pure_as_of(
    kb_factory: Factory, statutes_published: dict[str, uuid.UUID], statute_record: dict[str, Any]
) -> None:
    seen: set[str] = set()
    compared = 0
    async with kb_factory() as session:
        for article in statute_record["articles"]:
            if article["article_no"] not in statutes_published or article["article_no"] == "5":
                continue
            for day in sorted(_probe_dates(article)):
                expected = _db_shape(statute_as_of(statute_record, article["article_no"], day))
                actual = await article_as_of(session, "4857", article["article_no"], day)
                assert actual == expected, (article["article_no"], day)
                seen.add(actual["status"])
                compared += 1
    assert seen == {"found", "gap", "not_in_force"}
    assert compared > 40


async def test_only_published_articles_count(
    kb_factory: Factory, statutes_published: dict[str, uuid.UUID]
) -> None:
    unpublished = {"status": "unknown_article", "reason": "not_published"}
    async with kb_factory() as session:
        # "5" is loaded but never approved; "99" and the statute 9999 do not exist
        assert await article_as_of(session, "4857", "5", date(2020, 1, 1)) == unpublished
        assert await article_as_of(session, "4857", "99", date(2020, 1, 1)) == unpublished
        assert await article_as_of(session, "9999", "18", date(2020, 1, 1)) == unpublished
        assert await statute_is_published(session, "4857")
        assert not await statute_is_published(session, "9999")


async def test_a_gap_carries_no_text(
    kb_factory: Factory, statutes_published: dict[str, uuid.UUID]
) -> None:
    async with kb_factory() as session:
        result = await article_as_of(session, "4857", "18", date(2014, 1, 1))
    assert set(result) == {"status", "gap", "latest_snapshot_date", "stale"}
    assert result["status"] == "gap"
    assert result["gap"]["known_amendments"][0]["law"] == "6552"
    assert "text" not in result["gap"]
