"""Knowledge-base writes that follow a human review (data-model.md §3-§4)."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from sqlalchemy import (
    ColumnElement,
    Exists,
    Select,
    Subquery,
    case,
    exists,
    func,
    nulls_last,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import (
    ChangeKind,
    Court,
    CourtLevel,
    Extraction,
    IngestFile,
    Jurisdiction,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
    SourceCategory,
    StatuteKind,
    TextCompleteness,
    Verification,
)
from app.models.decision import LIVE_KEY_INDEX, Decision
from app.models.statute import Statute, StatuteArticle, StatuteArticleVersion
from app.models.user import AppUser
from hukuk_ingest.statutes.timeline import FOUND, GAP, NOT_IN_FORCE, UNKNOWN_ARTICLE
from hukuk_models import Band, ListStatus, ReviewFilters, StatuteArticleStatus

PARSER_NAME = "decisions"
STATUTE_PARSER_NAME = "statutes"
Sort = Literal["score_asc", "score_desc", "reviewed_desc", "sha256"]

# The source statuses of each list tab. A published decision was approved, so it stays under
# "approved"; `summary` counts with the same sets.
STATUS_GROUPS: dict[str, tuple[RecordStatus, ...]] = {
    "pending": (RecordStatus.analyzed,),
    "approved": (RecordStatus.approved, RecordStatus.published),
    "rejected": (RecordStatus.rejected,),
}
STATUS_GROUPS["all"] = tuple(s for group in STATUS_GROUPS.values() for s in group)

# `decision` columns copied as they are from fields + edits; '' becomes NULL.
_NULLABLE_TEXT = ("esas_no", "karar_no", "outcome", "full_text", "editorial_summary")


async def publish_decision(
    session: AsyncSession, extraction_id: uuid.UUID, review_id: uuid.UUID
) -> uuid.UUID:
    """Copy an approved decision extraction (`fields` overlaid with `review.edits`) into
    `decision` and move its source to `approved`; the caller commits.

    `verification` is always `unverified`: the journal archive is a search aid, and only the
    official-source check (task 06) may make a decision citable. `approved` does not open it to
    citation. A live (court, bam_region, chamber, esas_no, karar_no) collision raises
    IntegrityError at flush."""
    review = await session.get(Review, review_id)
    extraction = await session.get(Extraction, extraction_id)
    if review is None or extraction is None or review.extraction_id != extraction_id:
        raise ValueError("review does not belong to the extraction")
    if review.decision is ReviewDecision.reject:
        raise ValueError("a rejected review cannot be published")
    source = (
        (
            await session.execute(
                select(Source)
                .where(Source.id == extraction.source_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if extraction.source_id
        else None
    )
    if source is None or source.category is not SourceCategory.decision:
        raise ValueError("extraction has no source of category 'decision'")
    if source.status is not RecordStatus.analyzed:
        raise ValueError("extraction has no source in status 'analyzed'")

    merged: dict[str, Any] = {**extraction.fields, **(review.edits or {})}
    if not merged["court"] or not merged["court_level"]:
        raise ValueError("court and court_level are required")
    decision = Decision(
        source_id=source.id,
        extraction_id=extraction_id,
        review_id=review_id,
        recorded_by=str(review.reviewer_id),
        court=Court(merged["court"]),
        court_level=CourtLevel(merged["court_level"]),
        chamber=merged["chamber"],
        source_chamber=merged["source_chamber"],
        bam_region=merged["bam_region"],
        decision_kind=merged["decision_kind"],
        decision_date=date.fromisoformat(merged["decision_date"])
        if merged["decision_date"]
        else None,
        jurisdiction=Jurisdiction(merged["jurisdiction"]) if merged["jurisdiction"] else None,
        related_articles=merged["related_articles"],
        keywords=merged["keywords"],
        text_completeness=TextCompleteness(merged["text_completeness"]),
        verification=Verification.unverified,
        journal_issue=merged["journal_issue"],
        journal_page=merged["journal_page"],
        **{name: merged[name] or None for name in _NULLABLE_TEXT},
    )
    session.add(decision)
    source.status = RecordStatus.approved
    await session.flush()
    return decision.id


def newest_extractions(source_id: uuid.UUID | None = None) -> Subquery:
    """The newest `decisions` extraction of every decision source (of one source if given), with
    what the queue filters and shows. None of it is read from `fields`: the generated columns
    of `extraction` hold it."""
    stmt = (
        select(
            Extraction.id,
            Extraction.source_id,
            IngestFile.sha256,
            Source.title,
            Source.status,
            Extraction.confidence,
            Extraction.court,
            Extraction.chamber,
            Extraction.esas_no,
            Extraction.karar_no,
            Extraction.decision_date,
            Extraction.journal_issue,
            Extraction.duplicate_group,
        )
        .ext(distinct_on(Extraction.source_id))
        .join(IngestFile, IngestFile.id == Extraction.file_id)
        .join(Source, Source.id == Extraction.source_id)
        .where(Extraction.parser_name == PARSER_NAME, Source.category == SourceCategory.decision)
        .order_by(Extraction.source_id, Extraction.extracted_at.desc(), Extraction.id)
    )
    if source_id:
        stmt = stmt.where(Extraction.source_id == source_id)
    return stmt.subquery()


def last_reviews() -> Subquery:
    """The latest review of every reviewed source, with the reviewer's name: one `DISTINCT ON`
    pass, joined once by the queue."""
    stmt = (
        select(
            Extraction.source_id,
            Review.reviewed_at,
            Review.decision.label("review_decision"),
            Review.note,
            AppUser.display_name.label("reviewer_name"),
        )
        .ext(distinct_on(Extraction.source_id))
        .join(Extraction, Extraction.id == Review.extraction_id)
        .outerjoin(AppUser, AppUser.id == Review.reviewer_id)
        .order_by(Extraction.source_id, Review.reviewed_at.desc(), Review.id.desc())
    )
    return stmt.subquery()


def queue(
    band: Band | None,
    filters: ReviewFilters,
    sort: Sort = "score_asc",
    after: str | None = None,
    status: ListStatus = "pending",
) -> Select[Any]:
    """The review queue: newest extraction of every decision source in `status` (`pending` =
    `analyzed`; the other tabs come with their last review), filtered and ordered (most
    suspicious first by default, ties by sha256; `reviewed_desc` the newest review first,
    never-reviewed last; `sha256` is the stable order of bulk runs, of which `after` is the
    cursor: only records with a greater sha256)."""
    newest = newest_extractions()
    score = newest.c.confidence["score"].as_integer()
    conditions: list[ColumnElement[bool]] = [newest.c.status.in_(STATUS_GROUPS[status])]
    if band:
        conditions.append(newest.c.confidence["band"].as_string() == band)
    if filters.court is not None:
        conditions.append(newest.c.court == filters.court)
    if filters.reason is not None:
        conditions.append(newest.c.confidence["reasons"].contains([filters.reason]))
    if filters.journal_issue is not None:
        conditions.append(newest.c.journal_issue == filters.journal_issue)
    if filters.q:
        conditions.append(
            or_(
                newest.c.esas_no.icontains(filters.q, autoescape=True),
                newest.c.karar_no.icontains(filters.q, autoescape=True),
                newest.c.title.icontains(filters.q, autoescape=True),
            )
        )
    if after is not None:
        conditions.append(newest.c.sha256 > after)
    columns: list[Any] = [
        *newest.c,
        newest.c.confidence["band"].as_string().label("band"),
        score.label("score"),
    ]
    source: Any = newest
    reviewed = None
    if status != "pending":
        reviewed = last_reviews()
        source = newest.outerjoin(reviewed, reviewed.c.source_id == newest.c.source_id)
        columns += [
            reviewed.c.reviewed_at,
            reviewed.c.reviewer_name,
            reviewed.c.review_decision,
            reviewed.c.note,
        ]
    order = {
        "score_asc": (score.asc(), newest.c.sha256),
        "score_desc": (score.desc(), newest.c.sha256),
        "sha256": (newest.c.sha256,),
    }
    if reviewed is not None:
        order["reviewed_desc"] = (nulls_last(reviewed.c.reviewed_at.desc()), newest.c.sha256)
    return select(*columns).select_from(source).where(*conditions).order_by(*order[sort])


class StaleExtraction(ValueError):
    """The extraction is no longer what the reviewer saw: its source left review, a newer
    extraction replaced it, or it left the requested band."""


async def lock_pending(
    session: AsyncSession, extraction_id: uuid.UUID, band: Band | None = None
) -> Source:
    """Lock the source of the extraction (the row lock `publish_decision` takes) and check under
    it that the source is still `analyzed`, that the extraction is still the newest of its
    source and, if `band` is given, still in that band. Raises StaleExtraction otherwise; the
    lock lasts to the end of the transaction."""
    source_id = (
        await session.execute(select(Extraction.source_id).where(Extraction.id == extraction_id))
    ).scalar_one_or_none()
    if source_id is None:
        raise ValueError("extraction has no source")
    source = (
        await session.execute(
            select(Source)
            .where(Source.id == source_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    if source.status is not RecordStatus.analyzed:
        raise StaleExtraction("source is no longer in review")
    newest = newest_extractions(source_id)
    row = (
        await session.execute(select(newest.c.id, newest.c.confidence["band"].as_string()))
    ).one_or_none()
    if row is None:
        raise ValueError("extraction has no source of category 'decision'")
    if row[0] != extraction_id:
        raise StaleExtraction("source has a newer extraction")
    if band is not None and row[1] != band:
        raise StaleExtraction(f"extraction is no longer in band {band}")
    return source


def _violated_constraint(exc: IntegrityError) -> str | None:
    return getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)


@asynccontextmanager
async def _reviewed(
    session: AsyncSession,
    extraction_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: ReviewDecision,
    edits: dict[str, Any] | None,
    note: str | None,
    band: Band | None,
) -> AsyncIterator[tuple[Source, Review]]:
    """The one path of every review: in a savepoint, lock and check the extraction
    (`lock_pending`) and write the `review` row; the body does the rest. An IntegrityError other
    than the live-key collision (an unknown reviewer, say) becomes a ValueError; the collision
    stays an IntegrityError. On any error the savepoint is rolled back and nothing is left."""
    try:
        async with session.begin_nested():
            source = await lock_pending(session, extraction_id, band)
            review = Review(
                extraction_id=extraction_id,
                reviewer_id=reviewer_id,
                decision=decision,
                edits=edits,
                note=note,
            )
            session.add(review)
            await session.flush()
            yield source, review
            await session.flush()
    except IntegrityError as exc:
        if (name := _violated_constraint(exc)) == LIVE_KEY_INDEX:
            raise
        raise ValueError(f"database constraint violated: {name}") from exc


async def approve_extraction(
    session: AsyncSession,
    extraction_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: ReviewDecision = ReviewDecision.approve,
    edits: dict[str, Any] | None = None,
    note: str | None = None,
    band: Band | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """`review` row + `publish_decision`; returns (review_id, decision_id). Raises
    StaleExtraction (see `lock_pending`), ValueError (not publishable) or IntegrityError (live-key
    collision); the caller commits."""
    async with _reviewed(session, extraction_id, reviewer_id, decision, edits, note, band) as (
        _,
        review,
    ):
        return review.id, await publish_decision(session, extraction_id, review.id)


async def reject_extraction(
    session: AsyncSession, extraction_id: uuid.UUID, reviewer_id: uuid.UUID, note: str
) -> uuid.UUID:
    """`review` row (reject) and the source `rejected`; returns the review id. Raises like
    `approve_extraction`; the caller commits."""
    async with _reviewed(
        session, extraction_id, reviewer_id, ReviewDecision.reject, None, note, None
    ) as (source, review):
        source.status = RecordStatus.rejected
    return review.id


@dataclass
class BatchResult:
    published: int = 0
    conflicts: list[uuid.UUID] = field(default_factory=list)
    failed: list[tuple[uuid.UUID, str]] = field(default_factory=list)


async def _run_batch(
    extraction_ids: Sequence[uuid.UUID], approve: Callable[[uuid.UUID], Awaitable[object]]
) -> BatchResult:
    result = BatchResult()
    for extraction_id in extraction_ids:
        try:
            await approve(extraction_id)
            result.published += 1
        except IntegrityError:
            result.conflicts.append(extraction_id)
        except ValueError as exc:
            result.failed.append((extraction_id, str(exc)))
    return result


async def publish_batch(
    session: AsyncSession,
    extraction_ids: Sequence[uuid.UUID],
    reviewer_id: uuid.UUID,
    band: Band,
) -> BatchResult:
    """Approve and publish each extraction in its own savepoint: a live-key collision goes to
    `conflicts`, any other record `approve_extraction` refuses (not publishable, stale, no
    longer in `band`) to `failed` (id, reason); neither stops the run. The caller commits."""
    return await _run_batch(
        extraction_ids,
        lambda extraction_id: approve_extraction(session, extraction_id, reviewer_id, band=band),
    )


# --- statutes (task 11b) ----------------------------------------------------------------------
# The review unit is the article: one `statutes` extraction holds the whole timeline of one
# article. Its source is the statute; the source goes `approved` with the first published article
# and the per-article state is the `review` row plus the live version rows (`extraction_id`).
# These paths never touch `queue`, which reads decision sources only.


def _rg_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day}/{d.month}/{d.year}"


def format_amending_ref(refs: Sequence[dict[str, Any]]) -> str | None:
    """The amending acts of a timeline version as one label: "6552 (10/9/2014), 7036 (12/10/2017)"
    (law number and kabul date, each pair once); None when no note is known."""
    labels = dict.fromkeys(f"{r['law']} ({_rg_date(r['date'])})" for r in refs)
    return ", ".join(labels) or None


def version_evidence(version: dict[str, Any]) -> dict[str, Any]:
    """The `evidence` of a timeline version as published: its own evidence plus the amending
    notes (`amendments`)."""
    return {**version["evidence"], "amendments": version["amending_ref"]}


async def _statute_row(session: AsyncSession, source: Source, fields: dict[str, Any]) -> Statute:
    number = fields["statute_number"]
    statute = (
        await session.execute(
            select(Statute).where(Statute.kind == StatuteKind.kanun, Statute.number == number)
        )
    ).scalar_one_or_none()
    if statute is None:
        header = fields["statute"]
        statute = Statute(
            source_id=source.id,
            number=number,
            kind=StatuteKind.kanun,
            full_title=header["title"] or f"{number} sayılı Kanun",
            rg_date=date.fromisoformat(header["rg_tarihi"]) if header["rg_tarihi"] else None,
            rg_number=header["rg_sayisi"],
        )
        session.add(statute)
        await session.flush()
    return statute


async def publish_statute_article(
    session: AsyncSession, extraction_id: uuid.UUID, review_id: uuid.UUID
) -> uuid.UUID:
    """Copy an approved article timeline into `statute` (if missing), `statute_article` and one
    `statute_article_version` per timeline version (a gap has no row); returns the article id.
    The source moves `analyzed` -> `approved`; the caller commits.

    Republishing the extraction that is already live is a no-op. A newer extraction of the same
    article supersedes the live rows (`superseded_at`, never deleted); an older one than the
    live one raises StaleExtraction. `review.edits` are not applied: a review of a statute
    article only approves it. Overlapping live versions fail at flush (IntegrityError)."""
    review = await session.get(Review, review_id)
    extraction = await session.get(Extraction, extraction_id)
    if review is None or extraction is None or review.extraction_id != extraction_id:
        raise ValueError("review does not belong to the extraction")
    if review.decision is ReviewDecision.reject:
        raise ValueError("a rejected review cannot be published")
    if review.edits:
        raise ValueError("edits are not supported for statute articles")
    if extraction.parser_name != STATUTE_PARSER_NAME:
        raise ValueError("extraction is not a statute article")
    source = (
        (
            await session.execute(
                select(Source)
                .where(Source.id == extraction.source_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if extraction.source_id
        else None
    )
    if source is None or source.category is not SourceCategory.statute:
        raise ValueError("extraction has no source of category 'statute'")

    fields = extraction.fields
    if not fields["versions"]:
        raise ValueError("the timeline has no version to publish")
    statute = await _statute_row(session, source, fields)
    article = (
        await session.execute(
            select(StatuteArticle).where(
                StatuteArticle.statute_id == statute.id,
                StatuteArticle.article_no == fields["article_no"],
            )
        )
    ).scalar_one_or_none()
    if article is None:
        article = StatuteArticle(
            statute_id=statute.id, article_no=fields["article_no"], ordinal=fields["ordinal"]
        )
        session.add(article)
        await session.flush()
    live = (
        (
            await session.execute(
                select(StatuteArticleVersion).where(
                    StatuteArticleVersion.article_id == article.id,
                    StatuteArticleVersion.superseded_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if live and all(v.extraction_id == extraction_id for v in live):
        return article.id
    if live:
        current = await session.get(Extraction, live[0].extraction_id)
        if current is not None and current.extracted_at > extraction.extracted_at:
            raise StaleExtraction("a newer extraction of this article is already published")
        await session.execute(
            update(StatuteArticleVersion)
            .where(StatuteArticleVersion.id.in_([v.id for v in live]))
            .values(superseded_at=func.now())
        )
    article.ordinal = fields["ordinal"]
    for v in fields["versions"]:
        if v["valid_from"] is None:
            raise ValueError("a version has no start date")
        session.add(
            StatuteArticleVersion(
                article_id=article.id,
                text=v["text"],
                heading=v["heading"],
                valid_from=date.fromisoformat(v["valid_from"]),
                valid_to=date.fromisoformat(v["valid_to"]) if v["valid_to"] else None,
                change_kind=ChangeKind(v["change_kind"]),
                amending_ref=format_amending_ref(v["amending_ref"]),
                evidence=version_evidence(v),
                confidence=v["confidence"],
                warnings=v["warnings"],
                footnotes=v["footnotes"],
                source_id=source.id,
                extraction_id=extraction_id,
                review_id=review_id,
                recorded_by=str(review.reviewer_id),
            )
        )
    if source.status is RecordStatus.analyzed:
        source.status = RecordStatus.approved
    await session.flush()
    return article.id


def newest_statute_extractions() -> Subquery:
    """The newest `statutes` extraction of every article, with what the queue filters and shows,
    cut out of `fields` (the version texts are not read)."""
    number = Extraction.fields["statute_number"].as_string()
    article_no = Extraction.fields["article_no"].as_string()
    return (
        select(
            Extraction.id,
            Extraction.source_id,
            number.label("statute_number"),
            article_no.label("article_no"),
            Extraction.fields["ordinal"].as_integer().label("ordinal"),
            Extraction.fields["heading"].as_string().label("heading"),
            Extraction.fields["latest_snapshot_date"].as_string().label("latest_snapshot_date"),
            func.jsonb_array_length(Extraction.fields["versions"]).label("version_count"),
            func.jsonb_array_length(Extraction.fields["gaps"]).label("gap_count"),
            Extraction.confidence["band"].as_string().label("band"),
            Extraction.confidence["reasons"].label("reasons"),
        )
        .ext(distinct_on(number, article_no))
        .where(Extraction.parser_name == STATUTE_PARSER_NAME)
        .order_by(number, article_no, Extraction.extracted_at.desc(), Extraction.id)
        .subquery()
    )


def _is_live(extraction_id: Any) -> Exists:
    return exists().where(
        StatuteArticleVersion.extraction_id == extraction_id,
        StatuteArticleVersion.superseded_at.is_(None),
    )


def _is_rejected(extraction_id: Any) -> Exists:
    return exists().where(
        Review.extraction_id == extraction_id, Review.decision == ReviewDecision.reject
    )


_TR_UPPER, _TR_LOWER = "İIıÇĞÖŞÜÂâÎîÛû", "iiiçğöşüaaiiuu"


def fold_tr(text: str) -> str:
    """Turkish case-insensitive form for search: İ, I, ı and i are one letter, the other
    Turkish capitals go to their lowercase and the circumflex vowels (kâr, hâl) to the plain
    ones (the database's `lower` may know only ASCII)."""
    return text.translate(str.maketrans(_TR_UPPER, _TR_LOWER)).lower()


def statute_queue(
    band: Band | None = None,
    status: ListStatus = "pending",
    statute: str | None = None,
    q: str | None = None,
) -> Select[Any]:
    """The article queue: newest extraction of every article in `status` (`pending` = not live
    and not rejected, `approved` = live, `rejected`), filtered by band, statute number and a
    search in article number and margin heading, ordered by statute and `ordinal`. Rows carry
    `status` too."""
    newest = newest_statute_extractions()
    state = case(
        (_is_live(newest.c.id), "approved"),
        (_is_rejected(newest.c.id), "rejected"),
        else_="pending",
    )
    conditions: list[ColumnElement[bool]] = []
    if status != "all":
        conditions.append(state == status)
    if band:
        conditions.append(newest.c.band == band)
    if statute:
        conditions.append(newest.c.statute_number == statute)
    if q:
        folded = fold_tr(q)
        conditions.append(
            or_(
                *(
                    func.lower(func.translate(column, _TR_UPPER, _TR_LOWER)).contains(
                        folded, autoescape=True
                    )
                    for column in (newest.c.article_no, newest.c.heading)
                )
            )
        )
    return (
        select(*newest.c, state.label("status"))
        .where(*conditions)
        .order_by(newest.c.statute_number, newest.c.ordinal, newest.c.id)
    )


def unpublished_statute_articles(
    band: Band, statute: str | None = None, after: uuid.UUID | None = None
) -> Select[Any]:
    """Ids of the newest `statutes` extraction of every article that is in `band` and still
    pending (not live, not rejected; an older extraction of it may be live: publishing the newer
    one supersedes it), by id; `after` is the cursor of bulk runs: only greater ids."""
    pending = statute_queue(band, "pending", statute).subquery()
    stmt = select(pending.c.id).order_by(pending.c.id)
    return stmt if after is None else stmt.where(pending.c.id > after)


async def statute_article_status(
    session: AsyncSession, extraction: Extraction
) -> StatuteArticleStatus:
    """`approved` (live), `rejected`, `pending` (the newest of its article, neither) or
    `superseded` (a newer extraction of the article exists, or its rows were replaced)."""
    if await session.scalar(select(_is_live(extraction.id))):
        return "approved"
    if await session.scalar(select(_is_rejected(extraction.id))):
        return "rejected"
    return "pending" if await _is_newest_statute(session, extraction) else "superseded"


async def _is_newest_statute(session: AsyncSession, extraction: Extraction) -> bool:
    newest = (
        await session.execute(
            select(Extraction.id)
            .where(
                Extraction.parser_name == STATUTE_PARSER_NAME,
                Extraction.fields["statute_number"].as_string()
                == extraction.fields["statute_number"],
                Extraction.fields["article_no"].as_string() == extraction.fields["article_no"],
            )
            .order_by(Extraction.extracted_at.desc(), Extraction.id)
            .limit(1)
        )
    ).scalar_one()
    return newest == extraction.id


async def lock_pending_statute(
    session: AsyncSession, extraction_id: uuid.UUID, band: Band | None = None
) -> Extraction:
    """Lock the extraction row and check under it that it is still `pending` (see
    `statute_article_status`) and, if `band` is given, still in that band. Raises StaleExtraction
    otherwise (a rejected extraction is not publishable unless a newer one arrives) and
    ValueError when it is no statute article; the lock lasts to the end of the transaction."""
    extraction = (
        await session.execute(
            select(Extraction)
            .where(Extraction.id == extraction_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if extraction is None or extraction.parser_name != STATUTE_PARSER_NAME:
        raise ValueError("extraction is not a statute article")
    if (state := await statute_article_status(session, extraction)) != "pending":
        raise StaleExtraction(f"extraction is {state}")
    if band is not None and extraction.confidence["band"] != band:
        raise StaleExtraction(f"extraction is no longer in band {band}")
    return extraction


async def approve_statute_article(
    session: AsyncSession,
    extraction_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    band: Band | None = None,
    *,
    note: str | None = None,
    idempotent: bool = True,
) -> tuple[uuid.UUID, uuid.UUID]:
    """`review` row (approve, with `note`) + `publish_statute_article`, in a savepoint; returns
    (review_id, article_id). Raises ValueError (not publishable, unknown reviewer, overlapping
    versions) or StaleExtraction (see `lock_pending_statute`); the caller commits.

    `idempotent` (default): an extraction that is already live is a no-op, the review that
    published it and its article are returned and no review is added. `idempotent=False` (the
    API, where a second approval is a conflict): it is stale like any other non-pending one."""
    if idempotent:
        live = (
            await session.execute(
                select(StatuteArticleVersion.review_id, StatuteArticleVersion.article_id)
                .where(
                    StatuteArticleVersion.extraction_id == extraction_id,
                    StatuteArticleVersion.superseded_at.is_(None),
                    StatuteArticleVersion.review_id.is_not(None),
                )
                .limit(1)
            )
        ).first()
        if live is not None:
            return live.review_id, live.article_id
    try:
        async with session.begin_nested():
            await lock_pending_statute(session, extraction_id, band)
            review = Review(
                extraction_id=extraction_id,
                reviewer_id=reviewer_id,
                decision=ReviewDecision.approve,
                note=note,
            )
            session.add(review)
            await session.flush()
            article_id = await publish_statute_article(session, extraction_id, review.id)
    except IntegrityError as exc:
        raise ValueError(f"database constraint violated: {_violated_constraint(exc)}") from exc
    return review.id, article_id


async def reject_statute_article(
    session: AsyncSession, extraction_id: uuid.UUID, reviewer_id: uuid.UUID, note: str
) -> uuid.UUID:
    """`review` row (reject) in a savepoint; nothing is published and the source keeps its
    status (the statute is one source, the article the review unit). Returns the review id.
    Raises like `approve_statute_article`; the caller commits."""
    try:
        async with session.begin_nested():
            await lock_pending_statute(session, extraction_id)
            review = Review(
                extraction_id=extraction_id,
                reviewer_id=reviewer_id,
                decision=ReviewDecision.reject,
                note=note,
            )
            session.add(review)
            await session.flush()
    except IntegrityError as exc:
        raise ValueError(f"database constraint violated: {_violated_constraint(exc)}") from exc
    return review.id


async def publish_statute_batch(
    session: AsyncSession,
    extraction_ids: Sequence[uuid.UUID],
    reviewer_id: uuid.UUID,
    band: Band,
) -> BatchResult:
    """`publish_batch` of statute articles: each in its own savepoint, a record that is refused
    (stale, no longer in `band`, not publishable) goes to `failed`. The caller commits."""
    return await _run_batch(
        extraction_ids,
        lambda extraction_id: approve_statute_article(
            session, extraction_id, reviewer_id, band, idempotent=False
        ),
    )


def _covers(start: date | None, end: date | None, day: date) -> bool:
    return (start is None or start <= day) and (end is None or day < end)


def _version_dict(v: StatuteArticleVersion) -> dict[str, Any]:
    return {
        "text": v.text,
        "heading": v.heading,
        "valid_from": v.valid_from.isoformat(),
        "valid_to": v.valid_to.isoformat() if v.valid_to else None,
        "change_kind": v.change_kind.value,
        "amending_ref": v.amending_ref,
        "evidence": v.evidence,
        "footnotes": v.footnotes,
        "warnings": v.warnings,
        "confidence": v.confidence,
    }


async def statute_is_published(db: AsyncSession, number: str) -> bool:
    return (
        await db.execute(
            select(exists().where(Statute.kind == StatuteKind.kanun, Statute.number == number))
        )
    ).scalar_one()


async def article_as_of(
    db: AsyncSession, statute_no: str, article_no: str, as_of: date
) -> dict[str, Any]:
    """What a published article said on `as_of`; mirrors `hukuk_ingest.statutes.timeline.as_of`
    (same statuses, same fields, same order: versions first, then gaps), except that

    - only published data counts: no live version rows -> `{status: unknown_article, reason:
      "not_published"}`, whether the article is unknown or merely not approved yet;
    - `version.amending_ref` is the label of `format_amending_ref` (the notes themselves are in
      `version.evidence["amendments"]`).

    The gaps and `latest_snapshot_date` come from the extraction of the live versions. A `gap`
    result has no `version`, so it carries no article text."""
    versions = (
        (
            await db.execute(
                select(StatuteArticleVersion)
                .join(StatuteArticle, StatuteArticle.id == StatuteArticleVersion.article_id)
                .join(Statute, Statute.id == StatuteArticle.statute_id)
                .where(
                    Statute.kind == StatuteKind.kanun,
                    Statute.number == statute_no,
                    StatuteArticle.article_no == article_no,
                    StatuteArticleVersion.superseded_at.is_(None),
                )
                .order_by(StatuteArticleVersion.valid_from)
            )
        )
        .scalars()
        .all()
    )
    if not versions:
        return {"status": UNKNOWN_ARTICLE, "reason": "not_published"}
    latest, gaps = (
        await db.execute(
            select(
                Extraction.fields["latest_snapshot_date"].as_string(), Extraction.fields["gaps"]
            ).where(Extraction.id == versions[0].extraction_id)
        )
    ).one()
    base = {"latest_snapshot_date": latest, "stale": as_of > date.fromisoformat(latest)}
    for v in versions:
        if _covers(v.valid_from, v.valid_to, as_of):
            out = _version_dict(v)
            if v.change_kind is ChangeKind.repealed:
                return {"status": NOT_IN_FORCE, "reason": "repealed", "version": out, **base}
            return {"status": FOUND, "version": out, "confidence": v.confidence, **base}
    for g in gaps:
        start = date.fromisoformat(g["from"]) if g["from"] else None
        if _covers(start, date.fromisoformat(g["to"]), as_of):
            return {"status": GAP, "gap": g, **base}
    return {"status": NOT_IN_FORCE, **base}
