"""Genelge loader (handoff 2026-11-22, A3). The database tests are skipped when DATABASE_URL is
unset; CI sets it.

The corpus test at the end also needs a real `admin-acts.jsonl` (`hukuk-ingest admin-acts ...`);
CI has none and skips it. Run it with

    DATABASE_URL=... HUKUK_ADMIN_ACTS_JSONL=/tmp/admin-acts/admin-acts.jsonl \\
        uv run pytest services/app/tests/test_loaders_admin_acts.py -k real
"""

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.loaders import admin_acts
from app.models.admin_act import AdminAct, AdminActVersion
from app.models.common import (
    ADMIN_ACT_PARSER_NAME,
    Extraction,
    IngestFile,
    IngestJob,
    IngestStatus,
    License,
    RecordStatus,
    Review,
    Source,
    SourceCategory,
    SourceRank,
)
from hukuk_ingest.admin_acts.run import build_record
from hukuk_ingest.quality import PAGE_BREAK

Factory = async_sessionmaker[AsyncSession]

LINE = "Bu satır sayfanın metin katmanı olduğunu göstermeye yetecek kadar uzun bir açıklamadır."
# A reduced genelge: "1" untouched, "1.1" repealed, "1.2" amended in place (medium, with a gap),
# "1.3" after a skipped number (low), "2" untouched.
TEXT = PAGE_BREAK.join(
    [
        "T.C.\nSOSYAL GÜVENLİK KURUMU BAŞKANLIĞI\nSayı : 51-010.06.02-E.1 01/04/2020\n"
        "Konu : İdari Para Cezası Genelgesi\n1-GENEL AÇIKLAMALAR.......2\n"
        "2-DİĞER HUSUSLAR ........2",
        f"GENELGE\n2020/8\n1- GENEL AÇIKLAMALAR\nİdari para cezaları açıklanmıştır.\n{LINE}\n"
        "1.1- (Mülga: 09/04/2026 tarihli ve 2026/9 sayılı Genelge)\n"
        "1.2- Bildirim süresi\n(Değişik, 17/09/2021 tarihli ve 2021/32 sayılı Genelge) "
        "Bildirge on gün içinde verilir.\n"
        "1.4- Atlanan numara\nBu bölümün numarası sırayı izlemez.\n"
        "2-DİĞER HUSUSLAR\nBu genelgeye göre işlem yapılır.\n"
        "Bilgi edinilmesini ve gereğini rica ederim.",
    ]
)
SHA = "a8" * 32
# The same genelge in a later file that no longer has section "1.2".
TEXT_WITHOUT_1_2 = TEXT.replace(
    "1.2- Bildirim süresi\n(Değişik, 17/09/2021 tarihli ve 2021/32 sayılı Genelge) "
    "Bildirge on gün içinde verilir.\n",
    "",
)


def act_record(text: str = TEXT, sha256: str = SHA) -> dict[str, Any]:
    """The reduced genelge as `hukuk-ingest admin-acts` writes it."""
    row = {
        "ref": "2020/8",
        "path": "Mevzuat/Genelge/2020-08 Genelge.pdf",
        "sha256": sha256,
        "size": 4096,
        "detected_type": "pdf",
        "status": "ok",
        "warnings": [],
    }
    return build_record(row, text)


async def load_acts(factory: Factory, *records: dict[str, Any]) -> admin_acts.Counts:
    counts = admin_acts.Counts()
    await admin_acts.load(factory, admin_acts.prepare(records or [act_record()]), counts)
    return counts


async def _count(factory: Factory, model: Any) -> int:
    async with factory() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


# --- no database --------------------------------------------------------------------------------


