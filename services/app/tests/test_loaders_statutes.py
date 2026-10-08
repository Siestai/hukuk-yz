"""Statute loader (task 11b). The database tests are skipped when DATABASE_URL is unset; CI sets
it."""

import asyncio
import copy
import json
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kb import STATUTE_PARSER_NAME
from app.loaders import statutes
from app.loaders.statutes_report import StatuteCounts
from app.models.common import (
    Extraction,
    IngestFile,
    IngestJob,
    License,
    RecordStatus,
    Review,
    Source,
    SourceCategory,
    SourceRank,
)
from app.models.statute import Statute, StatuteArticle, StatuteArticleVersion
from app.models.user import AppUser

STATUTES_FIXTURE = Path(__file__).parent / "fixtures" / "statutes_fixture.jsonl"
Factory = async_sessionmaker[AsyncSession]
ExtractionIds = Callable[[str], Awaitable[dict[str, uuid.UUID]]]  # the fixture of conftest


def _record(path: Path = STATUTES_FIXTURE) -> dict[str, Any]:
    record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return record


async def _count(factory: Factory, model: Any) -> int:
    async with factory() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def _load(factory: Factory, record: dict[str, Any]) -> StatuteCounts:
    counts = StatuteCounts()
    await statutes.load(factory, statutes.prepare([record]), {}, counts)
    return counts


# --- no database --------------------------------------------------------------------------------


def test_read_records_reports_unusable_lines(tmp_path: Path) -> None:
    good = _record()
    bad_band = copy.deepcopy(good)
    bad_band["articles"][0]["confidence"] = "certain"
    path = tmp_path / "s.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(good),
                "{not json",
                json.dumps({"number": "1"}),
                "",
                json.dumps(bad_band),
            ]
        ),
        encoding="utf-8",
    )
    records, errors = statutes.read_records(path)
    assert [r["number"] for r in records] == ["4857"]
    assert [e["error"] for e in errors] == ["invalid JSON", "missing record keys", "unknown band"]


def test_an_extraction_holds_the_article_timeline_and_its_statute() -> None:
    (statute,) = statutes.prepare([_record()])
    assert (statute.number, statute.parser_version, statute.title) == ("4857", "1", "İŞ KANUNU")
    assert statute.official_ref == "4857 sayılı Kanun, RG 10.06.2003 - 25134"
    assert statute.sha256s == ["a" * 64, "b" * 64]
    by_no = {a.article_no: a for a in statute.articles}
    assert list(by_no) == ["18", "Geçici 1", "Ek 2", "5"]
    a18 = by_no["18"]
    assert a18.fields["versions"] == _record()["articles"][0]["versions"]
    assert a18.fields["gaps"][0]["reason"] == "before_earliest_snapshot"
    assert a18.fields["latest_snapshot_date"] == "2026-04-22"
    assert a18.fields["statute_number"] == "4857"
    assert a18.fields["snapshot_sha256"] == ["a" * 64, "b" * 64]
    assert a18.fields["snapshots"] == [
        {"path": "Mevzuat/Kanunlar/4857 sayılı İş Kanunu 13.05.2016 .docx", "date": "2016-05-13"},
        {"path": "Mevzuat/Kanunlar/4857 sayılı İş Kanunu.pdf", "date": "2026-04-22"},
    ]
    assert a18.confidence == {
        "band": "medium",
        "reasons": ["before_earliest_snapshot", "exception_effective"],
    }
    assert by_no["Ek 2"].confidence["band"] == "low"
    assert by_no["5"].confidence == {"band": "high", "reasons": []}


def test_the_content_hash_covers_the_stored_fields_and_ignores_key_order() -> None:
    (statute,) = statutes.prepare([_record()])
    a18 = statute.articles[0]
    stored = {k: v for k, v in a18.fields.items() if k != "content_hash"}
    assert a18.fields["content_hash"] == statutes.content_hash(stored)
    assert statutes.content_hash(dict(reversed(stored.items()))) == a18.fields["content_hash"]
    changed = copy.deepcopy(_record())
    changed["articles"][0]["versions"][0]["text"] += " x"
    (other,) = statutes.prepare([changed])
    hashes = [a.fields["content_hash"] for a in statute.articles]
    other_hashes = [a.fields["content_hash"] for a in other.articles]
    assert other_hashes[0] != hashes[0] and other_hashes[1:] == hashes[1:]


