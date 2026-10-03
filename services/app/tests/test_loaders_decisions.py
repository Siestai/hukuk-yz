import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kb import PARSER_NAME
from app.loaders import decisions
from app.loaders.decisions import (
    REQUIRED_KEYS,
    approve_band,
    finish_job,
    load,
    official_ref,
    prepare,
    read_files,
    read_rows,
)
from app.loaders.normalize import BOOKKEEPING, COURT_LEVELS, COURTS, OUTCOMES
from app.loaders.report import LoadCounts, PreparedRecord, build_summary
from app.models.common import (
    Extraction,
    IngestFile,
    IngestJob,
    IngestStatus,
    License,
    RecordStatus,
    Source,
    SourceRank,
)
from app.models.decision import Decision
from app.models.user import AppUser

FIXTURE = Path(__file__).parent / "fixtures" / "decisions_fixture.jsonl"
FIXTURE_LINES = 25  # one of them repeats another's sha256 (the same PDF in two issues)


def _prepared() -> tuple[list[PreparedRecord], int]:
    rows, errors, total = read_rows(FIXTURE)
    assert (errors, total) == ([], FIXTURE_LINES)
    return prepare(rows, {})


def _by_page(prepared: list[PreparedRecord]) -> dict[int, PreparedRecord]:
    return {p.fields["journal_page"]: p for p in prepared}


# --- mapping and rules, no database ----------------------------------------------------------


def test_the_same_pdf_in_two_issues_is_one_record() -> None:
    prepared, repeated = _prepared()
    assert (len(prepared), repeated) == (FIXTURE_LINES - 1, 1)
    assert len({p.sha256 for p in prepared}) == len(prepared)


def test_a_record_carries_every_parser_field_and_its_provenance() -> None:
    first = _by_page(_prepared()[0])[10]
    assert REQUIRED_KEYS - BOOKKEEPING <= first.fields.keys()
    assert not BOOKKEEPING & first.fields.keys()
    assert first.title == "Fixture 00"
    assert first.official_ref == "Yargıtay 9. HD, E. 2003/2518 K. 2003/15276, 23.09.2003"
    assert first.raw_text_ref == f"data/extracted/{first.sha256[:2]}/{first.sha256}.clean.txt"
    assert first.parser_version == "5"
    assert first.size == 0
    assert first.detected_type is None


def test_enum_fields_are_inside_the_schema_enums_or_empty() -> None:
    for p in _prepared()[0]:
        assert p.fields["outcome"] in OUTCOMES | {""}
        assert p.fields["court"] in COURTS | {""}
        assert p.fields["court_level"] in COURT_LEVELS | {""}


def test_the_parser_outcome_is_normalized() -> None:
    outcomes = {p.fields["outcome"] for p in _prepared()[0]}
    assert "duzelterek_onama" in outcomes
    assert "düzelterek onama" not in outcomes


def test_a_decision_without_a_court_is_low_with_a_warning() -> None:
    p = _by_page(_prepared()[0])[21]
    assert p.fields["court"] == ""
    assert "court_missing" in p.warnings
    assert p.confidence["band"] == "low"


def test_same_text_group_keeps_the_longest_as_medium() -> None:
    by_page = _by_page(_prepared()[0])
    shorter, longest = by_page[13], by_page[30]
    for p in (shorter, longest):
        assert p.fields["duplicate_group"]["dup_kind"] == "same_text"
    assert longest.confidence["band"] == "medium"
    assert "duplicate_of" not in longest.warnings
    assert shorter.confidence["band"] == "low"
    assert "duplicate_of" in shorter.warnings


@pytest.mark.parametrize(
    ("pages", "dup_kind", "band"),
    [
        ((14, 31), "excerpt", "medium"),
        ((16, 32), "different_text", "low"),
        ((19, 33), "date_mismatch", "low"),
    ],
)
def test_duplicate_groups(pages: tuple[int, int], dup_kind: str, band: str) -> None:
    by_page = _by_page(_prepared()[0])
    keys = []
    for page in pages:
        p = by_page[page]
        assert p.fields["duplicate_group"]["dup_kind"] == dup_kind
        assert p.confidence["band"] == band
        keys.append(p.fields["duplicate_group"]["key"])
    assert keys[0] == keys[1]


