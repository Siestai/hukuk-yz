"""The search index in the database (task 14, data-model.md §8): which chunks a record has, kept
in step with its review state, and their embeddings.

A record's chunks are a function of its state, so one call rebuilds them all (`sync_decision`,
`sync_statute_article`): an approved record is indexed from its typed row, one waiting for review
from its newest extraction, a rejected or reopened-and-rejected one not at all. The review paths
(`app.kb`) call these inside their transaction; they write text and full-text search only. The
embedding (a network call) is `embed_pending`, run by `python -m app.loaders.chunks`; a chunk
whose embedding input and model are unchanged keeps its vector across a rebuild.
"""

import uuid
from collections.abc import Sequence
from dataclasses import astuple, dataclass, fields
from datetime import date
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings import Embedder
from app.models.chunk import Chunk
from app.models.common import (
    PARSER_NAME,
    STATUTE_PARSER_NAME,
    ChangeKind,
    ChunkKind,
    CourtLevel,
    Extraction,
    License,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
    SourceCategory,
    StatuteKind,
)
from app.models.decision import Decision
from app.models.statute import Statute, StatuteArticle, StatuteArticleVersion
from hukuk_ingest.index.chunking import (
    EDITORIAL_SUMMARY,
    ChunkDraft,
    article_label,
    chunk_article,
    chunk_decision,
    content_hash,
    decision_header,
    embedding_input,
    estimate_tokens,
    statute_header,
)

# `chunk.parent_kind` values; the review status of a result follows from it.
DECISION = "decision"
STATUTE_ARTICLE = "statute_article"
EXTRACTION = "extraction"
APPROVED_PARENTS = (DECISION, STATUTE_ARTICLE)

INDEXED_STATUSES = (RecordStatus.analyzed, RecordStatus.approved, RecordStatus.published)
# Texts per embedding request, and the most (estimated) tokens in one; the API takes 8.191 per
# input and 300.000 per request.
EMBED_BATCH = 64
EMBED_BATCH_TOKENS = 60_000


@dataclass(frozen=True)
class Row:
    """A chunk to store: `Chunk` without id, embedding and tsv (the trigger's)."""

    source_id: uuid.UUID
    category: SourceCategory
    parent_kind: str
    parent_id: uuid.UUID
    version_id: uuid.UUID | None
    kind: ChunkKind
    license: License
    ordinal: int
    char_start: int
    char_end: int
    header: str
    text: str
    text_hash: str
    title: str
    ref: str | None
    court_level: CourtLevel | None
    doc_date: date | None
    valid_from: date | None
    valid_to: date | None


def _chunks(drafts: Sequence[ChunkDraft], source: Source, **common: Any) -> list[Row]:
    """The editorial summary is `internal_only`; a body chunk has the license of its source."""
    return [
        Row(
            kind=ChunkKind(d.kind),
            license=License.internal_only if d.kind == EDITORIAL_SUMMARY else source.license,
            ordinal=d.ordinal,
            char_start=d.char_start,
            char_end=d.char_end,
            header=d.header,
            text=d.text,
            text_hash=content_hash(d.header, d.text),
            **common,
        )
        for d in drafts
    ]


def _decision_rows(
    source: Source, parent_kind: str, parent_id: uuid.UUID, f: dict[str, Any]
) -> list[Row]:
    """`f`: the decision fields, from a `Decision` row or an extraction's `fields`."""
    header = decision_header(
        source.official_ref or source.title, f["related_articles"] or [], f["keywords"] or []
    )
    # A `summary_only` record has no text of the court's own: its `full_text` is the journal's
    # summary, which is licensed apart (editorial_summary chunk), so there is no body to index.
    drafts = chunk_decision(
        f["full_text"] or "",
        f["editorial_summary"] or "",
        header,
        body=f["text_completeness"] != "summary_only",
    )
    return _chunks(
        drafts,
        source,
        source_id=source.id,
        category=source.category,
        parent_kind=parent_kind,
        parent_id=parent_id,
        version_id=None,
        title=source.title,
        ref=source.official_ref,
        court_level=CourtLevel(f["court_level"]) if f["court_level"] else None,
        doc_date=f["decision_date"],
        valid_from=None,
        valid_to=None,
    )


def _decision_fields_of_row(d: Decision) -> dict[str, Any]:
    return {
        "court_level": d.court_level.value,
        "decision_date": d.decision_date,
        "related_articles": d.related_articles,
        "keywords": d.keywords,
        "full_text": d.full_text,
        "editorial_summary": d.editorial_summary,
        "text_completeness": d.text_completeness.value,
    }


def _decision_fields_of_extraction(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        **fields,
        "decision_date": date.fromisoformat(fields["decision_date"])
        if fields["decision_date"]
        else None,
    }


