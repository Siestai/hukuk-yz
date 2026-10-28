"""Fixtures shared by the database tests (skipped when DATABASE_URL is unset; CI sets it)."""

import hashlib
import json
import os
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from alembic import command
from app.db import make_engine, make_session_factory
from app.embeddings import Embedded
from app.kb import approve_statute_article
from app.loaders import statutes as statute_loader
from app.loaders.statutes_report import StatuteCounts
from app.models.common import (
    STATUTE_PARSER_NAME,
    Court,
    CourtLevel,
    Extraction,
    RecordStatus,
    Source,
    SourceCategory,
    SourceRank,
    TextCompleteness,
)
from app.models.decision import Decision
from app.models.user import AppUser, UserRole


class FakeEmbedder:
    """An embedder with no network: a normalized bag of hashed words, so that texts with words in
    common are close. `calls` lists the texts of every request."""

    model_id = "fake-embedding:1024"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> Embedded:
        self.calls.append(list(texts))
        vectors: list[list[float]] = []
        tokens = 0
        for passage in texts:
            vector = [0.0] * 1024
            words = re.findall(r"\w+", passage.lower())
            tokens += len(words)
            for word in words:
                vector[int(hashlib.sha1(word.encode()).hexdigest()[:8], 16) % 1024] += 1.0
            norm = sum(x * x for x in vector) ** 0.5 or 1.0
            vectors.append([x / norm for x in vector])
        return Embedded(vectors, tokens)


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"
SCAN_PNG_PATH = (
    Path(__file__).parents[3] / "packages" / "ingest" / "tests" / "fixtures" / "scan.png"
)

SENTENCE = (
    "Isci kidem tazminatina hak kazanmak icin ayni isyerinde en az bir yil calismis olmalidir. "
    "Is sozlesmesinin haklı nedenle feshi halinde ihbar suresi aranmaz ve odeme yapilir. "
)


def make_pdf(text: str = SENTENCE * 6) -> bytes:
    """A one-page PDF with a text layer (ASCII text; Helvetica)."""
    escaped = text.encode("ascii", "replace").replace(b"(", b"\\(").replace(b")", b"\\)")
    lines = [escaped[i : i + 90] for i in range(0, len(escaped), 90)]
    stream = b"BT /F1 10 Tf 12 TL 40 750 Td " + b" T* ".join(b"(" + x + b") Tj" for x in lines)
    stream += b" ET"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R "
        b"/Resources << /Font << /F1 3 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for num, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % num + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


@pytest.fixture(name="make_pdf")
def make_pdf_fixture() -> Callable[..., bytes]:
    """Builds a small PDF with a text layer, for the file store, files API and worker tests."""
    return make_pdf


@pytest.fixture
def scan_png() -> bytes:
    """A small scanned page (no text layer), for the OCR tests."""
    return SCAN_PNG_PATH.read_bytes()


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    return Config(str(ALEMBIC_INI))


@pytest.fixture
def migrated(alembic_config: Config) -> None:
    # Sync on purpose: env.py runs its own event loop via asyncio.run().
    command.upgrade(alembic_config, "head")


