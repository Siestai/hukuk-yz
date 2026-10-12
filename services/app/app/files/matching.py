"""Matches of an uploaded file with the files already there (task 13a): the version it may
replace and the files that look like it. A match only suggests; nothing is linked here.

Candidates are found from the cheap fields (type + reference, title, file name) by a query that
compares the same normalised keys as `reason_for`; only the candidates are read, and only their
texts are compared, in Python (`hukuk_ingest.classify.similar`). A file without a stored text
(the archive decisions, loaded without a scan) is compared by its decision text."""

import asyncio
import string
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.files.import_dir import fold, name_key, stem_key
from app.files.store import FileStore
from app.models.common import DocumentType, Extraction, IngestFile
from app.models.decision import Decision
from hukuk_ingest.classify.similar import SIMILAR_THRESHOLD, containment, shingles

MAX_COMPARED = 20
MAX_SIMILAR = 5
# Reasons a file became a candidate, strongest first (they are the wire format of `matches`).
SAME_REF, SAME_TITLE, SAME_NAME = "same_ref", "same_title", "same_name"
_ORDER = (SAME_REF, SAME_TITLE, SAME_NAME)
# The letters `fold` maps, for the same folding in SQL.
Column = ColumnElement[Any] | InstrumentedAttribute[str | None]
_FROM = string.ascii_uppercase + "çğıöşüâîûÇĞİÖŞÜÂÎÛ"
_TO = string.ascii_lowercase + "cgiosuaiucgiosuaiu"


def ref_key(ref: str | None) -> str:
    """A reference without case, accents, spaces and punctuation: `2024/5` and `2024-5` agree."""
    return "".join(c for c in fold(ref or "") if c.isalnum())


def _sql_fold(column: Column) -> ColumnElement[str]:
    """`fold` in SQL, for the letters of Turkish text: no combining marks, no case, no accents."""
    return func.translate(func.regexp_replace(column, "[\\u0300-\\u036f]", "", "g"), _FROM, _TO)


def _sql_name_key(column: Column) -> ColumnElement[str]:
    return func.trim(func.regexp_replace(_sql_fold(column), "[^a-z0-9]+", " ", "g"))


def _sql_stem_key(column: Column) -> ColumnElement[str]:
    return _sql_name_key(func.regexp_replace(column, "\\.[^./]*$", ""))


@dataclass(frozen=True)
class Subject:
    """The file being matched, with the best values known for it (its own fields, else the
    suggestions). `doc_types` holds the type the user gave and the one the rules detected: a
    wrong guess of the user must not hide the file it duplicates."""

    id: uuid.UUID
    supersedes_id: uuid.UUID | None
    doc_types: frozenset[str]
    official_ref: str | None
    title: str | None
    name: str | None


@dataclass(frozen=True)
class Row:
    id: uuid.UUID
    original_name: str | None
    title: str | None
    doc_type: str | None
    official_ref: str | None
    uploaded_at: datetime
    text_key: str | None


def reason_for(subject: Subject, row: Row) -> str | None:
    """Why `row` is a candidate for `subject`, the strongest reason, or None."""
    same_type = row.doc_type is not None and row.doc_type in subject.doc_types
    if same_type and (key := ref_key(subject.official_ref)) and key == ref_key(row.official_ref):
        return SAME_REF
    if (key := name_key(subject.title or "")) and key in (
        name_key(row.title or ""),
        stem_key(row.original_name or ""),
    ):
        return SAME_TITLE
    if (key := stem_key(subject.name or "")) and key in (
        stem_key(row.original_name or ""),
        name_key(row.title or ""),
    ):
        return SAME_NAME
    return None


async def _ancestors(db: AsyncSession, start: uuid.UUID | None) -> set[uuid.UUID]:
    """`start` and the files it supersedes, one lookup per step."""
    seen: set[uuid.UUID] = set()
    while start is not None and start not in seen:
        seen.add(start)
        start = (
            await db.execute(select(IngestFile.supersedes_id).where(IngestFile.id == start))
        ).scalar_one_or_none()
    return seen


async def _newest_version(db: AsyncSession, first: uuid.UUID) -> uuid.UUID:
    """The newest not archived file of the chain `first` belongs to (`first` itself when no
    newer one is usable), one lookup per step."""
    best, current, seen = first, first, {first}
    while (
        step := (
            await db.execute(
                select(IngestFile.id, IngestFile.archived_at).where(
                    IngestFile.supersedes_id == current
                )
            )
        ).first()
    ) is not None and step[0] not in seen:
        current = step[0]
        seen.add(current)
        if step[1] is None:
            best = current
    return best


def _ranked(rows: dict[uuid.UUID, Row], reasons: dict[uuid.UUID, str]) -> list[uuid.UUID]:
    """Candidates by the strongest reason, then the newest upload."""
    return sorted(
        reasons, key=lambda rid: (_ORDER.index(reasons[rid]), -rows[rid].uploaded_at.timestamp())
    )


