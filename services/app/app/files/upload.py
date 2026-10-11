"""Streaming parse of an upload (task 12a).

The multipart body is read from the ASGI stream and the file part is written straight to a
staging file, hashed on the way, with the size limit enforced on the bytes as they arrive (a
chunked request has no `Content-Length` to trust). Nothing unbounded is ever spooled: the body
as a whole is capped at `max_bytes + FORM_OVERHEAD_BYTES`, the file part at `max_bytes`.
"""

import hashlib
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import BinaryIO

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from python_multipart import MultipartParser
from python_multipart.exceptions import FormParserError
from python_multipart.multipart import parse_options_header

from app.errors import ApiError
from hukuk_models import ErrorCode

# Multipart framing and the form fields on top of the file itself.
FORM_OVERHEAD_BYTES = 256 * 1024
MAX_PARTS = 20
_SUFFIX = re.compile(r"\.[a-z0-9]{1,8}")


@dataclass
class Staged:
    """What was in the body: the text fields and the file part (`path` is None without one)."""

    fields: dict[str, str] = field(default_factory=dict)
    filename: str | None = None
    path: Path | None = None
    sha256: str = ""
    size: int = 0


class _Collector:
    """Callbacks of the multipart parser. They run synchronously inside `parser.write`, so they
    only collect; `read_upload` writes the collected file bytes to disk in a thread."""

    def __init__(self, directory: Path) -> None:
        self.staged = Staged()
        self.directory = directory
        self.to_write: list[bytes] = []
        self.parts = 0
        self._header_name = b""
        self._header_value = b""
        self._headers: dict[bytes, bytes] = {}
        self._name = ""
        self._is_file = False
        self._field = bytearray()

    def on_part_begin(self) -> None:
        self.parts += 1
        if self.parts > MAX_PARTS:
            raise ApiError(400, ErrorCode.invalid_file)
        self._headers = {}
        self._field = bytearray()
        self._is_file = False

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._header_name += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._header_value += data[start:end]

    def on_header_end(self) -> None:
        self._headers[self._header_name.lower()] = self._header_value
        self._header_name = self._header_value = b""

    def on_headers_finished(self) -> None:
        _, options = parse_options_header(self._headers.get(b"content-disposition", b""))
        self._name = options.get(b"name", b"").decode("utf-8", "replace")
        filename = options.get(b"filename")
        if filename is None:
            return
        # Exactly one file part, named `file`.
        if self._name != "file" or self.staged.path is not None:
            raise ApiError(400, ErrorCode.invalid_file)
        self._is_file = True
        # The staging file keeps the extension, which `detect` compares with the content.
        suffix = PurePosixPath(
            filename.decode("utf-8", "replace").replace("\\", "/")
        ).suffix.lower()
        self.staged.path = self.directory / f"upload{suffix if _SUFFIX.fullmatch(suffix) else ''}"
        self.staged.filename = filename.decode("utf-8", "replace")

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._is_file:
            self.to_write.append(data[start:end])
        else:
            self._field += data[start:end]

    def on_part_end(self) -> None:
        if not self._is_file:
            self.staged.fields[self._name] = self._field.decode("utf-8", "replace")


@asynccontextmanager
async def read_upload(request: Request, max_bytes: int) -> AsyncIterator[Staged]:
    """The parsed upload; the staging file lives until the block ends."""
    content_type = request.headers.get("content-type", "")
    mime, options = parse_options_header(content_type)
    if mime.lower() != b"multipart/form-data":
        raise ApiError(415, ErrorCode.unsupported_media_type)
    boundary = options.get(b"boundary")
    if not boundary:
        raise ApiError(400, ErrorCode.invalid_file)
    limit = max_bytes + FORM_OVERHEAD_BYTES

    def too_large() -> ApiError:
        return ApiError(413, ErrorCode.file_too_large, {"max_bytes": max_bytes})

    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > limit:
        raise too_large()
    with TemporaryDirectory(prefix="upload-") as staging:
        collector = _Collector(Path(staging))
        parser = MultipartParser(
            boundary,
            {
                "on_part_begin": collector.on_part_begin,
                "on_header_field": collector.on_header_field,
                "on_header_value": collector.on_header_value,
                "on_header_end": collector.on_header_end,
                "on_headers_finished": collector.on_headers_finished,
                "on_part_data": collector.on_part_data,
                "on_part_end": collector.on_part_end,
            },
        )
        digest = hashlib.sha256()
        received = 0
        out: BinaryIO | None = None

        def write(chunks: list[bytes]) -> None:
            nonlocal out
            if out is None:
                assert (
                    collector.staged.path is not None
                )  # bytes only come after the file part began
                out = collector.staged.path.open("wb")
            for chunk in chunks:
                digest.update(chunk)
                out.write(chunk)

        try:
            async for chunk in request.stream():
                received += len(chunk)
                if received > limit:
                    raise too_large()
                try:
                    parser.write(chunk)
                except FormParserError:
                    raise ApiError(400, ErrorCode.invalid_file) from None
                if collector.to_write:
                    collector.staged.size += sum(len(c) for c in collector.to_write)
                    if collector.staged.size > max_bytes:
                        raise too_large()
                    await run_in_threadpool(write, collector.to_write)
                    collector.to_write = []
            try:
                parser.finalize()
            except FormParserError:
                raise ApiError(400, ErrorCode.invalid_file) from None
        finally:
            if out is not None:
                out.close()
        collector.staged.sha256 = digest.hexdigest()
        yield collector.staged