async def decision_rows(session: AsyncSession, source_id: uuid.UUID) -> list[Row]:
    """The chunks a decision source should have now (none for a rejected or unreadable one)."""
    source = await session.get(Source, source_id)
    if source is None or source.category is not SourceCategory.decision:
        return []
    if source.status not in INDEXED_STATUSES:
        return []
    live = (
        await session.execute(
            select(Decision).where(
                Decision.source_id == source_id, Decision.superseded_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if live is not None:
        return _decision_rows(source, DECISION, live.id, _decision_fields_of_row(live))
    if source.status is not RecordStatus.analyzed:
        return []
    newest = (
        await session.execute(
            select(Extraction)
            .where(Extraction.source_id == source_id, Extraction.parser_name == PARSER_NAME)
            .order_by(Extraction.extracted_at.desc(), Extraction.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if newest is None:
        return []
    return _decision_rows(
        source, EXTRACTION, newest.id, _decision_fields_of_extraction(newest.fields)
    )


def _article_rows(
    source: Source,
    number: str,
    article_no: str,
    parent_kind: str,
    parent_id: uuid.UUID,
    versions: Sequence[tuple[uuid.UUID | None, str, str | None, date, date | None, str]],
) -> list[Row]:
    """`versions`: (version id, text, heading, valid_from, valid_to, change_kind) per version."""
    rows: list[Row] = []
    for version_id, text, heading, valid_from, valid_to, change_kind in versions:
        if change_kind == ChangeKind.repealed.value:  # no operative text: the article is gone
            continue
        header = statute_header(number, article_no, heading, valid_from.isoformat())
        title = f"{source.title} {article_label(article_no)}" + (f" · {heading}" if heading else "")
        rows += _chunks(
            chunk_article(text, header),
            source,
            source_id=source.id,
            category=source.category,
            parent_kind=parent_kind,
            parent_id=parent_id,
            version_id=version_id,
            title=title,
            ref=f"{number} {article_label(article_no)}",
            court_level=None,
            doc_date=None,
            valid_from=valid_from,
            valid_to=valid_to,
        )
    return rows


def _article_extractions(number: str, article_no: str) -> Any:
    return select(Extraction).where(
        Extraction.parser_name == STATUTE_PARSER_NAME,
        Extraction.fields["statute_number"].as_string() == number,
        Extraction.fields["article_no"].as_string() == article_no,
    )


async def statute_article_rows(session: AsyncSession, number: str, article_no: str) -> list[Row]:
    """The chunks an article should have now: its live versions when it is published, else the
    versions of its newest extraction unless a reviewer rejected that one. The `gaps` of a
    timeline have no text and no chunk."""
    live = (
        await session.execute(
            select(StatuteArticleVersion, StatuteArticle.id, Source)
            .join(StatuteArticle, StatuteArticle.id == StatuteArticleVersion.article_id)
            .join(Statute, Statute.id == StatuteArticle.statute_id)
            .join(Source, Source.id == StatuteArticleVersion.source_id)
            .where(
                Statute.kind == StatuteKind.kanun,
                Statute.number == number,
                StatuteArticle.article_no == article_no,
                StatuteArticleVersion.superseded_at.is_(None),
            )
            .order_by(StatuteArticleVersion.valid_from)
        )
    ).all()
    if live:
        return _article_rows(
            live[0].Source,
            number,
            article_no,
            STATUTE_ARTICLE,
            live[0].id,
            [
                (
                    v.id,
                    v.text,
                    v.heading,
                    v.valid_from,
                    v.valid_to,
                    v.change_kind.value,
                )
                for v, _, _ in live
            ],
        )
    newest = (
        await session.execute(
            _article_extractions(number, article_no)
            .order_by(Extraction.extracted_at.desc(), Extraction.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if newest is None or newest.source_id is None:
        return []
    rejected = (
        await session.execute(
            select(func.count()).where(
                Review.extraction_id == newest.id, Review.decision == ReviewDecision.reject
            )
        )
    ).scalar_one()
    source = await session.get(Source, newest.source_id)
    if rejected or source is None:
        return []
    return _article_rows(
        source,
        number,
        article_no,
        EXTRACTION,
        newest.id,
        [
            (
                None,
                v["text"],
                v["heading"],
                date.fromisoformat(v["valid_from"]),
                date.fromisoformat(v["valid_to"]) if v["valid_to"] else None,
                v["change_kind"],
            )
            for v in newest.fields["versions"]
            if v["valid_from"]
        ],
    )


def review_status(parent_kind: str) -> str:
    """The review status a result carries: "approved", or "analyzed" for a record that no
    reviewer has approved yet (its chunks are built from the extraction)."""
    return "approved" if parent_kind in APPROVED_PARENTS else "analyzed"


@dataclass
class SyncResult:
    """The chunks a record should have, and what the sync did: `written` when they changed,
    `reused` of them kept a vector, `unembedded` of them still wait for one."""

    rows: list[Row]
    written: bool = False
    reused: int = 0
    unembedded: int = 0


async def _replace(session: AsyncSession, existing_where: Any, rows: list[Row]) -> SyncResult:
    """Make the stored chunks selected by `existing_where` equal `rows`: nothing is touched when
    they already are; otherwise they are deleted and written again, and a chunk keeps the vector
    of an old one with the same embedding input and model (`text_hash`)."""
    stored = (await session.execute(select(Chunk).where(existing_where))).scalars().all()
    columns = [f.name for f in fields(Row)]
    if {astuple(r) for r in rows} == {tuple(getattr(c, f) for f in columns) for c in stored}:
        return SyncResult(rows, unembedded=sum(1 for c in stored if c.embedding is None))
    vectors = {
        c.text_hash: (c.embedding, c.embedding_model) for c in stored if c.embedding is not None
    }
    if stored:
        await session.execute(delete(Chunk).where(existing_where))
    reused = 0
    for row in rows:
        values = {f: getattr(row, f) for f in columns}
        chunk = Chunk(**values)
        if row.text_hash in vectors:
            chunk.embedding, chunk.embedding_model = vectors[row.text_hash]
            reused += 1
        session.add(chunk)
    await session.flush()
    return SyncResult(rows, True, reused, len(rows) - reused)


async def sync_decision(session: AsyncSession, source_id: uuid.UUID) -> SyncResult:
    """Rebuild the chunks of a decision source; the caller commits."""
    return await _replace(
        session, Chunk.source_id == source_id, await decision_rows(session, source_id)
    )


async def sync_statute_article(session: AsyncSession, number: str, article_no: str) -> SyncResult:
    """Rebuild the chunks of one article (its live versions and its extractions); the caller
    commits."""
    ids = (
        (
            await session.execute(
                _article_extractions(number, article_no).with_only_columns(Extraction.id)
            )
        )
        .scalars()
        .all()
    )
    article_ids = (
        (
            await session.execute(
                select(StatuteArticle.id)
                .join(Statute, Statute.id == StatuteArticle.statute_id)
                .where(
                    Statute.kind == StatuteKind.kanun,
                    Statute.number == number,
                    StatuteArticle.article_no == article_no,
                )
            )
        )
        .scalars()
        .all()
    )
    where = or_(
        (Chunk.parent_kind == EXTRACTION) & Chunk.parent_id.in_(ids),
        (Chunk.parent_kind == STATUTE_ARTICLE) & Chunk.parent_id.in_(article_ids),
    )
    return await _replace(session, where, await statute_article_rows(session, number, article_no))


async def sync_extraction(session: AsyncSession, extraction_id: uuid.UUID) -> None:
    """Rebuild the chunks of the record an extraction belongs to (after its review)."""
    extraction = await session.get(Extraction, extraction_id)
    if extraction is None or extraction.source_id is None:
        return
    if extraction.parser_name == PARSER_NAME:
        await sync_decision(session, extraction.source_id)
    elif extraction.parser_name == STATUTE_PARSER_NAME:
        await sync_statute_article(
            session, extraction.fields["statute_number"], extraction.fields["article_no"]
        )


@dataclass
class EmbedReport:
    chunks: int = 0
    tokens: int = 0
    failed: int = 0


async def embed_pending(
    session: AsyncSession, embedder: Embedder, *, source_ids: Sequence[uuid.UUID] | None = None
) -> EmbedReport:
    """Embed the chunks (of `source_ids`, if given) that have no vector of the current model, in
    batches, committing after each; a batch that fails is counted and left for the next run."""
    report = EmbedReport()
    pending = (
        select(Chunk.id, Chunk.header, Chunk.text)
        .where(Chunk.embedding.is_(None) | (Chunk.embedding_model != embedder.model_id))
        .order_by(Chunk.id)
    )
    if source_ids is not None:
        pending = pending.where(Chunk.source_id.in_(source_ids))
    todo = (await session.execute(pending)).all()
    batch: list[tuple[uuid.UUID, str]] = []
    batch_tokens = 0

    async def flush() -> None:
        nonlocal batch, batch_tokens
        if not batch:
            return
        try:
            result = await embedder.embed([text for _, text in batch])
        except Exception as error:  # the client has retried already: report, go on
            report.failed += len(batch)
            print(f"embedding batch failed: {type(error).__name__}: {error}")
        else:
            await session.execute(
                update(Chunk),
                [
                    {"id": chunk_id, "embedding": vector, "embedding_model": embedder.model_id}
                    for (chunk_id, _), vector in zip(batch, result.vectors, strict=True)
                ],
            )
            await session.commit()
            report.chunks += len(batch)
            report.tokens += result.tokens
        batch, batch_tokens = [], 0

    for chunk_id, header, text in todo:
        content = embedding_input(header or "", text)
        tokens = estimate_tokens(content)
        if batch and (len(batch) >= EMBED_BATCH or batch_tokens + tokens > EMBED_BATCH_TOKENS):
            await flush()
        batch.append((chunk_id, content))
        batch_tokens += tokens
    await flush()
    return report
