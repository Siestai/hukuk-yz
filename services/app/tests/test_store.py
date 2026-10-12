"""The file store (task 12a). No database."""

import hashlib
import io
from pathlib import Path

import pytest

from app.files.store import LocalFileStore, blob_key, text_key


def test_put_stores_the_content_under_its_sha256_key(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path)
    data = b"merhaba " * 1000
    digest = hashlib.sha256(data).hexdigest()
    stored = store.put(io.BytesIO(data))
    assert stored.sha256 == digest
    assert stored.size == len(data)
    assert stored.key == f"sha256/{digest[:2]}/{digest[2:4]}/{digest}"
    assert stored.key == blob_key(digest)
    assert (tmp_path / stored.key).read_bytes() == data
    assert store.exists(stored.key)
    with store.open(stored.key) as fh:
        assert fh.read() == data


def test_the_same_content_is_stored_once_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path)
    first = store.put(io.BytesIO(b"x" * 10))
    second = store.put(io.BytesIO(b"x" * 10))
    assert first == second
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert files == [tmp_path / first.key]


def test_a_stream_that_fails_midway_leaves_nothing(tmp_path: Path) -> None:
    class Broken(io.RawIOBase):
        calls = 0

        def readable(self) -> bool:
            return True

        def read(self, size: int = -1) -> bytes:
            self.calls += 1
            if self.calls > 1:
                raise OSError("disk gone")
            return b"abc"

    store = LocalFileStore(tmp_path)
    with pytest.raises(OSError):
        store.put(Broken())  # type: ignore[arg-type]
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_put_hashes_chunk_by_chunk(tmp_path: Path) -> None:
    data = b"a" * (3 * (1 << 20) + 5)
    stored = LocalFileStore(tmp_path).put(io.BytesIO(data))
    assert stored.size == len(data)
    assert stored.sha256 == hashlib.sha256(data).hexdigest()


def test_text_is_kept_under_text_key_and_replaced(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path)
    digest = hashlib.sha256(b"doc").hexdigest()
    key = store.put_text(digest, "birinci")
    assert key == text_key(digest) == f"text/{digest}.txt"
    assert store.put_text(digest, "ikinci çğ") == key
    with store.open(key) as fh:
        assert fh.read().decode("utf-8") == "ikinci çğ"


@pytest.mark.parametrize("key", ["../etc/passwd", "sha256/ab/cd/x", "/abs", "text/../x.txt", ""])
def test_keys_of_any_other_shape_never_reach_the_file_system(tmp_path: Path, key: str) -> None:
    store = LocalFileStore(tmp_path)
    with pytest.raises(ValueError):
        store.open(key)
    with pytest.raises(ValueError):
        store.exists(key)


def test_a_missing_key_does_not_exist(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path)
    assert not store.exists(blob_key("0" * 64))
    with pytest.raises(FileNotFoundError):
        store.open(blob_key("0" * 64))


def test_delete_removes_a_stored_file_and_a_missing_one_is_not_an_error(tmp_path: Path) -> None:
    store = LocalFileStore(tmp_path)
    stored = store.put(io.BytesIO(b"abc"))
    text = store.put_text(stored.sha256, "abc")
    store.delete(stored.key)
    store.delete(text)
    store.delete(stored.key)
    assert not store.exists(stored.key)
    assert not store.exists(text)
    with pytest.raises(ValueError, match="not a file store key"):
        store.delete("../outside")