async def previous_version(
    db: AsyncSession,
    subject: Subject,
    rows: dict[uuid.UUID, Row],
    reasons: dict[uuid.UUID, str],
) -> dict[str, Any] | None:
    """The file `subject` may be the next version of: the strongest candidate, then the newest
    of its chain. None when the user already chose a previous version."""
    if subject.supersedes_id is not None or not reasons:
        return None
    first = _ranked(rows, reasons)[0]
    return {"file_id": str(await _newest_version(db, first)), "reason": reasons[first]}


def _read_text(store: FileStore, key: str) -> str | None:
    try:
        with store.open(key) as fh:
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None


def similar_files(
    store: FileStore,
    text: str,
    rows: dict[uuid.UUID, Row],
    reasons: dict[uuid.UUID, str],
    fallback: dict[uuid.UUID, str],
) -> list[dict[str, Any]]:
    """Candidates whose text scores at `SIMILAR_THRESHOLD` or more against `text`, best first.
    The text is the stored one, else the `fallback` one. Reads the candidates' texts: runs in
    a thread."""
    mine = shingles(text)
    ranked = [rid for rid in _ranked(rows, reasons) if rows[rid].text_key or rid in fallback]
    found: list[dict[str, Any]] = []
    for rid in ranked[:MAX_COMPARED]:
        key = rows[rid].text_key
        other = _read_text(store, key) if key else fallback.get(rid)
        if other is None:
            continue
        score = containment(mine, shingles(other))
        if score >= SIMILAR_THRESHOLD:
            found.append({"file_id": str(rid), "score": round(score, 2), "reason": reasons[rid]})
    found.sort(key=lambda m: -m["score"])
    return found[:MAX_SIMILAR]


async def _decision_texts(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """The texts of files that have none in the store, in one query: the live decision of the
    file's source. A decision not yet reviewed exists only in the extraction's `fields`, which
    is read for those files alone (`coalesce` skips it when the decision has a text)."""
    if not ids:
        return {}
    result = await db.execute(
        select(
            Extraction.file_id,
            func.coalesce(Decision.full_text, Extraction.fields["full_text"].astext),
        )
        .ext(distinct_on(Extraction.file_id))
        .outerjoin(
            Decision,
            and_(Decision.source_id == Extraction.source_id, Decision.superseded_at.is_(None)),
        )
        .where(Extraction.file_id.in_(ids))
        .order_by(Extraction.file_id, Extraction.extracted_at.desc())
    )
    return {file_id: text for file_id, text in result.all() if text}


async def _candidates(
    db: AsyncSession, subject: Subject, exclude: set[uuid.UUID]
) -> dict[uuid.UUID, Row]:
    """The stored, not archived files that may share type + reference, title or name with
    `subject`: a query on the same keys as `reason_for` (a superset of its matches for the
    letters of Turkish text), then `reason_for` decides."""
    keys = {k for k in (name_key(subject.title or ""), stem_key(subject.name or "")) if k}
    conditions: list[ColumnElement[bool]] = []
    if keys:
        conditions += [
            _sql_name_key(IngestFile.title).in_(keys),
            _sql_stem_key(IngestFile.original_name).in_(keys),
        ]
    if (ref := ref_key(subject.official_ref)) and subject.doc_types:
        conditions.append(
            and_(
                IngestFile.doc_type.in_([DocumentType(t) for t in subject.doc_types]),
                func.regexp_replace(_sql_fold(IngestFile.official_ref), "[^a-z0-9]+", "", "g")
                == ref,
            )
        )
    if not conditions:
        return {}
    result = await db.execute(
        select(
            IngestFile.id,
            IngestFile.original_name,
            IngestFile.title,
            IngestFile.doc_type,
            IngestFile.official_ref,
            IngestFile.uploaded_at,
            IngestFile.scan_result["text_key"].astext,
        ).where(
            IngestFile.storage_key.is_not(None),
            IngestFile.archived_at.is_(None),
            IngestFile.id.not_in(exclude),
            or_(*conditions),
        )
    )
    return {
        r[0]: Row(r[0], r[1], r[2], r[3].value if r[3] else None, r[4], r[5], r[6])
        for r in result.all()
    }


async def compute_matches(
    db: AsyncSession, store: FileStore, subject: Subject, text: str
) -> dict[str, Any]:
    """`{"previous_version": {...} | None, "similar": [...]}` for `subject`, whose extracted
    text is `text`."""
    own = await _ancestors(db, subject.supersedes_id) | {subject.id}
    rows = await _candidates(db, subject, own)
    reasons = {rid: reason for rid, row in rows.items() if (reason := reason_for(subject, row))}
    missing = [rid for rid in _ranked(rows, reasons) if not rows[rid].text_key][:MAX_COMPARED]
    fallback = await _decision_texts(db, missing)
    similar = await asyncio.to_thread(similar_files, store, text, rows, reasons, fallback)
    return {
        "previous_version": await previous_version(db, subject, rows, reasons),
        "similar": similar,
    }
