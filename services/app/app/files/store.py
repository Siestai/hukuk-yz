"""Content-addressed storage of uploaded files (task 12).

`FileStore` is the seam to a later S3-compatible bucket: callers hold keys, never paths. The keys
are derived from the content (`sha256/ab/cd/<sha256>`; the extracted text of a file is
`text/<sha256>.txt`), so the same content is stored once and a key can be checked against its
record. The calls are synchronous file operations; async code runs them in a thread.
"""

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import BinaryIO, NamedTuple, Protocol

CHUNK_BYTES = 1 << 20
_KEY_RE = re.compile(r"sha256/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{64}|text/[0-9a-f]{64}\.txt")


class StoredFile(NamedTuple):
    key: str
    sha256: str
    size: int


class FileStore(Protocol):
    def put(self, stream: BinaryIO) -> StoredFile:
        """Store the stream's content under its sha256 key; content already stored is kept."""

    def put_text(self, sha256: str, text: str) -> str:
        """Store the extracted text of the file with this sha256 (replacing an earlier one);
        returns its key."""

    def open(self, key: str) -> BinaryIO: ...

    def exists(self, key: str) -> bool: ...


def blob_key(sha256: str) -> str:
    return f"sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}"


def text_key(sha256: str) -> str:
    return f"text/{sha256}.txt"


class LocalFileStore:
    """Files below a root directory. Writes go to a temporary file in the root and are renamed
    into place, so a reader never sees a partial file."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        # Keys come from hashes; a key of any other shape never reaches the file system.
        if not _KEY_RE.fullmatch(key):
            raise ValueError(f"not a file store key: {key!r}")
        return self.root / key

    def _install(self, tmp: str, target: Path, *, replace: bool) -> None:
        if target.exists() and not replace:
            os.unlink(tmp)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, target)

    def put(self, stream: BinaryIO) -> StoredFile:
        self.root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with tempfile.NamedTemporaryFile(dir=self.root, prefix=".put-", delete=False) as tmp:
            try:
                while chunk := stream.read(CHUNK_BYTES):
                    digest.update(chunk)
                    size += len(chunk)
                    tmp.write(chunk)
                tmp.flush()
                os.fsync(tmp.fileno())
                key = blob_key(digest.hexdigest())
                self._install(tmp.name, self._path(key), replace=False)
            except BaseException:
                Path(tmp.name).unlink(missing_ok=True)
                raise
        return StoredFile(key, digest.hexdigest(), size)

    def put_text(self, sha256: str, text: str) -> str:
        key = text_key(sha256)
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.root, prefix=".put-", delete=False) as tmp:
            try:
                tmp.write(text.encode("utf-8"))
                tmp.flush()
                os.fsync(tmp.fileno())
                self._install(tmp.name, target, replace=True)
            except BaseException:
                Path(tmp.name).unlink(missing_ok=True)
                raise
        return key

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()
