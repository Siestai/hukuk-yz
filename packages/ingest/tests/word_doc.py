"""Synthetic Word 97-2003 `.doc` builder for tests: a real OLE2 container with a piece table.

Only the parts the reader uses exist: the FIB fields (nFib, flags, fcClx/lcbClx), the CLX with a
leading Prc and a PlcPcd, and the text pieces. Streams are padded past the 4096-byte mini-stream
cutoff so they live in ordinary FAT sectors, which keeps the container writer trivial.
"""

import struct

_FREE = 0xFFFFFFFF
_END = 0xFFFFFFFE
_SECTOR = 512
_MIN_STREAM = 4096
_TEXT_START = 0x400


def _ole2(streams: dict[str, bytes]) -> bytes:
    """OLE2 v3 container: sector 0 = FAT, sector 1 = directory, then each stream as a chain."""
    assert len(streams) <= 3
    fat = [0xFFFFFFFD, _END]
    body = b""
    entries = []
    for name, data in streams.items():
        data = data.ljust(max(_MIN_STREAM, -(-len(data) // _SECTOR) * _SECTOR), b"\x00")
        first = len(fat)
        count = len(data) // _SECTOR
        fat += [first + i + 1 for i in range(count - 1)] + [_END]
        body += data
        entries.append((name, first, len(data)))
    assert len(fat) <= 128

    def entry(name: str, kind: int, child: int, right: int, start: int, size: int) -> bytes:
        raw = name.encode("utf-16-le")
        out = bytearray(128)
        out[: len(raw)] = raw
        struct.pack_into("<HBB", out, 64, len(raw) + 2, kind, 1)
        struct.pack_into("<III", out, 68, _FREE, right, child)  # left, right, child
        struct.pack_into("<II", out, 116, start, size)
        return bytes(out)

    directory = entry("Root Entry", 5, 1, _FREE, _END, 0)
    for i, (name, first, size) in enumerate(entries):
        right = i + 2 if i + 1 < len(entries) else _FREE
        directory += entry(name, 2, _FREE, right, first, size)
    header = bytearray(512)
    header[0:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    struct.pack_into("<HHHHH", header, 24, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<III", header, 44, 1, 1, 0)  # FAT sectors, first directory sector, tx sig
    struct.pack_into("<IIIII", header, 56, 4096, _END, 0, _END, 0)
    struct.pack_into("<I", header, 76, 0)  # DIFAT[0]: the FAT is sector 0
    header[80:512] = struct.pack("<I", _FREE) * 108
    fat_sector = struct.pack("<128I", *fat, *([_FREE] * (128 - len(fat))))
    return bytes(header) + fat_sector + directory.ljust(_SECTOR, b"\x00") + body


def make_doc(
    pieces: list[tuple[str, bool]],
    *,
    n_fib: int = 0xC1,
    encrypted: bool = False,
    table_stream: str = "0Table",
) -> bytes:
    """`pieces`: (text, compressed). Compressed pieces are stored as cp1254 bytes, others UTF-16."""
    text_area = bytearray()
    pcds = []
    cps = [0]
    for text, compressed in pieces:
        offset = _TEXT_START + len(text_area)
        if compressed:
            text_area += text.encode("cp1254")
            fc = (offset * 2) | 0x40000000
        else:
            text_area += text.encode("utf-16-le")
            fc = offset
        cps.append(cps[-1] + len(text))
        pcds.append(struct.pack("<HIH", 0, fc, 0))
    plc = struct.pack(f"<{len(cps)}I", *cps) + b"".join(pcds)
    prc = b"\x01" + struct.pack("<H", 3) + b"abc"  # formatting data the reader must skip
    clx = prc + b"\x02" + struct.pack("<I", len(plc)) + plc

    word = bytearray(_TEXT_START)
    struct.pack_into("<HH", word, 0, 0xA5EC, n_fib)
    flags = (0x0100 if encrypted else 0) | (0x0200 if table_stream == "1Table" else 0)
    struct.pack_into("<H", word, 0x0A, flags)
    struct.pack_into("<II", word, 0x01A2, 0, len(clx))
    return _ole2({"WordDocument": bytes(word) + bytes(text_area), table_stream: clx})
