"""Files API (task 12a): upload, versions, list, detail, content and text, archive, rescan.

Files are kept by content in a `FileStore`; `ingest_file` is the record. An upload is checked
(size, extension, content type), stored, and queued for the worker, which scans it
(`app.worker`). `original_name` is metadata only: no path of the file system or the store is
ever built from it.

The upload is parsed after the role check (a handler that declares no body parameters), so an
unauthenticated request is refused before any of its body is read.
"""

import base64
import hashlib
import logging
import re
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Annotated, Any, BinaryIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import iterate_in_threadpool, run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import Select, exists, func, literal, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.auth import CurrentUser, Db, require_role
from app.errors import ApiError
from app.files.scan_result import carry_import_path
from app.files.store import CHUNK_BYTES, FileStore, LocalFileStore
from app.files.upload import Staged, read_upload
from app.models.common import (
    DocumentType,
    IngestFile,
    IngestJob,
    IngestKind,
    ScanStatus,
)
from app.models.user import AppUser
from app.review_common import Limit, reviewer_check
from app.settings import get_settings
from hukuk_ingest.detect import DetectedType, detect
from hukuk_models import (
    DocType,
    ErrorCode,
    FileDetail,
    FileFields,
    FileListItem,
    FileListResponse,
    FileOut,
    ScanState,
)

logger = logging.getLogger("app")

ALLOWED_SUFFIXES = frozenset(
    {".pdf", ".doc", ".docx", ".udf", ".png", ".jpg", ".jpeg", ".xlsx", ".xlsm", ".txt"}
)
MAX_NAME_LENGTH = 255
FORM_FIELDS = ("doc_type", "doc_date", "official_ref", "origin_url", "note")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_UNSAFE_HEADER_CHARS = re.compile(r"[^\x20-\x7e]|[\"\\]")

router = APIRouter(
    prefix="/files",
    tags=["files"],
    dependencies=[Depends(reviewer_check)],
    responses={400: {}, 413: {}, 503: {}},
)
admin_check = require_role("admin")


def get_store() -> FileStore:
    root = get_settings().file_store_root
    if root is None:
        raise ApiError(503, ErrorCode.file_store_unavailable)
    return LocalFileStore(root)


Store = Annotated[FileStore, Depends(get_store)]


def _multipart_body(*, doc_type_required: bool) -> dict[str, Any]:
    properties: dict[str, Any] = {"file": {"type": "string", "format": "binary"}}
    schema = FileFields.model_json_schema()
    for name in FORM_FIELDS:
        properties[name] = schema["properties"][name]
    required = ["file", "doc_type"] if doc_type_required else ["file"]
    return {
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {"type": "object", "properties": properties, "required": required}
                }
            },
        }
    }


def _select_files() -> Select[IngestFile, str]:
    return select(IngestFile, AppUser.display_name).outerjoin(
        AppUser, AppUser.id == IngestFile.uploaded_by
    )


def _out(file: IngestFile, uploader_name: str | None) -> FileOut:
    return FileOut(
        id=file.id,
        original_name=file.original_name,
        sha256=file.sha256,
        size=file.size,
        detected_type=file.detected_type,
        doc_type=file.doc_type.value if file.doc_type else None,
        doc_date=file.doc_date,
        official_ref=file.official_ref,
        origin_url=file.origin_url,
        note=file.note,
        uploaded_by_id=file.uploaded_by,
        uploaded_by_name=uploader_name,
        uploaded_at=file.uploaded_at,
        supersedes_id=file.supersedes_id,
        scan_status=file.scan_status.value,
        scan_result=file.scan_result,
        archived_at=file.archived_at,
    )


async def _load(db: AsyncSession, file_id: uuid.UUID) -> tuple[IngestFile, str | None]:
    row = (await db.execute(_select_files().where(IngestFile.id == file_id))).one_or_none()
    if row is None:
        raise ApiError(404, ErrorCode.file_not_found)
    file, uploader = row.tuple()
    return file, uploader


# --- upload -----------------------------------------------------------------------------------


