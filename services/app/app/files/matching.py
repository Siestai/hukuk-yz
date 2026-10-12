"""Matches of an uploaded file with the files already there (task 13a): the version it may
replace and the files that look like it. A match only suggests; nothing is linked here.

Candidates are found from the cheap fields (type + reference, title, file name, type + date, and
for decisions the Esas / Karar numbers of the archive), the text is compared only for them, in
Python (`hukuk_ingest.classify.similar`)."""

import asyncio
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.files.import_dir import fold, name_key, stem_key
from app.files.store import FileStore
from app.kb import PARSER_NAME
from app.models.common import Extraction, IngestFile, ReviewStatus
from hukuk_ingest.classify.similar import SIMILAR_THRESHOLD, containment, shingles

MAX_COMPARED = 20
MAX_SIMILAR = 5
# Reasons a file became a candidate, strongest first (they are the wire format of `matches`).
SAME_CASE, SAME_REF, SAME_TITLE, SAME_NAME, SAME_DATE = (
    "same_case",
    "same_ref",
    "same_title",
    "same_name",
    "same_date",
)
_ORDER = (SAME_CASE, SAME_REF, SAME_TITLE, SAME_NAME, SAME_DATE)
_VERSION_REASONS = frozenset(_ORDER[:4])
_CASE_RE = re.compile(r"(\d{4}/\d+)\s*E\.?.*?(\d{4}/\d+)\s*K\.?")


def ref_key(ref: str | None) -> str:
    """A reference without case, accents, spaces and punctuation: `2024/5` and `2024-5` agree."""
    return "".join(c for c in fold(ref or "") if c.isalnum())


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
    doc_date: date | None


@dataclass(frozen=True)
class Row:
    id: uuid.UUID
    supersedes_id: uuid.UUID | None
    original_name: str | None
    title: str | None
    doc_type: str | None
    official_ref: str | None
    doc_date: date | None
    uploaded_at: datetime
    archived: bool
    approved: bool
    text_key: str | None


def reason_for(subject: Subject, row: Row, same_case: bool = False) -> str | None:
    """Why `row` is a candidate for `subject`, the strongest reason, or None."""
    if same_case:
        return SAME_CASE
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
    if same_type and subject.doc_date is not None and subject.doc_date == row.doc_date:
        return SAME_DATE
    return None


def _chain_ids(rows: dict[uuid.UUID, Row], start: uuid.UUID | None) -> set[uuid.UUID]:
    seen: set[uuid.UUID] = set()
    while start is not None and start in rows and start not in seen:
        seen.add(start)
        start = rows[start].supersedes_id
    return seen


def newest_version(rows: dict[uuid.UUID, Row], first: Row) -> Row | None:
    """The newest approved, not archived file of the chain `first` belongs to."""
    next_of = {r.supersedes_id: r for r in rows.values() if r.supersedes_id is not None}
    best = first if first.approved and not first.archived else None
    current, seen = first, {first.id}
    while (successor := next_of.get(current.id)) is not None and successor.id not in seen:
        seen.add(successor.id)
        current = successor
        if current.approved and not current.archived:
            best = current
    return best


def previous_version(
    subject: Subject, rows: dict[uuid.UUID, Row], reasons: dict[uuid.UUID, str]
) -> dict[str, Any] | None:
    """The file `subject` may be the next version of: the strongest candidate, then the newest
    of its chain. None when the user already chose a previous version."""
    if subject.supersedes_id is not None:
        return None
    own = _chain_ids(rows, subject.id)
    ranked = sorted(
        (
            (_ORDER.index(reason), -row.uploaded_at.timestamp(), row)
            for rid, reason in reasons.items()
            if reason in _VERSION_REASONS and rid not in own and (row := rows[rid]).approved
        ),
        key=lambda item: item[:2],
    )
    for _, _, row in ranked:
        if (newest := newest_version(rows, row)) is not None:
            return {"file_id": str(newest.id), "reason": reasons[row.id]}
    return None


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
    exclude: set[uuid.UUID],
) -> list[dict[str, Any]]:
    """Candidates whose text scores at `SIMILAR_THRESHOLD` or more against `text`, best first.
    Reads the candidates' texts: runs in a thread."""
    mine = shingles(text)
    ranked = sorted(
        (rid for rid in reasons if rid not in exclude and rows[rid].text_key),
        key=lambda rid: (_ORDER.index(reasons[rid]), -rows[rid].uploaded_at.timestamp()),
    )[:MAX_COMPARED]
    found: list[dict[str, Any]] = []
    for rid in ranked:
        key = rows[rid].text_key
        other = _read_text(store, key) if key else None
        if other is None:
            continue
        score = containment(mine, shingles(other))
        if score >= SIMILAR_THRESHOLD:
            found.append({"file_id": str(rid), "score": round(score, 2), "reason": reasons[rid]})
    found.sort(key=lambda m: -m["score"])
    return found[:MAX_SIMILAR]


async def _load_rows(db: AsyncSession) -> dict[uuid.UUID, Row]:
    result = await db.execute(
        select(
            IngestFile.id,
            IngestFile.supersedes_id,
            IngestFile.original_name,
            IngestFile.title,
            IngestFile.doc_type,
            IngestFile.official_ref,
            IngestFile.doc_date,
            IngestFile.uploaded_at,
            IngestFile.archived_at,
            IngestFile.review_status,
            IngestFile.scan_result["text_key"].astext,
        ).where(IngestFile.storage_key.is_not(None))
    )
    return {
        r[0]: Row(
            r[0],
            r[1],
            r[2],
            r[3],
            r[4].value if r[4] else None,
            r[5],
            r[6],
            r[7],
            r[8] is not None,
            r[9] is ReviewStatus.approved,
            r[10],
        )  # fmt: skip
        for r in result.all()
    }


async def _same_case(db: AsyncSession, ref: str | None) -> set[uuid.UUID]:
    """Files of the decision archive with the Esas and Karar numbers of `ref`
    ("2020/123 E., 2021/456 K.")."""
    m = _CASE_RE.search(ref or "")
    if m is None:
        return set()
    result = await db.execute(
        select(Extraction.file_id).where(
            Extraction.parser_name == PARSER_NAME,
            Extraction.fields["esas_no"].astext == m[1],
            Extraction.fields["karar_no"].astext == m[2],
        )
    )
    return set(result.scalars())


async def compute_matches(
    db: AsyncSession, store: FileStore, subject: Subject, text: str
) -> dict[str, Any]:
    """`{"previous_version": {...} | None, "similar": [...]}` for `subject`, whose extracted
    text is `text`."""
    rows = await _load_rows(db)
    own = _chain_ids(rows, subject.supersedes_id) | {subject.id}
    cases = await _same_case(db, subject.official_ref)
    reasons: dict[uuid.UUID, str] = {}
    for rid, row in rows.items():
        if rid in own or row.archived:
            continue
        if reason := reason_for(subject, row, rid in cases):
            reasons[rid] = reason
    similar = await asyncio.to_thread(similar_files, store, text, rows, reasons, own)
    return {"previous_version": previous_version(subject, rows, reasons), "similar": similar}
