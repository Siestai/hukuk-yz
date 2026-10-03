"""Word 97-2003 `.doc` text from the piece table (CLX/PlcPcd) of the WordDocument stream."""

import struct
from pathlib import Path

import olefile

_NFIB_WORD97 = 0xC1
_FLAG_ENCRYPTED = 0x0100
_FLAG_TABLE_1 = 0x0200
_FC_CLX_OFFSET = 0x01A2
_PIECE_COMPRESSED = 0x40000000
_FIELD_BEGIN, _FIELD_SEPARATOR, _FIELD_END = "\x13", "\x14", "\x15"
_CCP_TEXT_OFFSET = 0x004C  # FibRgLw97.ccpText: characters of the main document story
_CHAR_MAP = str.maketrans({"\r": "\n", "\x07": "\t", "\x0b": "\n", "\x0c": "\n", "\x1e": "-"})
_CONTROL = {chr(c) for c in (*range(0x00, 0x09), *range(0x0E, 0x20))}


class UnsupportedDoc(Exception):
    """A `.doc` this reader cannot decode; `reason` is the pipeline status reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _pieces(clx: bytes) -> list[tuple[int, int, int]]:
    """(first cp, last cp, fc) for each piece of the PlcPcd inside the CLX."""
    try:
        i = 0
        while clx[i] == 0x01:  # Prc: formatting data, skipped
            i += 3 + struct.unpack_from("<H", clx, i + 1)[0]
        if clx[i] != 0x02:
            raise ValueError("no piece table in CLX")
        (lcb,) = struct.unpack_from("<I", clx, i + 1)
        plc = clx[i + 5 : i + 5 + lcb]
        if len(plc) != lcb:
            raise ValueError("truncated piece table")
        n = (lcb - 4) // 12
        cps = struct.unpack_from(f"<{n + 1}I", plc, 0)
        pcd_base = 4 * (n + 1)
        return [
            (cps[k], cps[k + 1], struct.unpack_from("<I", plc, pcd_base + 8 * k + 2)[0])
            for k in range(n)
        ]
    except (IndexError, struct.error) as exc:
        raise ValueError(f"corrupt piece table: {exc}") from exc


def _strip_fields(text: str) -> str:
    """Drop field instructions (`\\x13 code \\x14 result \\x15`) but keep the results."""
    out: list[str] = []
    in_result: list[bool] = []  # one entry per open field: has its separator been seen?
    for ch in text:
        if ch == _FIELD_BEGIN:
            in_result.append(False)
        elif ch == _FIELD_SEPARATOR:
            if in_result:
                in_result[-1] = True
        elif ch == _FIELD_END:
            if in_result:
                in_result.pop()
        elif all(in_result):
            out.append(ch)
    return "".join(out)


def read_doc(path: Path) -> str:
    """The main-story text (no footnotes, headers or text boxes).

    Raises `UnsupportedDoc` for encrypted and pre-Word-97 files and `ValueError` for truncated or
    corrupt ones.
    """
    ole = olefile.OleFileIO(path)
    try:
        word = ole.openstream("WordDocument").read()
        (n_fib,) = struct.unpack_from("<H", word, 0x02)
        if n_fib < _NFIB_WORD97:
            raise UnsupportedDoc("legacy_doc_pre97")
        (flags,) = struct.unpack_from("<H", word, 0x0A)
        if flags & _FLAG_ENCRYPTED:
            raise UnsupportedDoc("encrypted_doc")
        table = ole.openstream("1Table" if flags & _FLAG_TABLE_1 else "0Table").read()
    finally:
        ole.close()
    try:
        fc_clx, lcb_clx = struct.unpack_from("<II", word, _FC_CLX_OFFSET)
        (ccp_text,) = struct.unpack_from("<I", word, _CCP_TEXT_OFFSET)
    except struct.error as exc:
        raise ValueError(f"truncated FIB: {exc}") from exc
    parts: list[str] = []
    for first, last, fc in _pieces(table[fc_clx : fc_clx + lcb_clx]):
        count = min(last, ccp_text) - first
        if count <= 0:
            break
        compressed = bool(fc & _PIECE_COMPRESSED)
        start = (fc & ~_PIECE_COMPRESSED) // 2 if compressed else fc
        chunk = word[start : start + (count if compressed else 2 * count)]
        if len(chunk) != (count if compressed else 2 * count):
            raise ValueError("text piece lies beyond the WordDocument stream")
        parts.append(chunk.decode("cp1254" if compressed else "utf-16-le", errors="replace"))
    text = _strip_fields("".join(parts)).translate(_CHAR_MAP)
    return "".join(ch for ch in text if ch not in _CONTROL)
