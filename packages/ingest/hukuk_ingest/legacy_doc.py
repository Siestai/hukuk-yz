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
_CHAR_MAP = str.maketrans({"\r": "\n", "\x07": "\t", "\x0b": "\n", "\x0c": "\n"})
_CONTROL = {chr(c) for c in (*range(0x00, 0x09), *range(0x0E, 0x20))}


class UnsupportedDoc(Exception):
    """A `.doc` this reader cannot decode; `reason` is the pipeline status reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _pieces(clx: bytes) -> list[tuple[int, int, int]]:
    """(first cp, last cp, fc) for each piece of the PlcPcd inside the CLX."""
    i = 0
    while clx[i] == 0x01:  # Prc: formatting data, skipped
        i += 3 + struct.unpack_from("<H", clx, i + 1)[0]
    if clx[i] != 0x02:
        raise ValueError("no piece table in CLX")
    (lcb,) = struct.unpack_from("<I", clx, i + 1)
    plc = clx[i + 5 : i + 5 + lcb]
    n = (lcb - 4) // 12
    cps = struct.unpack_from(f"<{n + 1}I", plc, 0)
    pcd_base = 4 * (n + 1)
    return [
        (cps[k], cps[k + 1], struct.unpack_from("<I", plc, pcd_base + 8 * k + 2)[0])
        for k in range(n)
    ]


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
    """The document text; raises `UnsupportedDoc` for encrypted and pre-Word-97 files."""
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
    fc_clx, lcb_clx = struct.unpack_from("<II", word, _FC_CLX_OFFSET)
    parts: list[str] = []
    for first, last, fc in _pieces(table[fc_clx : fc_clx + lcb_clx]):
        count = last - first
        if fc & _PIECE_COMPRESSED:
            start = (fc & ~_PIECE_COMPRESSED) // 2
            parts.append(word[start : start + count].decode("cp1254", errors="replace"))
        else:
            parts.append(word[fc : fc + 2 * count].decode("utf-16-le", errors="replace"))
    text = _strip_fields("".join(parts)).translate(_CHAR_MAP)
    return "".join(ch for ch in text if ch not in _CONTROL)