@pytest.fixture
async def kb_factory(
    database_url: str, migrated: None
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Sessions for tests whose code commits: the KB tables and the users are emptied before and
    after."""
    engine = make_engine(database_url)

    async def clean() -> None:
        async with engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE source, ingest_job, app_user, login_attempt CASCADE")
            )

    await clean()
    yield make_session_factory(engine)
    await clean()
    await engine.dispose()


@pytest.fixture
async def reviewer(kb_factory: async_sessionmaker[AsyncSession]) -> AppUser:
    """A reviewer user (committed; removed with the rest by `kb_factory`). Its password hash is
    a placeholder: tests that log in create their own users."""
    async with kb_factory() as session:
        user = AppUser(
            email="reviewer@x.test",
            display_name="Reviewer",
            role=UserRole.reviewer,
            password_hash="x",
        )
        session.add(user)
        await session.commit()
    return user


@pytest.fixture
async def users_factory(
    database_url: str, migrated: None
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Sessions for the auth tests: app_user (and with it user_session) and login_attempt are
    emptied around them."""
    engine = make_engine(database_url)

    async def clean() -> None:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE app_user, login_attempt CASCADE"))

    await clean()
    yield make_session_factory(engine)
    await clean()
    await engine.dispose()


NewDecision = Callable[..., Awaitable[uuid.UUID]]


@pytest.fixture
def new_decision() -> NewDecision:
    """`await new_decision(session, **overrides)`: an approved, unverified Yargıtay 9. HD
    decision (editorial source) with a random esas number, flushed but not committed."""

    async def add(session: AsyncSession, **overrides: Any) -> uuid.UUID:
        source = Source(
            category=SourceCategory.decision,
            title="t",
            source_rank=SourceRank.editorial,
            status=RecordStatus.approved,
        )
        session.add(source)
        await session.flush()
        fields: dict[str, Any] = {
            "court": Court.yargitay,
            "court_level": CourtLevel.daire,
            "chamber": "9. HD",
            "esas_no": f"2017/{uuid.uuid4().int % 10**6}",
            "karar_no": "2020/1",
            "decision_date": date(2020, 12, 9),
            "text_completeness": TextCompleteness.full,
            **overrides,
        }
        decision = Decision(source_id=source.id, **fields)
        session.add(decision)
        await session.flush()
        return decision.id

    return add


STATUTES_FIXTURE = Path(__file__).parent / "fixtures" / "statutes_fixture.jsonl"
# Articles of the fixture statute (4857, reduced): "18" has a gap before its first version and two
# versions, "Geçici 1" is repealed, "Ek 2" is low and starts open, "5" is never approved.
PUBLISHED_ARTICLES = ("18", "Geçici 1", "Ek 2")


@pytest.fixture
def statute_record() -> dict[str, Any]:
    record: dict[str, Any] = json.loads(STATUTES_FIXTURE.read_text(encoding="utf-8"))
    return record


ExtractionIds = Callable[[str], Awaitable[dict[str, uuid.UUID]]]


@pytest.fixture
def extraction_ids(kb_factory: async_sessionmaker[AsyncSession]) -> ExtractionIds:
    """`await extraction_ids(version)`: the id of every loaded statute article extraction of a
    parser version, by article number."""

    async def ids(version: str) -> dict[str, uuid.UUID]:
        async with kb_factory() as session:
            rows = (
                await session.execute(
                    select(Extraction.fields["article_no"].as_string(), Extraction.id).where(
                        Extraction.parser_name == STATUTE_PARSER_NAME,
                        Extraction.parser_version == version,
                    )
                )
            ).all()
        return {article_no: extraction_id for article_no, extraction_id in rows}

    return ids


@pytest.fixture
async def statutes_loaded(
    kb_factory: async_sessionmaker[AsyncSession],
    statute_record: dict[str, Any],
    extraction_ids: ExtractionIds,
) -> dict[str, uuid.UUID]:
    """The statute fixture loaded as review-queue rows; returns the extraction ids by article."""
    prepared = statute_loader.prepare([statute_record])
    await statute_loader.load(kb_factory, prepared, {}, StatuteCounts())
    return await extraction_ids("1")


@pytest.fixture
async def statutes_published(
    kb_factory: async_sessionmaker[AsyncSession],
    statutes_loaded: dict[str, uuid.UUID],
    reviewer: AppUser,
) -> dict[str, uuid.UUID]:
    """`statutes_loaded` with `PUBLISHED_ARTICLES` approved and published."""
    async with kb_factory() as session:
        for article_no in PUBLISHED_ARTICLES:
            await approve_statute_article(session, statutes_loaded[article_no], reviewer.id)
        await session.commit()
    return statutes_loaded
