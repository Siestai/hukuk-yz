"""Schema tests against a real Postgres (skipped when DATABASE_URL is unset; CI sets it)."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from alembic import command
from app.db import make_engine
from app.loaders.decisions import load, prepare, read_rows
from app.loaders.report import LoadCounts
from app.models.common import Base, Extraction, Review

DECISION_LIVE_INDEX = "uq_decision_court_bam_region_chamber_esas_no_karar_no_live"
DECISIONS_FIXTURE = Path(__file__).parent / "fixtures" / "decisions_fixture.jsonl"
HALF_VECTOR = "[" + ",".join(["0.5"] * 1024) + "]"


@pytest.fixture
async def conn(database_url: str, migrated: None) -> AsyncIterator[AsyncConnection]:
    engine = make_engine(database_url)
    async with engine.connect() as connection:
        yield connection
        await connection.rollback()  # every test leaves the database untouched
    await engine.dispose()


async def _table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        return {row[0] for row in rows}


def _tables(url: str) -> set[str]:
    async def run() -> set[str]:
        engine = make_engine(url)
        try:
            return await _table_names(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _columns(url: str, table: str) -> set[str]:
    async def run() -> set[str]:
        engine = make_engine(url)
        try:
            async with engine.connect() as connection:
                rows = await connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
                    ),
                    {"t": table},
                )
                return {row[0] for row in rows}
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_the_statute_evidence_migration_downgrades_to_0007(
    alembic_config: Config, database_url: str
) -> None:
    new = {"evidence", "confidence", "warnings", "footnotes"}
    command.upgrade(alembic_config, "head")
    assert new <= _columns(database_url, "statute_article_version")
    command.downgrade(alembic_config, "0007")
    assert not new & _columns(database_url, "statute_article_version")
    command.upgrade(alembic_config, "head")
    assert new <= _columns(database_url, "statute_article_version")


def test_upgrade_downgrade_upgrade(alembic_config: Config, database_url: str) -> None:
    expected = set(Base.metadata.tables)

    command.upgrade(alembic_config, "head")
    assert expected <= _tables(database_url)

    command.downgrade(alembic_config, "base")
    assert not expected & _tables(database_url)

    command.upgrade(alembic_config, "head")
    assert expected <= _tables(database_url)


def test_the_login_attempt_migration_downgrades_to_0006(
    alembic_config: Config, database_url: str
) -> None:
    command.upgrade(alembic_config, "head")
    assert "login_attempt" in _tables(database_url)
    command.downgrade(alembic_config, "0006")
    tables = _tables(database_url)
    assert "login_attempt" not in tables
    assert {"app_user", "user_session"} <= tables
    command.upgrade(alembic_config, "head")
    assert "login_attempt" in _tables(database_url)


async def test_login_attempt_is_indexed_for_the_limit_lookups_and_the_prune(
    conn: AsyncConnection,
) -> None:
    names = set(
        await conn.scalars(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'login_attempt'")
        )
    )
    assert {
        "ix_login_attempt_email_attempted_at",
        "ix_login_attempt_ip_attempted_at",
        "ix_login_attempt_attempted_at",
    } <= names


def test_alembic_check_has_no_drift(alembic_config: Config, migrated: None) -> None:
    command.check(alembic_config)  # raises CommandError when models and migration differ


async def _load_fixture(factory: async_sessionmaker[AsyncSession]) -> None:
    rows, _, _ = read_rows(DECISIONS_FIXTURE)
    prepared, _ = prepare(rows, {})
    await load(factory, prepared, LoadCounts())


async def test_the_reviewer_fk_migration_runs_over_legacy_reviews(
    kb_factory: async_sessionmaker[AsyncSession], alembic_config: Config
) -> None:
    await _load_fixture(kb_factory)
    async with kb_factory() as session:
        extraction_id = (await session.execute(select(Extraction.id).limit(1))).scalar_one()
    await asyncio.to_thread(command.downgrade, alembic_config, "0005")
    try:
        async with kb_factory() as session:  # what the task 05 CLI wrote: a reviewer, no user
            await session.execute(
                text(
                    "INSERT INTO review (extraction_id, reviewer_id, decision) "
                    "VALUES (:e, :r, 'approve')"
                ),
                {"e": extraction_id, "r": uuid.uuid4()},
            )
            await session.commit()
    finally:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
    async with kb_factory() as session:
        assert (await session.execute(select(func.count()).select_from(Review))).scalar_one() == 1
        validated = (
            await session.execute(
                text(
                    "SELECT convalidated FROM pg_constraint "
                    "WHERE conname = 'fk_review_reviewer_id_app_user'"
                )
            )
        ).scalar_one()
    assert validated is False


async def test_the_queue_columns_of_extraction_follow_fields(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _load_fixture(kb_factory)
    async with kb_factory() as session:
        extraction = (
            await session.execute(
                select(Extraction).where(Extraction.fields["journal_page"].as_integer() == 11)
            )
        ).scalar_one()
        fields = extraction.fields
        assert (extraction.court, extraction.chamber, extraction.esas_no) == (
            fields["court"],
            fields["chamber"],
            fields["esas_no"],
        )
        assert (extraction.karar_no, extraction.decision_date, extraction.journal_issue) == (
            fields["karar_no"],
            fields["decision_date"],
            fields["journal_issue"],
        )
        assert extraction.duplicate_group == fields.get("duplicate_group")
        assert (extraction.duplicate_key is None) == ("duplicate_group" not in fields)

        await session.execute(
            text(
                "UPDATE extraction SET fields = fields || "
                '\'{"court": "aym", "journal_issue": 7}\' WHERE id = :id'
            ),
            {"id": extraction.id},
        )
        await session.refresh(extraction)
        assert (extraction.court, extraction.journal_issue) == ("aym", 7)


def _uuid(value: object) -> uuid.UUID:
    assert isinstance(value, uuid.UUID)
    return value


async def _source(conn: AsyncConnection, category: str = "statute") -> uuid.UUID:
    result = await conn.execute(
        text(
            f"INSERT INTO source (category, title, source_rank) "
            f"VALUES ('{category}', 't', 'official_primary') RETURNING id"
        )
    )
    return _uuid(result.scalar_one())


async def _article(conn: AsyncConnection, source_id: uuid.UUID) -> uuid.UUID:
    statute = (
        await conn.execute(
            text(
                "INSERT INTO statute (source_id, number, kind, full_title) "
                "VALUES (:s, '4857', 'kanun', 'İş Kanunu') RETURNING id"
            ),
            {"s": source_id},
        )
    ).scalar_one()
    article = await conn.execute(
        text(
            "INSERT INTO statute_article (statute_id, article_no, ordinal) "
            "VALUES (:st, '18', 18) RETURNING id"
        ),
        {"st": statute},
    )
    return _uuid(article.scalar_one())


async def _version(
    conn: AsyncConnection,
    source_id: uuid.UUID,
    article_id: uuid.UUID,
    valid_from: date,
    valid_to: date | None,
    superseded: bool = False,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO statute_article_version "
            "(article_id, text, valid_from, valid_to, change_kind, source_id, superseded_at) "
            "VALUES (:a, 'x', :f, :t, 'original', :s, "
            "CASE WHEN :sup THEN now() END)"
        ),
        {"a": article_id, "f": valid_from, "t": valid_to, "s": source_id, "sup": superseded},
    )


async def test_overlapping_live_versions_are_rejected(conn: AsyncConnection) -> None:
    source_id = await _source(conn)
    article_id = await _article(conn, source_id)
    await _version(conn, source_id, article_id, date(2019, 1, 1), date(2020, 1, 1))

    with pytest.raises(IntegrityError, match="ex_statute_article_version_no_overlap"):
        async with conn.begin_nested():
            await _version(conn, source_id, article_id, date(2019, 6, 1), None)


async def test_adjacent_and_superseded_versions_are_allowed(conn: AsyncConnection) -> None:
    source_id = await _source(conn)
    article_id = await _article(conn, source_id)
    await _version(conn, source_id, article_id, date(2019, 1, 1), date(2020, 1, 1))
    # valid_to is exclusive: the next version may start on that very day
    await _version(conn, source_id, article_id, date(2020, 1, 1), None)
    # superseded history may overlap anything
    await _version(conn, source_id, article_id, date(2019, 6, 1), None, superseded=True)


async def test_a_version_has_empty_evidence_by_default_and_a_known_confidence_band(
    conn: AsyncConnection,
) -> None:
    source_id = await _source(conn)
    article_id = await _article(conn, source_id)
    await _version(conn, source_id, article_id, date(2019, 1, 1), None)
    row = (
        await conn.execute(
            text("SELECT evidence, confidence, warnings, footnotes FROM statute_article_version")
        )
    ).one()
    assert (row.evidence, row.confidence, row.warnings, row.footnotes) == ({}, None, [], [])
    with pytest.raises(IntegrityError, match="ck_statute_article_version_confidence"):
        async with conn.begin_nested():
            await conn.execute(text("UPDATE statute_article_version SET confidence = 'certain'"))
    await conn.execute(text("UPDATE statute_article_version SET confidence = 'low'"))


async def test_valid_range_check(conn: AsyncConnection) -> None:
    source_id = await _source(conn)
    article_id = await _article(conn, source_id)
    with pytest.raises(IntegrityError, match="ck_statute_article_version_valid_range"):
        async with conn.begin_nested():
            await _version(conn, source_id, article_id, date(2020, 1, 1), date(2019, 1, 1))


async def test_valid_range_check_is_strict(conn: AsyncConnection) -> None:
    # from = to is an empty [from, to) range: it would dodge the EXCLUDE and never be found
    source_id = await _source(conn)
    article_id = await _article(conn, source_id)
    with pytest.raises(IntegrityError, match="ck_statute_article_version_valid_range"):
        async with conn.begin_nested():
            await _version(conn, source_id, article_id, date(2020, 1, 1), date(2020, 1, 1))


async def _decision(
    conn: AsyncConnection, source_id: uuid.UUID, superseded: bool = False
) -> uuid.UUID:
    result = await conn.execute(
        text(
            "INSERT INTO decision (court, court_level, chamber, esas_no, karar_no, "
            "text_completeness, full_text, source_id, superseded_at) "
            "VALUES ('yargitay', 'daire', '9. HD', '2017/16188', '2018/1234', 'full', "
            "'Kıdem tazminatı davası', :s, CASE WHEN :sup THEN now() END) RETURNING id"
        ),
        {"s": source_id, "sup": superseded},
    )
    return _uuid(result.scalar_one())


async def _hgk_decision(conn: AsyncConnection, source_id: uuid.UUID) -> None:
    # chamber omitted on purpose: HGK has none, the column default ('') applies
    await conn.execute(
        text(
            "INSERT INTO decision (court, court_level, esas_no, karar_no, text_completeness, "
            "source_id) VALUES ('yargitay', 'hgk_iddk', '2017/9-100', '2018/200', 'full', :s)"
        ),
        {"s": source_id},
    )


async def test_decision_unique_partial(conn: AsyncConnection) -> None:
    source_id = await _source(conn, "decision")
    first = await _decision(conn, source_id)

    with pytest.raises(IntegrityError, match=DECISION_LIVE_INDEX):
        async with conn.begin_nested():
            await _decision(conn, source_id)

    # once the first record is superseded, the same E/K may be recorded again
    await conn.execute(
        text("UPDATE decision SET superseded_at = now() WHERE id = :i"), {"i": first}
    )
    await _decision(conn, source_id)
    # and superseded rows never collide with each other
    await _decision(conn, source_id, superseded=True)
    await _decision(conn, source_id, superseded=True)


async def test_chamberless_duplicate_is_rejected(conn: AsyncConnection) -> None:
    # chamber is NOT NULL DEFAULT '', so HGK rows (no chamber) collide like any other
    source_id = await _source(conn, "decision")
    await _hgk_decision(conn, source_id)
    with pytest.raises(IntegrityError, match=DECISION_LIVE_INDEX):
        async with conn.begin_nested():
            await _hgk_decision(conn, source_id)


async def _bam_decision(conn: AsyncConnection, source_id: uuid.UUID, region: str) -> None:
    await conn.execute(
        text(
            "INSERT INTO decision (court, court_level, chamber, bam_region, esas_no, karar_no, "
            "text_completeness, source_id) VALUES ('bam', 'bam_bim', '12. HD', :r, "
            "'2020/100', '2021/200', 'full', :s)"
        ),
        {"r": region, "s": source_id},
    )


async def test_same_chamber_and_numbers_in_different_bam_regions_coexist(
    conn: AsyncConnection,
) -> None:
    source_id = await _source(conn, "decision")
    await _bam_decision(conn, source_id, "İstanbul")
    await _bam_decision(conn, source_id, "Ankara")


async def test_same_bam_region_collides(conn: AsyncConnection) -> None:
    source_id = await _source(conn, "decision")
    await _bam_decision(conn, source_id, "İstanbul")
    with pytest.raises(IntegrityError, match=DECISION_LIVE_INDEX):
        async with conn.begin_nested():
            await _bam_decision(conn, source_id, "İstanbul")


async def test_statute_kind_number_is_unique(conn: AsyncConnection) -> None:
    source_id = await _source(conn)
    await _article(conn, source_id)  # creates statute kanun/4857
    with pytest.raises(IntegrityError, match="uq_statute_kind_number"):
        async with conn.begin_nested():
            await _article(conn, source_id)


async def test_decision_defaults_and_tsv_trigger(conn: AsyncConnection) -> None:
    source_id = await _source(conn, "decision")
    decision_id = await _decision(conn, source_id)
    row = (
        await conn.execute(
            text(
                "SELECT verification, tsv @@ plainto_tsquery('turkish_unaccent', 'Tazminati') "
                "FROM decision WHERE id = :i"
            ),
            {"i": decision_id},
        )
    ).one()
    assert row[0] == "unverified"
    assert row[1] is True


async def test_chunk_embedding_roundtrip(conn: AsyncConnection) -> None:
    await conn.execute(
        text(
            "INSERT INTO chunk (category, parent_kind, parent_id, kind, license, ordinal, "
            "char_start, char_end, text, embedding, embedding_model) "
            "VALUES ('decision', 'decision', gen_random_uuid(), 'body', 'public', 0, 0, 5, "
            "'hello', CAST(:e AS vector), 'test-model')"
        ),
        {"e": HALF_VECTOR},
    )
    row = (
        await conn.execute(
            text("SELECT vector_dims(embedding), tsv IS NOT NULL FROM chunk WHERE text = 'hello'")
        )
    ).one()
    assert row[0] == 1024
    assert row[1] is True