def test_dry_run_needs_no_database_and_writes_a_report_without_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    out = tmp_path / "report"
    assert statutes.main([str(STATUTES_FIXTURE), "--dry-run", "--report", str(out)]) == 0
    assert "articles 4, new 4, skipped 0, errors 0" in capsys.readouterr().out
    summary = json.loads((out / "load-summary.json").read_text(encoding="utf-8"))
    assert summary["dry_run"] is True
    assert (summary["articles"], summary["versions"], summary["gaps"]) == (4, 6, 2)
    assert summary["bands"] == {"high": 2, "medium": 1, "low": 1}
    # 2003-06-10 .. 2016-05-13 is the only gap with a start date
    assert summary["gap_days"] == 4721
    assert summary["statutes"][0]["gaps_open_start"] == 1
    for name in ("load-summary.json", "load-summary.md"):
        content = (out / name).read_text(encoding="utf-8")
        assert "Madde 18" not in content
        assert "Dipnot metni" not in content


def test_approve_band_needs_a_reviewer_and_no_dry_run() -> None:
    with pytest.raises(SystemExit):
        statutes.main([str(STATUTES_FIXTURE), "--approve-band", "high"])
    with pytest.raises(SystemExit):
        statutes.main(
            [
                str(STATUTES_FIXTURE),
                "--dry-run",
                "--approve-band",
                "high",
                "--reviewer",
                str(uuid.uuid4()),
            ]
        )


# --- database (skipped without DATABASE_URL) ----------------------------------------------------


async def test_load_writes_files_one_source_and_one_extraction_per_article(
    kb_factory: Factory,
) -> None:
    counts = StatuteCounts()
    job_id = await statutes.load(
        kb_factory,
        statutes.prepare([_record()]),
        {"b" * 64: {"size": 1234, "detected_type": "pdf"}},
        counts,
    )
    assert job_id is not None
    assert (counts.new, counts.skipped_existing, counts.errors) == (4, 0, [])
    assert (counts.sources_new, counts.files_new) == (1, 2)
    assert await _count(kb_factory, IngestJob) == 1
    assert await _count(kb_factory, IngestFile) == 2
    assert await _count(kb_factory, Source) == 1
    assert await _count(kb_factory, Extraction) == 4
    for model in (Statute, StatuteArticle, StatuteArticleVersion, Review):
        assert await _count(kb_factory, model) == 0, model

    async with kb_factory() as session:
        source = (await session.execute(select(Source))).scalar_one()
        assert source.category is SourceCategory.statute
        assert source.source_rank is SourceRank.official_secondary
        assert source.license is License.public
        assert source.status is RecordStatus.analyzed
        assert (source.title, source.official_ref) == (
            "İŞ KANUNU",
            "4857 sayılı Kanun, RG 10.06.2003 - 25134",
        )
        files = {f.sha256: f for f in (await session.execute(select(IngestFile))).scalars().all()}
        assert (files["b" * 64].size, files["b" * 64].detected_type) == (1234, "pdf")
        assert files["a" * 64].size == 0
        extractions = (await session.execute(select(Extraction))).scalars().all()
        assert {e.source_id for e in extractions} == {source.id}
        assert {e.file_id for e in extractions} == {files["b" * 64].id}  # the newest snapshot
        a18 = next(e for e in extractions if e.fields["article_no"] == "18")
        assert (a18.parser_name, a18.parser_version) == (STATUTE_PARSER_NAME, "1")
        assert a18.confidence["band"] == "medium"
        assert a18.warnings == ["before_earliest_snapshot", "exception_effective"]
        assert a18.fields["versions"][1]["valid_from"] == "2018-01-01"
        # the queue columns of the decisions stay empty
        assert (a18.court, a18.esas_no, a18.journal_issue, a18.duplicate_key) == (
            None,
            None,
            None,
            None,
        )


async def test_a_second_run_adds_nothing(kb_factory: Factory) -> None:
    await _load(kb_factory, _record())
    counts = StatuteCounts()
    assert await statutes.load(kb_factory, statutes.prepare([_record()]), {}, counts) is None
    assert (counts.new, counts.skipped_existing) == (0, 4)
    for model, expected in ((Source, 1), (IngestFile, 2), (Extraction, 4), (IngestJob, 1)):
        assert await _count(kb_factory, model) == expected, model


