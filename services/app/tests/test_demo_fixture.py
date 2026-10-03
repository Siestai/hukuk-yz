"""The synthetic demo fixture (infra/demo, task 10d) loads through the real loader and fills the
review queue the way the dashboard e2e suite expects."""

import hashlib
from collections import Counter
from pathlib import Path

import pypdfium2
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kb import queue
from app.loaders.decisions import load, prepare, read_files, read_rows
from app.loaders.report import LoadCounts, PreparedRecord
from hukuk_models import Band, ReviewFilters

DEMO = Path(__file__).parents[3] / "infra" / "demo"
ARCHIVE = DEMO / "archive"
BANDS: dict[Band, int] = {"high": 6, "medium": 4, "low": 2}


def _prepared() -> list[PreparedRecord]:
    rows, errors, total = read_rows(DEMO / "decisions.jsonl")
    assert (errors, total) == ([], 12)
    prepared, repeated = prepare(rows, read_files(DEMO / "files.jsonl"))
    assert repeated == 0
    return prepared


def test_bands_reasons_and_courts_without_a_database() -> None:
    prepared = _prepared()
    assert Counter(p.confidence["band"] for p in prepared) == BANDS
    assert {p.fields["court"] for p in prepared} == {"yargitay", "bam"}
    reasons = {r for p in prepared for r in p.confidence["reasons"]}
    assert {
        "duplicate_of",
        "duplicate_same_text",
        "missing_karar_no",
        "date_from_closing",
    } <= reasons
    duplicates = [p for p in prepared if p.fields.get("duplicate_group")]
    assert len(duplicates) == 2


def test_every_record_has_its_pdf_in_the_demo_archive() -> None:
    for p in _prepared():
        path = ARCHIVE / p.source_path
        content = path.read_bytes()
        assert len(content) < 2048
        assert hashlib.sha256(content).hexdigest() == p.sha256
        assert p.detected_type == "pdf"
        assert len(pypdfium2.PdfDocument(content)) == 1


def test_the_fixture_is_marked_synthetic() -> None:
    assert "SYNTHETIC" in (DEMO / "README.md").read_text(encoding="utf-8").upper()
    for p in _prepared():
        assert p.fields["editorial_summary"].startswith("Kurgusal")


async def test_loaded_fixture_fills_each_band(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    counts = LoadCounts(total=12)
    assert await load(kb_factory, _prepared(), counts) is not None
    assert (counts.new, counts.errors) == (12, [])
    async with kb_factory() as session:
        for band, expected in BANDS.items():
            rows = (await session.execute(queue(band, ReviewFilters()))).all()
            assert len(rows) == expected, band