def _safe_name(raw: str | None) -> tuple[str, str]:
    """(display name, lower-case suffix) of an uploaded file name, or an `ApiError`. Only the
    last path segment counts; the name is never used as a path."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name or len(name) > MAX_NAME_LENGTH or _CONTROL_CHARS.search(name):
        raise ApiError(400, ErrorCode.invalid_file)
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ApiError(415, ErrorCode.unsupported_file_type)
    return name, suffix


def _check_and_store(store: FileStore, staged: Staged, suffix: str) -> tuple[DetectedType, str]:
    """Check the staged file's content against its extension and move it into the store. Runs in
    a thread."""
    assert staged.path is not None  # checked by the caller
    if staged.size == 0:
        raise ApiError(400, ErrorCode.invalid_file)
    detection = detect(staged.path)
    if detection.type is DetectedType.UNKNOWN or detection.extension_mismatch:
        raise ApiError(415, ErrorCode.unsupported_file_type)
    return detection.type, store.put_path(staged.path, staged.sha256)


def _fields(form: dict[str, str]) -> FileFields:
    given = {
        name: value.strip() for name in FORM_FIELDS if (value := form.get(name)) and value.strip()
    }
    try:
        return FileFields.model_validate(given)
    except ValidationError as exc:
        raise RequestValidationError(
            [{**e, "loc": ("body", *e["loc"])} for e in exc.errors()]
        ) from None


async def _duplicate(db: AsyncSession, sha256: str) -> ApiError | None:
    existing = (
        await db.execute(
            select(IngestFile.id, IngestFile.archived_at).where(
                IngestFile.sha256 == sha256, IngestFile.storage_key.is_not(None)
            )
        )
    ).one_or_none()
    if existing is None:
        return None
    return ApiError(
        409,
        ErrorCode.duplicate_file,
        {"file_id": str(existing.id), "archived": existing.archived_at is not None},
    )


async def _create(
    request: Request, db: AsyncSession, store: FileStore, user: AppUser, previous: IngestFile | None
) -> FileOut:
    """Check, store and queue an upload; `previous` makes it the next version of that file
    (empty form fields are then copied from it)."""
    async with read_upload(request, get_settings().file_max_bytes) as staged:
        if staged.path is None:
            raise ApiError(400, ErrorCode.invalid_file)
        fields = _fields(staged.fields)
        name, suffix = _safe_name(staged.filename)
        doc_type = fields.doc_type or (
            previous.doc_type.value if previous is not None and previous.doc_type else None
        )
        if doc_type is None:
            raise RequestValidationError(
                [{"loc": ("body", "doc_type"), "type": "missing", "msg": "Field required"}]
            )
        detected, key = await run_in_threadpool(_check_and_store, store, staged, suffix)
    sha256, size = staged.sha256, staged.size
    if (error := await _duplicate(db, sha256)) is not None:
        raise error
    file = IngestFile(
        path=key,
        sha256=sha256,
        size=size,
        detected_type=detected.value,
        storage_key=key,
        original_name=name,
        doc_type=DocumentType(doc_type),
        doc_date=fields.doc_date or (previous.doc_date if previous else None),
        official_ref=fields.official_ref or (previous.official_ref if previous else None),
        origin_url=fields.origin_url or (previous.origin_url if previous else None),
        note=fields.note or (previous.note if previous else None),
        uploaded_by=user.id,
        supersedes_id=previous.id if previous else None,
        scan_status=ScanStatus.queued,
    )
    job = IngestJob(created_by=user.id, kind=IngestKind.upload, stats={"files": 1})
    db.add(job)
    await db.flush()
    file.job_id = job.id
    db.add(file)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Lost a race: the same content was uploaded, or the file got its next version, first.
        if (error := await _duplicate(db, sha256)) is not None:
            raise error from None
        if previous is not None:
            raise ApiError(409, ErrorCode.file_version_conflict) from None
        raise
    # The blob is stored (or already was); a failed insert above leaves it for the next upload.
    await db.refresh(file)
    logger.info("file %s uploaded by %s (%d bytes)", file.id, user.id, file.size)
    return _out(file, user.display_name)


@router.post("", status_code=201, openapi_extra=_multipart_body(doc_type_required=True))
async def upload_file(request: Request, db: Db, store: Store, user: CurrentUser) -> FileOut:
    return await _create(request, db, store, user, None)


@router.post(
    "/{file_id}/versions",
    status_code=201,
    openapi_extra=_multipart_body(doc_type_required=False),
)
async def upload_version(
    file_id: uuid.UUID, request: Request, db: Db, store: Store, user: CurrentUser
) -> FileOut:
    previous, _ = await _load(db, file_id)
    has_next = (
        await db.execute(select(exists().where(IngestFile.supersedes_id == previous.id)))
    ).scalar_one()
    if has_next or previous.archived_at is not None:
        raise ApiError(409, ErrorCode.file_version_conflict)
    return await _create(request, db, store, user, previous)


# --- list and detail --------------------------------------------------------------------------


def _cursor_of(file: IngestFile) -> str:
    raw = f"{file.uploaded_at.isoformat()}|{file.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _parse_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        stamp, _, file_id = base64.urlsafe_b64decode(cursor).decode().partition("|")
        return datetime.fromisoformat(stamp), uuid.UUID(file_id)
    except ValueError:  # includes bad base64 and bad UTF-8
        raise ApiError(422, ErrorCode.validation_error, {"fields": ["cursor"]}) from None


async def _version_counts(db: AsyncSession, head_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Length of the version chain ending in each of the heads."""
    chain = (
        select(IngestFile.id.label("head"), IngestFile.supersedes_id.label("previous"))
        .where(IngestFile.id.in_(head_ids))
        .cte(recursive=True)
    )
    chain = chain.union_all(
        select(chain.c.head, IngestFile.supersedes_id).join(
            IngestFile, IngestFile.id == chain.c.previous
        )
    )
    rows = await db.execute(select(chain.c.head, func.count()).group_by(chain.c.head))
    return {head: count for head, count in rows.all()}


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("")
async def list_files(
    db: Db,
    doc_type: DocType | None = None,
    scan_status: ScanState | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    archived: bool = False,
    cursor: Annotated[str | None, Query(max_length=100)] = None,
    limit: Limit = 50,
) -> FileListResponse:
    """The newest version of every document, newest upload first."""
    newer = aliased(IngestFile)
    stmt = (
        _select_files()
        .where(
            ~exists().where(newer.supersedes_id == IngestFile.id),
            IngestFile.archived_at.is_not(None) if archived else IngestFile.archived_at.is_(None),
        )
        .order_by(IngestFile.uploaded_at.desc(), IngestFile.id.desc())
        .limit(limit + 1)
    )
    if doc_type is not None:
        stmt = stmt.where(IngestFile.doc_type == DocumentType(doc_type))
    if scan_status is not None:
        stmt = stmt.where(IngestFile.scan_status == ScanStatus(scan_status))
    if q is not None and q.strip():
        pattern = _like(q.strip())
        stmt = stmt.where(
            IngestFile.original_name.ilike(pattern, escape="\\")
            | IngestFile.official_ref.ilike(pattern, escape="\\")
        )
    if cursor is not None:
        stamp, file_id = _parse_cursor(cursor)
        stmt = stmt.where(tuple_(IngestFile.uploaded_at, IngestFile.id) < (stamp, file_id))
    rows = (await db.execute(stmt)).all()
    page = rows[:limit]
    counts = await _version_counts(db, [row[0].id for row in page]) if page else {}
    return FileListResponse(
        items=[
            FileListItem(**_out(row[0], row[1]).model_dump(), version_count=counts[row[0].id])
            for row in page
        ],
        next_cursor=_cursor_of(page[-1][0]) if len(rows) > limit else None,
    )


