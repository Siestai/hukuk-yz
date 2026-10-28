"""Hybrid search over the chunk index (task 14, data-model.md §7-§8): `GET /kb/search`.

Two rankings of chunks (Turkish full-text search with unaccent, and cosine distance to the
query's embedding, HNSW) are merged by reciprocal rank fusion, weighted lightly by court level
and source rank, and grouped into records: a record scores as its best chunk. What is searched:

- `rejected` sources never; records no reviewer has approved (chunks of an `extraction`) only
  while `KB_SEARCH_INCLUDE_UNREVIEWED` is on, and then labelled `analyzed`;
- `as_of`: a statute version in force on that day (`valid_from <= as_of < valid_to`; a `gap` has
  no chunk, so a day in a gap finds no version) and decisions dated on or before it (a decision
  without a date is not dated "before" anything and is left out);
- `date_from` / `date_to` bound the decision date; statute versions are not affected by them.

A chunk with license `internal_only` (the journal's editorial summary) is matched but never
returned: the record's own text is shown instead.
"""

import logging
import re
import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import ColumnElement, and_, func, literal_column, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Db, current_user
from app.chunk_index import APPROVED_PARENTS, EXTRACTION, INDEXED_STATUSES, review_status
from app.embeddings import Embedder, get_embedder
from app.models.chunk import Chunk
from app.models.common import ChunkKind, License, Source, SourceCategory
from app.models.decision import Decision
from app.settings import Settings, get_settings
from hukuk_ingest.index.rrf import Scored, authority_weight, group_by_record, rrf
from hukuk_models import KbCategory, KbCourtLevel, KbSearchMatch, KbSearchResponse, KbSearchResult

logger = logging.getLogger("app")

router = APIRouter(prefix="/kb", tags=["kb"], dependencies=[Depends(current_user)])

MATCHES_PER_RECORD = 3
# Candidates per ranking: enough records after grouping, never more than the HNSW scan returns
# (`hnsw.ef_search`).
EF_SEARCH = 200
_TOKEN_RE = re.compile(r"\w{3,}")
_MAX_TOKENS = 16


def _tsquery(q: str) -> str:
    """The words of the question joined by OR: a natural-language question rarely has all its
    words in one passage, so the ranking (not the match) separates good from poor."""
    return " | ".join(dict.fromkeys(_TOKEN_RE.findall(q.lower())[:_MAX_TOKENS]))


def _filters(
    *,
    include_unreviewed: bool,
    categories: list[str] | None,
    as_of: date | None,
    court_level: str | None,
    date_from: date | None,
    date_to: date | None,
) -> list[ColumnElement[bool]]:
    parents = [*APPROVED_PARENTS, EXTRACTION] if include_unreviewed else list(APPROVED_PARENTS)
    is_decision = Chunk.category == SourceCategory.decision
    conditions: list[ColumnElement[bool]] = [
        Source.status.in_(INDEXED_STATUSES),
        Chunk.parent_kind.in_(parents),
    ]
    if categories:
        conditions.append(Chunk.category.in_([SourceCategory(c) for c in categories]))
    if court_level:
        conditions.append(Chunk.court_level == court_level)
    if as_of:
        conditions.append(
            or_(
                and_(is_decision, Chunk.doc_date <= as_of),
                and_(
                    ~is_decision,
                    Chunk.valid_from <= as_of,
                    or_(Chunk.valid_to.is_(None), Chunk.valid_to > as_of),
                ),
            )
        )
    if date_from:
        conditions.append(or_(~is_decision, Chunk.doc_date >= date_from))
    if date_to:
        conditions.append(or_(~is_decision, Chunk.doc_date <= date_to))
    return conditions


async def _fulltext_ranking(
    db: AsyncSession, q: str, conditions: list[ColumnElement[bool]], limit: int
) -> list[uuid.UUID]:
    tokens = _tsquery(q)
    if not tokens:
        return []
    query = func.to_tsquery(literal_column("'turkish_unaccent'"), tokens)
    rows = await db.execute(
        select(Chunk.id)
        .join(Source, Source.id == Chunk.source_id)
        .where(*conditions, Chunk.tsv.op("@@")(query))
        .order_by(func.ts_rank_cd(Chunk.tsv, query).desc(), Chunk.id)
        .limit(limit)
    )
    return list(rows.scalars())