def test_records_outside_a_group_have_no_group_field() -> None:
    assert "duplicate_group" not in _by_page(_prepared()[0])[10].fields


def test_same_key_in_another_bam_region_is_not_a_duplicate() -> None:
    rows, _, _ = read_rows(FIXTURE)
    bam = next(r for r in rows if r["court"] == "bam")
    other = {**bam, "sha256": "ab" * 32, "bam_region": "Ankara"}
    prepared, _ = prepare([bam, other], {})
    assert all("duplicate_group" not in p.fields for p in prepared)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "Yargıtay 9. HD, E. 2017/16188 K. 2019/1234, 12.03.2019"),
        ({"esas_no": ""}, "Yargıtay 9. HD, K. 2019/1234, 12.03.2019"),
        ({"decision_date": ""}, "Yargıtay 9. HD, E. 2017/16188 K. 2019/1234"),
        ({"chamber": ""}, "Yargıtay, E. 2017/16188 K. 2019/1234, 12.03.2019"),
        (
            {"court": "bam", "bam_region": "İstanbul"},
            "İstanbul BAM 9. HD, E. 2017/16188 K. 2019/1234, 12.03.2019",
        ),
        ({"court": "", "chamber": "", "esas_no": "", "karar_no": "", "decision_date": ""}, None),
    ],
)
def test_official_ref_leaves_out_missing_parts(
    overrides: dict[str, Any], expected: str | None
) -> None:
    fields = {
        "court": "yargitay",
        "chamber": "9. HD",
        "bam_region": "",
        "esas_no": "2017/16188",
        "karar_no": "2019/1234",
        "decision_date": "2019-03-12",
    }
    assert official_ref({**fields, **overrides}) == expected


def test_files_jsonl_supplies_size_and_type(tmp_path: Path) -> None:
    rows, _, _ = read_rows(FIXTURE)
    sha = rows[0]["sha256"]
    files = tmp_path / "files.jsonl"
    files.write_text(
        json.dumps({"sha256": sha, "size": 1234, "detected_type": "pdf_text"}) + "\n"
        + json.dumps({"sha256": "", "size": 1, "detected_type": "unknown"}) + "\n",
        encoding="utf-8",
    )  # fmt: skip
    prepared, _ = prepare(rows, read_files(files))
    first = next(p for p in prepared if p.sha256 == sha)
    assert (first.size, first.detected_type) == (1234, "pdf_text")


def test_read_rows_reports_unusable_lines(tmp_path: Path) -> None:
    rows, _, _ = read_rows(FIXTURE)
    broken = {**rows[0], "status": "error"}
    path = tmp_path / "decisions.jsonl"
    path.write_text(
        "not json\n"
        + json.dumps({"sha256": "ab" * 32}) + "\n"
        + json.dumps(broken) + "\n"
        + json.dumps(rows[1]) + "\n",
        encoding="utf-8",
    )  # fmt: skip
    usable, errors, total = read_rows(path)
    assert (len(usable), total) == (1, 4)
    assert [e["error"] for e in errors] == ["invalid JSON", "missing parser keys", "parse error"]


# --- CLI, no database --------------------------------------------------------------------------


def test_dry_run_needs_no_database_and_writes_a_report_without_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    out = tmp_path / "report"
    assert decisions.main([str(FIXTURE), "--dry-run", "--report", str(out)]) == 0
    for name in ("load-summary.json", "load-summary.md"):
        content = (out / name).read_text(encoding="utf-8")
        assert "Fixture" not in content
        assert "gerekçe" not in content


def test_approve_band_needs_a_reviewer_email_and_no_dry_run() -> None:
    with pytest.raises(SystemExit):
        decisions.main([str(FIXTURE), "--approve-band", "high"])
    with pytest.raises(SystemExit):
        decisions.main(
            [str(FIXTURE), "--dry-run", "--approve-band", "high", "--reviewer-email", "a@x.test"]
        )


# --- database (skipped without DATABASE_URL) ----------------------------------------------------