@router.get("/{file_id}")
async def get_file(file_id: uuid.UUID, db: Db) -> FileDetail:
    this, uploader = await _load(db, file_id)
    older = (
        select(
            IngestFile.id.label("id"),
            IngestFile.supersedes_id.label("link"),
            literal(0).label("depth"),
        )
        .where(IngestFile.id == file_id)
        .cte("older", recursive=True)
    )
    older = older.union_all(
        select(IngestFile.id, IngestFile.supersedes_id, older.c.depth - 1).join(
            older, IngestFile.id == older.c.link
        )
    )
    newer = (
        select(IngestFile.id.label("id"), literal(0).label("depth"))
        .where(IngestFile.id == file_id)
        .cte("newer", recursive=True)
    )
    newer = newer.union_all(
        select(IngestFile.id, newer.c.depth + 1).join(newer, IngestFile.supersedes_id == newer.c.id)
    )
    chain = select(older.c.id, older.c.depth).union(select(newer.c.id, newer.c.depth)).subquery()
    rows = await db.execute(
        _select_files().join(chain, chain.c.id == IngestFile.id).order_by(chain.c.depth)
    )
    versions = [_out(file, name) for file, name in (row.tuple() for row in rows)]
    return FileDetail(**_out(this, uploader).model_dump(), versions=versions)


# --- content ----------------------------------------------------------------------------------