async def _vector_ranking(
    db: AsyncSession,
    vector: list[float],
    model_id: str,
    conditions: list[ColumnElement[bool]],
    limit: int,
) -> list[uuid.UUID]:
    # Per transaction: how many neighbours the HNSW scan collects before the filters apply.
    await db.execute(text(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}"))
    rows = await db.execute(
        select(Chunk.id)
        .join(Source, Source.id == Chunk.source_id)
        .where(*conditions, Chunk.embedding_model == model_id)
        .order_by(Chunk.embedding.cosine_distance(vector), Chunk.id)
        .limit(limit)
    )
    return list(rows.scalars())


async def _embed_query(embedder: Embedder | None, q: str) -> list[float] | None:
    if embedder is None:
        return None
    try:
        return (await embedder.embed([q])).vectors[0]
    except Exception:  # the search stays up on the text index alone; `mode` says so
        logger.warning("query embedding failed, searching full text only", exc_info=True)
        return None


def _record_key(chunk: Chunk) -> tuple[Any, ...]:
    return (chunk.source_id, chunk.parent_id, chunk.version_id, chunk.valid_from)


async def search(
    db: AsyncSession,
    embedder: Embedder | None,
    *,
    q: str,
    include_unreviewed: bool,
    categories: list[str] | None = None,
    as_of: date | None = None,
    court_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 10,
) -> KbSearchResponse:
    conditions = _filters(
        include_unreviewed=include_unreviewed,
        categories=categories,
        as_of=as_of,
        court_level=court_level,
        date_from=date_from,
        date_to=date_to,
    )
    candidates = min(max(limit * 4, 50), EF_SEARCH)
    vector = await _embed_query(embedder, q) if q.strip() else None
    rankings = [await _fulltext_ranking(db, q, conditions, candidates)]
    if vector is not None and embedder is not None:
        rankings.append(
            await _vector_ranking(db, vector, embedder.model_id, conditions, candidates)
        )
    fused = rrf(rankings)
    mode = "hybrid" if vector is not None else "fulltext"
    if not fused:
        return KbSearchResponse(mode=mode, results=[])

    found = (
        await db.execute(
            select(Chunk, Source.source_rank, Decision.verification)
            .join(Source, Source.id == Chunk.source_id)
            .outerjoin(
                Decision, and_(Chunk.parent_kind == "decision", Decision.id == Chunk.parent_id)
            )
            .where(Chunk.id.in_([i for i in fused if isinstance(i, uuid.UUID)]))
        )
    ).all()
    chunks = {c.id: c for c, _, _ in found}
    extras = {c.id: (rank, verification) for c, rank, verification in found}
    scored = [
        Scored(
            str(c.id),
            _record_key(c),
            fused[c.id]
            * authority_weight(
                c.court_level.value if c.court_level else None, extras[c.id][0].value
            ),
        )
        for c in chunks.values()
    ]
    grouped = group_by_record(scored)[:limit]

    results: list[KbSearchResult] = []
    bodyless: list[tuple[Any, ...]] = []
    for record, score, chunk_ids in grouped:
        best = chunks[uuid.UUID(chunk_ids[0])]
        shown = [
            chunks[uuid.UUID(i)]
            for i in chunk_ids
            if chunks[uuid.UUID(i)].license is not License.internal_only
        ][:MATCHES_PER_RECORD]
        if not shown:
            bodyless.append(record)
        verification = extras[best.id][1]
        results.append(
            KbSearchResult(
                source_id=best.source_id,
                parent_id=best.parent_id,
                version_id=best.version_id,
                category=best.category.value,
                title=best.title,
                ref=best.ref,
                review_status=review_status(best.parent_kind),
                verification=verification.value if verification else None,
                valid_from=best.valid_from,
                valid_to=best.valid_to,
                score=score,
                matches=[_match(c) for c in shown],
            )
        )
    if bodyless:
        await _opening_chunks(db, results, bodyless, chunks)
    return KbSearchResponse(mode=mode, results=results)


def _match(chunk: Chunk) -> KbSearchMatch:
    return KbSearchMatch(
        chunk_id=chunk.id, text=chunk.text, char_start=chunk.char_start, char_end=chunk.char_end
    )


async def _opening_chunks(
    db: AsyncSession,
    results: list[KbSearchResult],
    records: list[tuple[Any, ...]],
    chunks: dict[uuid.UUID, Chunk],
) -> None:
    """A record found only through its editorial summary is shown by the first chunk of its own
    text (if it has one)."""
    first: dict[tuple[Any, ...], Chunk] = {}
    rows = await db.execute(
        select(Chunk)
        .where(
            Chunk.parent_id.in_([r[1] for r in records]),
            Chunk.kind == ChunkKind.body,
            Chunk.license != License.internal_only,
        )
        .order_by(Chunk.ordinal)
    )
    for chunk in rows.scalars():
        first.setdefault(_record_key(chunk), chunk)
    for result in results:
        if result.matches:
            continue
        key = (result.source_id, result.parent_id, result.version_id, result.valid_from)
        if key in first:
            result.matches = [_match(first[key])]


@router.get("/search")
async def kb_search(
    q: Annotated[str, Query(min_length=1, max_length=1000)],
    db: Db,
    settings: Annotated[Settings, Depends(get_settings)],
    embedder: Annotated[Embedder | None, Depends(get_embedder)],
    category: Annotated[list[KbCategory] | None, Query()] = None,
    as_of: date | None = None,
    court_level: KbCourtLevel | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> KbSearchResponse:
    return await search(
        db,
        embedder,
        q=q,
        include_unreviewed=settings.kb_search_include_unreviewed,
        categories=list(category) if category else None,
        as_of=as_of,
        court_level=court_level,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