async def test_a_new_parser_version_adds_extractions_and_leaves_published_rows_alone(
    kb_factory: Factory, statutes_published: dict[str, uuid.UUID], extraction_ids: ExtractionIds
) -> None:
    async with kb_factory() as session:
        live_before = (
            await session.execute(
                select(StatuteArticleVersion.id, StatuteArticleVersion.superseded_at)
            )
        ).all()
    counts = await _load(kb_factory, {**_record(), "parser_version": "2"})
    assert (counts.new, counts.skipped_existing, counts.sources_new, counts.files_new) == (
        4,
        0,
        0,
        0,
    )
    assert await _count(kb_factory, Source) == 1
    assert await _count(kb_factory, Extraction) == 8
    new = await extraction_ids("2")
    assert set(new) == set(statutes_published) and not set(new.values()) & set(
        statutes_published.values()
    )
    async with kb_factory() as session:
        live_after = (
            await session.execute(
                select(StatuteArticleVersion.id, StatuteArticleVersion.superseded_at)
            )
        ).all()
    assert sorted(live_after) == sorted(live_before)
    assert all(superseded is None for _, superseded in live_after)


async def test_a_changed_timeline_with_the_same_parser_version_adds_one_extraction(
    kb_factory: Factory,
) -> None:
    await _load(kb_factory, _record())
    record = _record()
    record["articles"][0]["versions"][0]["text"] += " (registry update)"
    counts = await _load(kb_factory, record)
    assert (counts.new, counts.skipped_existing, counts.sources_new, counts.files_new) == (
        1,
        3,
        0,
        0,
    )
    assert await _count(kb_factory, Extraction) == 5
    async with kb_factory() as session:
        article_nos = (
            await session.scalars(select(Extraction.fields["article_no"].as_string()))
        ).all()
    assert Counter(article_nos) == {"18": 2, "5": 1, "Ek 2": 1, "Geçici 1": 1}
    assert (await _load(kb_factory, record)).new == 0


async def test_a_new_snapshot_set_adds_extractions(kb_factory: Factory) -> None:
    await _load(kb_factory, _record())
    record = _record()
    record["snapshots"][1]["sha256"] = "c" * 64
    counts = await _load(kb_factory, record)
    assert (counts.new, counts.files_new, counts.files_existing, counts.sources_new) == (4, 1, 1, 0)
    assert await _count(kb_factory, Source) == 1
    assert await _count(kb_factory, IngestFile) == 3
    assert await _count(kb_factory, Extraction) == 8


async def test_approve_band_publishes_the_band_only(
    kb_factory: Factory, statutes_loaded: dict[str, uuid.UUID], reviewer: AppUser
) -> None:
    counts = StatuteCounts()
    await statutes.approve_band(kb_factory, "high", reviewer.id, counts)
    assert (counts.published, counts.publish_failed) == (2, [])
    async with kb_factory() as session:
        articles = (await session.execute(select(StatuteArticle.article_no))).scalars().all()
        source = (await session.execute(select(Source))).scalar_one()
    assert sorted(articles) == ["5", "Geçici 1"]
    assert source.status is RecordStatus.approved
    again = StatuteCounts()
    await statutes.approve_band(kb_factory, "high", reviewer.id, again)
    assert again.published == 0
    assert await _count(kb_factory, Review) == 2


async def test_the_cli_approves_a_band_end_to_end(
    kb_factory: Factory,
    database_url: str,
    reviewer: AppUser,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = [str(STATUTES_FIXTURE), "--approve-band", "high", "--reviewer", str(reviewer.id)]
    assert await asyncio.to_thread(statutes.main, argv) == 0
    assert "published 2" in capsys.readouterr().out
    assert await _count(kb_factory, StatuteArticleVersion) == 3
    assert await asyncio.to_thread(statutes.main, argv) == 0  # a rerun adds nothing
    assert await _count(kb_factory, Extraction) == 4
    assert await _count(kb_factory, StatuteArticleVersion) == 3


async def test_the_cli_refuses_an_unknown_reviewer_before_loading(
    kb_factory: Factory, database_url: str
) -> None:
    argv = [str(STATUTES_FIXTURE), "--approve-band", "high", "--reviewer", str(uuid.uuid4())]
    with pytest.raises(SystemExit, match="no user with id"):
        await asyncio.to_thread(statutes.main, argv)
    assert await _count(kb_factory, Source) == 0
