"""A downloaded decision PDF into the review queue (task 20).

The PDF goes to the file store, is read by the task 04 parser and written as `ingest_file` +
`source` (status `analyzed`) + `extraction` by the archive loader's own writer
(`app.loaders.decisions`), so a scanned decision looks like an archive one in the queue. Nothing
is approved or published here.
"""

import asyncio
import hashlib
import io
import tempfile
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.files.store import FileStore, blob_key, text_key
from app.loaders.decisions import group_key, prepare, write_batch
from app.models.common import (
    PARSER_NAME,
    DocumentType,
    Extraction,
    IngestFile,
    ReviewStatus,
    ScanStatus,
)
from hukuk_ingest.decisions import qa
from hukuk_ingest.decisions.parse import ARCHIVE_DIR, DecisionRecord, parse_text
from hukuk_ingest.pipeline import cache_base, process_file


@dataclass(frozen=True)
class JournalPost:
    """Where a scanned decision came from: stored in `scan_result.journal`."""

    issue_no: int
    post_id: int
    page_url: str
    pdf_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_no": self.issue_no,
            "post_id": self.post_id,
            "page_url": self.page_url,
            "pdf_url": self.pdf_url,
        }

    @property
    def name(self) -> str:
        """A readable file name: the last part of the decision page's address."""
        slug = urlsplit(self.page_url).path.rstrip("/").rsplit("/", 1)[-1]
        return f"{slug or self.post_id}.pdf"


@dataclass(frozen=True)
class Read:
    record: DecisionRecord
    scan_result: dict[str, Any]
    text: str


def _unreadable(post: JournalPost, source_path: str, sha256: str, reason: str) -> DecisionRecord:
    """A file the parser could not read still goes to the queue, with empty fields and the
    reason as a warning."""
    record = DecisionRecord(
        source_path=source_path,
        sha256=sha256,
        journal_issue=post.issue_no,
        layout="unknown",
        warnings=[reason],
    )
    record.missing = qa.missing_fields(record.to_dict())
    return record


def read_pdf(content: bytes, post: JournalPost) -> Read:
    """Extract and parse one PDF (runs in a thread). The archive's issue folder is imitated in
    the path the parser reads the issue number from; the path is not stored."""
    source_path = f"{ARCHIVE_DIR}/{post.issue_no}. Sayı/{post.name}"
    sha256 = hashlib.sha256(content).hexdigest()
    with tempfile.TemporaryDirectory(prefix="journal-") as tmp:
        root = Path(tmp)
        path = root / "journal.pdf"
        path.write_bytes(content)
        result = process_file(path, root, root / "cache")
        scan_result: dict[str, Any] = {
            "detected_type": result.detected_type,
            "pages": result.pages,
            "text_chars": result.chars,
            "warnings": result.warnings,
            "reason": result.reason,
            "extractor": result.extractor,
        }
        if result.status != "ok" or not result.text_ref:
            return Read(
                _unreadable(post, source_path, sha256, f"extract_{result.status}"), scan_result, ""
            )
        text = (root / "cache" / result.text_ref).read_text(encoding="utf-8")
        clean = cache_base(root / "cache", sha256).with_suffix(".clean.txt").read_text("utf-8")
    try:
        record = parse_text(clean, source_path, sha256)
    except Exception as exc:  # one bad file must not stop the scan
        return Read(
            _unreadable(post, source_path, sha256, f"parse_{type(exc).__name__}"), scan_result, text
        )
    return Read(record, scan_result, text)


async def known_post_ids(session: AsyncSession, issue_no: int) -> set[int]:
    """The decision pages of an issue that were downloaded before."""
    rows = await session.execute(
        select(IngestFile.scan_result["journal"]["post_id"].as_integer()).where(
            IngestFile.scan_result["journal"]["issue_no"].as_integer() == issue_no
        )
    )
    return {post_id for (post_id,) in rows if post_id is not None}


async def has_file(session: AsyncSession, sha256: str) -> bool:
    return (
        await session.execute(select(IngestFile.id).where(IngestFile.sha256 == sha256).limit(1))
    ).first() is not None


async def _same_decision(session: AsyncSession, fields: dict[str, Any]) -> list[dict[str, Any]]:
    """The fields of the archive's records with the same court, chamber and E/K (one per source,
    the newest extraction), for the duplicate check."""
    if group_key(fields) is None:
        return []
    rows = await session.execute(
        select(Extraction.source_id, Extraction.fields)
        .where(
            Extraction.parser_name == PARSER_NAME,
            Extraction.court == fields["court"],
            Extraction.chamber == fields["chamber"],
            Extraction.esas_no == fields["esas_no"],
            Extraction.karar_no == fields["karar_no"],
            Extraction.fields["bam_region"].as_string() == fields["bam_region"],
        )
        .order_by(Extraction.source_id, Extraction.extracted_at.desc())
    )
    newest: dict[uuid.UUID | None, dict[str, Any]] = {}
    for source_id, fields_ in rows:
        newest.setdefault(source_id, fields_)
    return list(newest.values())


async def enqueue(
    session: AsyncSession,
    store: FileStore,
    job_id: uuid.UUID,
    content: bytes,
    post: JournalPost,
) -> bool | None:
    """Store, parse and queue a PDF in the caller's transaction (the caller commits). Returns
    None when a file with this content exists already (nothing is written), else whether the
    decision is a duplicate candidate: the archive has one with the same court, chamber and E/K.
    The record is `analyzed` and unverified, its source rank editorial (the archive loader's
    values); the file counts as approved like the archive's (the decision review is the human
    step)."""
    sha256 = hashlib.sha256(content).hexdigest()
    if await has_file(session, sha256):
        return None
    await asyncio.to_thread(store.put, io.BytesIO(content))
    read = await asyncio.to_thread(read_pdf, content, post)
    files = {sha256: {"size": len(content), "detected_type": "pdf"}}
    (alone,), _ = prepare([read.record.to_dict()], files)
    known = await _same_decision(session, alone.fields)
    (prepared,), _ = prepare([read.record.to_dict()], files, known)
    text_ref = await asyncio.to_thread(store.put_text, sha256, read.text)
    decision_date = prepared.fields["decision_date"]
    prepared.raw_text_ref = text_ref
    prepared.file_values = {
        "path": blob_key(sha256),
        "storage_key": blob_key(sha256),
        "original_name": post.name,
        "doc_type": DocumentType.karar,
        "doc_date": date.fromisoformat(decision_date) if decision_date else None,
        "official_ref": prepared.official_ref,
        "origin_url": post.pdf_url,
        "title": prepared.official_ref,
        "scan_status": ScanStatus.done,
        "scan_result": {
            **read.scan_result,
            "text_key": text_key(sha256),
            "journal": post.to_dict(),
        },
        "review_status": ReviewStatus.approved,
    }
    await write_batch(session, [prepared], {}, job_id)
    return bool(known)
