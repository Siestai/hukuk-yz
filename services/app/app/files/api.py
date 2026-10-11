"""Files API (task 12a): upload, versions, list, detail, content and text, archive, rescan.

Files are kept by content in a `FileStore`; `ingest_file` is the record. An upload is checked
(size, extension, content type), stored, and queued for the worker, which scans it
(`app.worker`). `original_name` is metadata only: no path of the file system or the store is
ever built from it.

The upload is parsed after the role check (a handler that declares no body parameters), so an
unauthenticated request is refused before any of its body is read.
"""

import hashlib
import logging
import re
import tempfile
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, BinaryIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import iterate_in_threadpool, run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import Select, exists, func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from starlette.datastructures import FormData, UploadFile

from app.auth import Db, require_role
from app.errors import ApiError
from app.files.store import CHUNK_BYTES, FileStore, LocalFileStore, StoredFile
from app.models.common import (
    DocumentType,
    IngestFile,
    IngestJob,
    IngestKind,
    ScanStatus,
)
from app.models.user import AppUser
from app.review_common import Limit, Reviewer, reviewer_check
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
# Multipart framing and the form fields on top of the file itself.
FORM_OVERHEAD_BYTES = 256 * 1024
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


class _TooLarge(Exception):
    pass


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


def _check_and_store(
    store: FileStore, source: BinaryIO, suffix: str, max_bytes: int
) -> tuple[DetectedType, StoredFile]:
    """Copy the upload to a staging file (at most `max_bytes`), check its content against the
    extension, and store it. Runs in a thread."""
    with tempfile.TemporaryDirectory(prefix="upload-") as staging:
        staged = Path(staging) / f"upload{suffix}"
        size = 0
        try:
            with staged.open("wb") as out:
                while chunk := source.read(CHUNK_BYTES):
                    size += len(chunk)
                    if size > max_bytes:
                        raise _TooLarge
                    out.write(chunk)
        except _TooLarge:
            raise ApiError(413, ErrorCode.file_too_large, {"max_bytes": max_bytes}) from None
        if size == 0:
            raise ApiError(400, ErrorCode.invalid_file)
        detection = detect(staged)
        if detection.type is DetectedType.UNKNOWN or detection.extension_mismatch:
            raise ApiError(415, ErrorCode.unsupported_file_type)
        with staged.open("rb") as fh:
            return detection.type, store.put(fh)


async def _parse_form(request: Request, max_bytes: int) -> FormData:
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > max_bytes + FORM_OVERHEAD_BYTES:
        raise ApiError(413, ErrorCode.file_too_large, {"max_bytes": max_bytes})
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "multipart/form-data":
        raise ApiError(415, ErrorCode.unsupported_media_type)
    # Starlette keeps an upload over 1 MB in a temporary file, not in memory.
    return await request.form(max_files=1, max_fields=20)


def _fields(form: FormData) -> FileFields:
    given = {
        name: value.strip()
        for name in FORM_FIELDS
        if isinstance(value := form.get(name), str) and value.strip()
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
    max_bytes = get_settings().file_max_bytes
    form = await _parse_form(request, max_bytes)
    try:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise ApiError(400, ErrorCode.invalid_file)
        fields = _fields(form)
        name, suffix = _safe_name(upload.filename)
        doc_type = fields.doc_type or (
            previous.doc_type.value if previous is not None and previous.doc_type else None
        )
        if doc_type is None:
            raise RequestValidationError(
                [{"loc": ("body", "doc_type"), "type": "missing", "msg": "Field required"}]
            )
        detected, stored = await run_in_threadpool(
            _check_and_store, store, upload.file, suffix, max_bytes
        )
    finally:
        await form.close()
    if (error := await _duplicate(db, stored.sha256)) is not None:
        raise error
    file = IngestFile(
        path=stored.key,
        sha256=stored.sha256,
        size=stored.size,
        detected_type=detected.value,
        storage_key=stored.key,
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
        if (error := await _duplicate(db, stored.sha256)) is not None:
            raise error from None
        if previous is not None:
            raise ApiError(409, ErrorCode.file_version_conflict) from None
        raise
    # The blob is stored (or already was); a failed insert above leaves it for the next upload.
    await db.refresh(file)
    logger.info("file %s uploaded by %s (%d bytes)", file.id, user.id, file.size)
    return _out(file, user.display_name)


@router.post("", status_code=201, openapi_extra=_multipart_body(doc_type_required=True))
async def upload_file(request: Request, db: Db, store: Store, user: Reviewer) -> FileOut:
    return await _create(request, db, store, user, None)


@router.post(
    "/{file_id}/versions",
    status_code=201,
    openapi_extra=_multipart_body(doc_type_required=False),
)
async def upload_version(
    file_id: uuid.UUID, request: Request, db: Db, store: Store, user: Reviewer
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
    return f"{file.uploaded_at.isoformat()}|{file.id}"


def _parse_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        stamp, _, file_id = cursor.partition("|")
        return datetime.fromisoformat(stamp), uuid.UUID(file_id)
    except ValueError:
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
    chain = [_out(this, uploader)]
    previous_id = this.supersedes_id
    while previous_id is not None:
        older, name = await _load(db, previous_id)
        chain.insert(0, _out(older, name))
        previous_id = older.supersedes_id
    current = this.id
    while (
        row := (
            await db.execute(_select_files().where(IngestFile.supersedes_id == current))
        ).one_or_none()
    ) is not None:
        newer_file, name = row.tuple()
        chain.append(_out(newer_file, name))
        current = newer_file.id
    return FileDetail(**_out(this, uploader).model_dump(), versions=chain)


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
    file, uploader = await _load(db, file_id)
    if file.storage_key is None:  # a row of the archive loaders: nothing stored to scan
        raise ApiError(404, ErrorCode.file_not_found)
    file.scan_status = ScanStatus.queued
    await db.commit()
    return _out(file, uploader)