def test_read_records_reports_unusable_lines(tmp_path: Path) -> None:
    good = act_record()
    bad_band = copy.deepcopy(good)
    bad_band["sections"][0]["confidence"] = "certain"
    needs_ocr = {**good, "status": "needs_ocr", "sections": []}
    path = tmp_path / "a.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(row) if isinstance(row, dict) else row
            for row in (good, "{not json", {"ref": "2020/8"}, "", bad_band, needs_ocr)
        ),
        encoding="utf-8",
    )

    records, errors = admin_acts.read_records(path)

    assert [r["ref"] for r in records] == ["2020/8"]
    assert errors == [
        {"ref": "satır 2", "error": "invalid JSON"},
        {"ref": "satır 3", "error": "missing record keys"},
        {"ref": "satır 5 · 2020/8", "error": "unknown band"},
        {"ref": "satır 6 · 2020/8", "error": "needs_ocr"},
    ]


def test_prepare_names_the_genelge_and_bands_its_sections() -> None:
    (act,) = admin_acts.prepare([act_record()])

    assert act.title == "SGK Genelgesi 2020/8 · İdari Para Cezası Genelgesi"
    assert act.official_ref == "SGK Genelgesi 2020/8, 01.04.2020"
    assert [(s.section_no, s.confidence) for s in act.sections] == [
        ("1", {"band": "high", "reasons": []}),
        ("1.1", {"band": "medium", "reasons": ["amended_in_place"]}),
        ("1.2", {"band": "medium", "reasons": ["amended_in_place"]}),
        ("1.4", {"band": "low", "reasons": ["number_skipped"]}),
        ("2", {"band": "high", "reasons": []}),
    ]
    first = act.sections[0].fields
    assert (first["act_ref"], first["file_sha256"]) == ("2020/8", SHA)
    assert first["act"] == {
        "issuer": "sgk",
        "kind": "genelge",
        "subject": "İdari Para Cezası Genelgesi",
        "date": "2020-04-01",
    }
    assert len(first["content_hash"]) == 64


def test_the_stored_band_is_never_better_than_the_warnings_say() -> None:
    record = act_record()
    record["sections"][3]["confidence"] = "high"  # declared high, but its number was skipped
    record["sections"][0]["confidence"] = "medium"  # declared worse than its warnings: kept

    (act,) = admin_acts.prepare([record])

    assert [(s.section_no, s.confidence["band"]) for s in act.sections] == [
        ("1", "medium"),
        ("1.1", "medium"),
        ("1.2", "medium"),
        ("1.4", "low"),
        ("2", "high"),
    ]


def test_the_content_hash_follows_the_section_text() -> None:
    (act,) = admin_acts.prepare([act_record()])
    (other,) = admin_acts.prepare([act_record(TEXT.replace("on gün", "on beş gün"))])

    changed = [
        a.section_no
        for a, b in zip(act.sections, other.sections, strict=True)
        if a.fields["content_hash"] != b.fields["content_hash"]
    ]
    assert changed == ["1.2"]


# --- database (skipped without DATABASE_URL) ----------------------------------------------------


async def test_load_writes_one_source_and_an_unreviewed_extraction_per_section(
    kb_factory: Factory,
) -> None:
    counts = await load_acts(kb_factory)

    assert (counts.new, counts.skipped_existing, counts.sources_new, counts.files_new) == (
        5,
        0,
        1,
        1,
    )
    async with kb_factory() as session:
        source = (await session.execute(select(Source))).scalars().one()
        file = (await session.execute(select(IngestFile))).scalars().one()
        extractions = (
            (await session.execute(select(Extraction).order_by(Extraction.fields["ordinal"])))
            .scalars()
            .all()
        )
    assert (source.category, source.status) == (SourceCategory.admin_act, RecordStatus.analyzed)
    assert (source.source_rank, source.license) == (SourceRank.official_secondary, License.public)
    assert source.title == "SGK Genelgesi 2020/8 · İdari Para Cezası Genelgesi"
    assert (file.sha256, file.path, file.size) == (SHA, "Mevzuat/Genelge/2020-08 Genelge.pdf", 4096)
    assert {e.parser_name for e in extractions} == {ADMIN_ACT_PARSER_NAME}
    assert {e.source_id for e in extractions} == {source.id}
    assert [(e.fields["section_no"], e.confidence["band"]) for e in extractions] == [
        ("1", "high"),
        ("1.1", "medium"),
        ("1.2", "medium"),
        ("1.4", "low"),
        ("2", "high"),
    ]
    assert extractions[3].warnings == ["number_skipped:1.3->1.4", "valid_from_assumed_issue_date"]
    # the queue only: nothing is approved or published by loading
    assert await _count(kb_factory, Review) == 0
    assert await _count(kb_factory, AdminAct) == 0
    assert await _count(kb_factory, AdminActVersion) == 0