def _content_disposition(disposition: str, name: str) -> str:
    """`filename` is an ASCII fallback, `filename*` the real name (RFC 5987 / 6266)."""
    fallback = _UNSAFE_HEADER_CHARS.sub("_", name)
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def _open_verified(store: FileStore, key: str, sha256: str) -> tuple[BinaryIO, int] | None:
    """The stored file, opened once and hashed; the bytes that were hashed are the bytes sent.
    None when it is missing or is not the content its record says."""
    try:
        fh = store.open(key)
    except OSError:
        return None
    digest = hashlib.sha256()
    size = 0
    while chunk := fh.read(CHUNK_BYTES):
        digest.update(chunk)
        size += len(chunk)
    if digest.hexdigest() != sha256:
        fh.close()
        return None
    fh.seek(0)
    return fh, size


def _chunks(fh: BinaryIO) -> Iterator[bytes]:
    with fh:
        while chunk := fh.read(CHUNK_BYTES):
            yield chunk


async def _serve(
    store: FileStore,
    key: str | None,
    sha256: str | None,
    *,
    media_type: str,
    disposition: str,
    name: str,
) -> StreamingResponse:
    opened = None
    if key is not None and sha256 is not None:
        opened = await run_in_threadpool(_open_verified, store, key, sha256)
    if opened is None:
        logger.warning("stored file %s is missing or does not match its sha256", key)
        raise ApiError(404, ErrorCode.file_not_found)
    fh, size = opened
    return StreamingResponse(
        iterate_in_threadpool(_chunks(fh)),
        media_type=media_type,
        headers={
            "Content-Length": str(size),
            "Content-Disposition": _content_disposition(disposition, name),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/{file_id}/content",
    response_class=StreamingResponse,
    responses={200: {"content": {"*/*": {"schema": {"type": "string", "format": "binary"}}}}},
)
async def get_content(file_id: uuid.UUID, db: Db, store: Store) -> StreamingResponse:
    file, _ = await _load(db, file_id)
    name = file.original_name or file.sha256
    pdf = file.detected_type == DetectedType.PDF.value
    return await _serve(
        store,
        file.storage_key,
        file.sha256,
        media_type="application/pdf" if pdf else "application/octet-stream",
        disposition="inline" if pdf else "attachment",
        name=name,
    )


@router.get(
    "/{file_id}/text",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/plain": {"schema": {"type": "string"}}}}},
)
async def get_text(file_id: uuid.UUID, db: Db, store: Store) -> StreamingResponse:
    file, _ = await _load(db, file_id)
    result = file.scan_result or {}
    return await _serve(
        store,
        result.get("text_key"),
        result.get("text_sha256"),
        media_type="text/plain; charset=utf-8",
        disposition="inline",
        name=f"{file.original_name or file.sha256}.txt",
    )


# --- admin ------------------------------------------------------------------------------------


@router.post("/{file_id}/archive", dependencies=[Depends(admin_check)])
async def archive_file(file_id: uuid.UUID, db: Db) -> FileOut:
    file, uploader = await _load(db, file_id)
    if file.archived_at is None:
        file.archived_at = datetime.now(UTC)
        await db.commit()
    return _out(file, uploader)


@router.post("/{file_id}/unarchive", dependencies=[Depends(admin_check)])
async def unarchive_file(file_id: uuid.UUID, db: Db) -> FileOut:
    file, uploader = await _load(db, file_id)
    file.archived_at = None
    await db.commit()
    return _out(file, uploader)


@router.post("/{file_id}/rescan", dependencies=[Depends(admin_check)])
async def rescan_file(file_id: uuid.UUID, db: Db) -> FileOut:
    """Queue the file for another scan; its earlier outcome (and text) is cleared. A file that
    is being scanned now is refused, one that is already queued stays as it is."""
    _, uploader = await _load(db, file_id)
    file = (
        await db.execute(
            select(IngestFile)
            .where(IngestFile.id == file_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    if file.storage_key is None:  # a row of the archive loaders: nothing stored to scan
        raise ApiError(404, ErrorCode.file_not_found)
    if file.scan_status is ScanStatus.running:
        raise ApiError(409, ErrorCode.scan_in_progress)
    if file.scan_status is not ScanStatus.queued:
        file.scan_status = ScanStatus.queued
        file.scan_result = carry_import_path(file.scan_result) or None
        file.error = None
        await db.commit()
    return _out(file, uploader)