async def _count(factory: async_sessionmaker[AsyncSession], model: Any) -> int:
    async with factory() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_load_writes_one_row_per_decision_and_no_decision(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    prepared, repeated = _prepared()
    counts = LoadCounts(total=FIXTURE_LINES, skipped_duplicate_sha256=repeated)
    job_id = await load(kb_factory, prepared, counts)
    assert job_id is not None
    assert (counts.new, counts.skipped_existing, counts.errors) == (len(prepared), 0, [])
    for model in (Source, IngestFile, Extraction):
        assert await _count(kb_factory, model) == len(prepared)
    assert await _count(kb_factory, IngestJob) == 1
    assert await _count(kb_factory, Decision) == 0

    first = prepared[0]
    async with kb_factory() as session:
        extraction = (
            await session.execute(
                select(Extraction).join(IngestFile).where(IngestFile.sha256 == first.sha256)
            )
        ).scalar_one()
        source = await session.get(Source, extraction.source_id)
        assert source is not None
        assert source.status is RecordStatus.analyzed
        assert source.source_rank is SourceRank.editorial
        assert source.license is License.unknown
        assert (source.title, source.official_ref) == (first.title, first.official_ref)
        assert extraction.parser_name == PARSER_NAME
        assert extraction.parser_version == "5"
        assert extraction.fields == first.fields
        assert extraction.confidence == first.confidence
        assert extraction.warnings == first.warnings
        assert extraction.raw_text_ref == first.raw_text_ref


async def test_job_stats_hold_the_summary(kb_factory: async_sessionmaker[AsyncSession]) -> None:
    prepared, repeated = _prepared()
    counts = LoadCounts(total=FIXTURE_LINES, skipped_duplicate_sha256=repeated)
    job_id = await load(kb_factory, prepared, counts)
    assert job_id is not None
    summary = build_summary(prepared, counts, 1.0, dry_run=False)
    await finish_job(kb_factory, job_id, summary)
    async with kb_factory() as session:
        job = await session.get(IngestJob, job_id)
        assert job is not None
        assert job.stats == json.loads(json.dumps(summary))
        assert job.finished_at is not None
        assert job.status is IngestStatus.completed


async def test_a_job_with_errors_is_marked_failed(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    prepared, _ = _prepared()
    job_id = await load(kb_factory, prepared[:1], LoadCounts())
    assert job_id is not None
    await finish_job(kb_factory, job_id, {"errors": 1})
    async with kb_factory() as session:
        job = await session.get(IngestJob, job_id)
        assert job is not None
        assert job.status is IngestStatus.failed


async def test_a_second_run_adds_nothing(kb_factory: async_sessionmaker[AsyncSession]) -> None:
    prepared, _ = _prepared()
    await load(kb_factory, prepared, LoadCounts())
    counts = LoadCounts()
    assert await load(kb_factory, prepared, counts) is None
    assert (counts.new, counts.skipped_existing) == (0, len(prepared))
    for model in (Source, IngestFile, Extraction, IngestJob):
        assert await _count(kb_factory, model) == (1 if model is IngestJob else len(prepared))


async def test_a_new_parser_version_adds_extractions_only(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    prepared, _ = _prepared()
    await load(kb_factory, prepared, LoadCounts())
    newer = [dataclasses.replace(p, parser_version="6") for p in prepared]
    counts = LoadCounts()
    await load(kb_factory, newer, counts)
    assert counts.new == len(prepared)
    assert await _count(kb_factory, Extraction) == 2 * len(prepared)
    assert await _count(kb_factory, Source) == len(prepared)
    assert await _count(kb_factory, IngestFile) == len(prepared)
    assert await _count(kb_factory, IngestJob) == 2


async def test_one_bad_row_does_not_lose_its_batch(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    prepared, _ = _prepared()
    bad = dataclasses.replace(prepared[0], size=2**70)  # overflows ingest_file.size
    counts = LoadCounts()
    await load(kb_factory, [bad, *prepared[1:]], counts)
    assert counts.new == len(prepared) - 1
    assert [e["ref"] for e in counts.errors] == [bad.ref]
    assert "gerekçe" not in json.dumps(counts.errors, ensure_ascii=False)
    assert await _count(kb_factory, Source) == len(prepared) - 1


async def test_approve_band_publishes_the_band_as_unverified(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    prepared, _ = _prepared()
    await load(kb_factory, prepared, LoadCounts())
    high = sum(p.confidence["band"] == "high" for p in prepared)
    result = await approve_band(kb_factory, "high", reviewer.id)
    assert (result.published, result.conflicts) == (high, [])
    async with kb_factory() as session:
        rows = (await session.execute(select(Decision))).scalars().all()
        assert len(rows) == high
        assert {d.verification.value for d in rows} == {"unverified"}
        statuses = (
            await session.execute(select(Source.status, func.count()).group_by(Source.status))
        ).all()
    assert dict(statuses) == {
        RecordStatus.approved: high,
        RecordStatus.analyzed: len(prepared) - high,
    }


async def test_approve_band_publishes_a_source_with_two_extractions_once(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    prepared, _ = _prepared()
    await load(kb_factory, prepared, LoadCounts())
    await load(
        kb_factory, [dataclasses.replace(p, parser_version="6") for p in prepared], LoadCounts()
    )
    high = sum(p.confidence["band"] == "high" for p in prepared)
    result = await approve_band(kb_factory, "high", reviewer.id)
    assert (result.published, result.conflicts, result.publish_failed) == (high, [], [])
    async with kb_factory() as session:
        versions = (
            (
                await session.execute(
                    select(Extraction.parser_version).join(
                        Decision, Decision.extraction_id == Extraction.id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert versions == ["6"] * high


async def test_approve_band_counts_a_publish_failure_and_goes_on(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    prepared, _ = _prepared()
    highs = [p for p in prepared if p.confidence["band"] == "high"]
    # A stale band: high on record, but without the court_level publish needs.
    stale = dataclasses.replace(highs[0], fields={**highs[0].fields, "court_level": ""})
    await load(kb_factory, [stale, *highs[1:]], LoadCounts())
    result = await approve_band(kb_factory, "high", reviewer.id)
    assert result.published == len(highs) - 1
    assert result.conflicts == []
    assert [(sha, "court_level" in reason) for sha, reason in result.publish_failed] == [
        (stale.sha256[:12], True)
    ]
    assert await _count(kb_factory, Decision) == len(highs) - 1


async def test_approve_band_reports_a_live_key_collision(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    prepared, _ = _prepared()
    by_page = _by_page(prepared)
    pair = (by_page[16], by_page[32])  # different_text group: one key, both low
    assert pair[0].fields["duplicate_group"]["key"] == pair[1].fields["duplicate_group"]["key"]
    assert {p.confidence["band"] for p in pair} == {"low"}
    await load(kb_factory, prepared, LoadCounts())
    result = await approve_band(kb_factory, "low", reviewer.id)
    assert {sha for sha in result.conflicts} & {p.sha256[:12] for p in pair}
    assert len(result.conflicts) == 2  # this pair and the date_mismatch pair, one loser each
    async with kb_factory() as session:
        published = (
            (
                await session.execute(
                    select(IngestFile.sha256)
                    .join(Extraction, Extraction.file_id == IngestFile.id)
                    .join(Decision, Decision.extraction_id == Extraction.id)
                )
            )
            .scalars()
            .all()
        )
    assert len({p.sha256 for p in pair} & set(published)) == 1


async def test_the_cli_approves_a_band_end_to_end(
    kb_factory: async_sessionmaker[AsyncSession],
    database_url: str,
    reviewer: AppUser,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prepared, _ = _prepared()
    high = sum(p.confidence["band"] == "high" for p in prepared)
    argv = [str(FIXTURE), "--approve-band", "high", "--reviewer-email", reviewer.email.upper()]
    assert await asyncio.to_thread(decisions.main, argv) == 0
    assert f"published {high}, conflicts 0, publish_failed 0" in capsys.readouterr().out
    assert await _count(kb_factory, Decision) == high
    assert await _count(kb_factory, Source) == len(prepared)


async def test_the_cli_refuses_an_unknown_reviewer_before_loading(
    kb_factory: async_sessionmaker[AsyncSession], database_url: str
) -> None:
    argv = [str(FIXTURE), "--approve-band", "high", "--reviewer-email", "nobody@x.test"]
    with pytest.raises(SystemExit, match="nobody@x.test"):
        await asyncio.to_thread(decisions.main, argv)
    assert await _count(kb_factory, Source) == 0