async def test_a_second_run_adds_nothing(kb_factory: Factory) -> None:
    await load_acts(kb_factory)

    counts = await load_acts(kb_factory)

    assert (counts.new, counts.skipped_existing, counts.sources_new, counts.files_new) == (
        0,
        5,
        0,
        0,
    )
    assert await _count(kb_factory, Extraction) == 5
    assert await _count(kb_factory, Source) == 1
    assert await _count(kb_factory, IngestFile) == 1
    assert await _count(kb_factory, IngestJob) == 1


async def test_a_changed_section_and_a_new_file_add_extractions_to_the_same_source(
    kb_factory: Factory,
) -> None:
    await load_acts(kb_factory)

    changed = await load_acts(kb_factory, act_record(TEXT.replace("on gün", "on beş gün")))
    new_file = await load_acts(kb_factory, act_record(sha256="b9" * 32))

    assert (changed.new, changed.skipped_existing, changed.sources_new) == (1, 4, 0)
    assert (new_file.new, new_file.sources_new, new_file.files_new) == (5, 0, 1)
    assert await _count(kb_factory, Source) == 1
    assert await _count(kb_factory, Extraction) == 11


async def test_main_loads_reports_and_fails_on_a_genelge_without_sections(
    kb_factory: Factory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "admin-acts.jsonl"
    needs_ocr = {**act_record(), "ref": "2018/38", "status": "needs_ocr", "sections": []}
    path.write_text(f"{json.dumps(act_record())}\n{json.dumps(needs_ocr)}\n", encoding="utf-8")

    code = await admin_acts._run(path)

    printed = capsys.readouterr().out
    assert "sections 5, new 5, skipped 0, errors 1" in printed
    assert "'2020/8': {'sections': 5, 'bands': {'high': 2, 'medium': 2, 'low': 1}}" in printed
    assert "error: satır 2 · 2018/38: needs_ocr" in printed
    assert code == 1
    async with kb_factory() as session:
        job = (await session.execute(select(IngestJob))).scalars().one()
    assert job.status is IngestStatus.failed  # the run reported an error
    assert job.stats["new"] == 5


# --- the real genelges ---------------------------------------------------------------------------

ADMIN_ACTS_JSONL = os.environ.get("HUKUK_ADMIN_ACTS_JSONL")
# Section counts of the golden set (packages/ingest/tests/fixtures/admin_acts/golden.toml).
REAL_SECTIONS = {"2018/38": 686, "2020/8": 177}


@pytest.mark.skipif(not ADMIN_ACTS_JSONL, reason="HUKUK_ADMIN_ACTS_JSONL not set")
async def test_the_real_genelges_load_once(kb_factory: Factory) -> None:
    records, errors = admin_acts.read_records(Path(str(ADMIN_ACTS_JSONL)))
    assert errors == []
    assert {r["ref"]: len(r["sections"]) for r in records} == REAL_SECTIONS

    first = await load_acts(kb_factory, *records)
    second = await load_acts(kb_factory, *records)

    total = sum(REAL_SECTIONS.values())
    assert (first.new, first.sources_new, first.files_new, first.errors) == (total, 2, 2, [])
    assert (second.new, second.skipped_existing, second.sources_new) == (0, total, 0)
    assert await _count(kb_factory, Extraction) == total
