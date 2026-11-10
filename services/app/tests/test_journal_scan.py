"""The weekly journal scan (task 20) against a fake site and a real database. The database tests
are skipped when DATABASE_URL is unset; CI sets it."""

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.files.store import LocalFileStore, blob_key, text_key
from app.journal import enqueue as enqueue_module
from app.journal import scan as scan_module
from app.journal.client import FetchError, Params, Reply
from app.journal.enqueue import JournalPost, Read
from app.journal.scan import LOCK_KEY, Outcome, _parser, describe, scan
from app.loaders.decisions import load, prepare
from app.loaders.report import LoadCounts
from app.models.common import (
    Extraction,
    IngestFile,
    IngestJob,
    IngestKind,
    IngestStatus,
    License,
    ReviewStatus,
    ScanStatus,
    Source,
    SourceRank,
)
from app.models.decision import Decision
from app.models.journal import JournalScan
from hukuk_ingest.decisions.parse import ARCHIVE_DIR, parse_text

Factory = async_sessionmaker[AsyncSession]
BASE = "https://yargi.calismatoplum.org"
PDF_MAGIC_BODY = b"%PDF-1.4\n"


def page_html(pdf_url: str | None) -> str:
    link = (
        f'<a href="{pdf_url}" class="jet-listing-dynamic-link__link" target="_blank">PDF</a>'
        if pdf_url
        else ""
    )
    return (
        f'<html><body><a href="{BASE}/other.pdf" class="menu">Eski</a>'
        f'<div class="jet-listing-dynamic-link">{link}</div></body></html>'
    )


@dataclass
class FakeSite:
    """`issues`: issue number -> list of (post id, slug, pdf bytes or None for "no link");
    `categories`: extra raw category rows. Anything not served is a 404."""

    issues: dict[int, list[tuple[int, str, bytes | None]]] = field(default_factory=dict)
    per_page: int = 100
    broken_api: bool = False
    pdf_overrides: dict[str, Reply] = field(default_factory=dict)
    requests: list[str] = field(default_factory=list)

    def _category_id(self, issue_no: int) -> int:
        return 6000 + issue_no

    def pdf_url(self, issue_no: int, post_id: int) -> str:
        return f"{BASE}/wp-content/uploads/2026/10/{issue_no}-{post_id}.pdf"

    def page_url(self, slug: str) -> str:
        return f"{BASE}/{slug}/"

    async def get(self, url: str, params: Params | None = None) -> Reply:
        self.requests.append(url)
        params = params or {}
        if self.broken_api and "/wp-json/" in url:
            raise FetchError(url, "http_503")
        if url == f"{BASE}/wp-json/wp/v2/categories":
            rows = [
                {"id": self._category_id(no), "slug": f"{no}-sayi-yargi-kararlari"}
                for no in sorted(self.issues)
            ]
            return self._paged(rows, params)
        if url == f"{BASE}/wp-json/wp/v2/posts":
            category = int(params["categories"])
            rows = [
                {"id": post_id, "link": self.page_url(slug)}
                for no, posts in self.issues.items()
                if self._category_id(no) == category
                for post_id, slug, _ in posts
            ]
            return self._paged(rows, params)
        if url in self.pdf_overrides:
            return self.pdf_overrides[url]
        for no, posts in self.issues.items():
            for post_id, slug, pdf in posts:
                if url == self.page_url(slug):
                    return Reply(
                        200, {}, page_html(self.pdf_url(no, post_id) if pdf else None).encode()
                    )
                if pdf is not None and url == self.pdf_url(no, post_id):
                    return Reply(200, {}, pdf)
        raise FetchError(url, "http_404")

    def _paged(self, rows: Sequence[Mapping[str, object]], params: Params) -> Reply:
        size = int(params.get("per_page", 100))
        size = min(size, self.per_page)
        page = int(params.get("page", 1))
        pages = max(-(-len(rows) // size), 1)
        body = json.dumps(rows[(page - 1) * size : page * size]).encode()
        return Reply(200, {"X-WP-TotalPages": str(pages), "X-WP-Total": str(len(rows))}, body)


FILLER = "Örnek gerekçe cümlesi uydurma bir metindir. " * 25


def decision_text(esas: str, karar: str, chamber: str = "9. HUKUK DAİRESİ") -> str:
    """A synthetic decision in the journal's second layout (names and numbers are made up)."""
    return (
        "Yargıtay Kararları\n117\n"
        f"İlgili Kanun / Madde\n4857 S. İşK/18-21\nT.C\nYARGITAY\n{chamber}\n"
        f"Esas No. {esas}\nKarar No. {karar}\nTarihi: 07.06.2021\n"
        "• ÖRNEK ANAHTAR\nÖZETİ: Örnek özet.\n"
        "DAVA: Davacı, örnek talebin kabulünü istemiştir.\n"
        f"{FILLER}\nSONUÇ: Temyiz olunan kararın BOZULMASINA, 07.06.2021 gününde "
        "oybirliğiyle karar verildi."
    )


@pytest.fixture
def texts(monkeypatch: pytest.MonkeyPatch) -> dict[bytes, str]:
    """PDFs by content -> the decision text the parser reads from them. A PDF that is not in the
    registry goes through the real extraction."""
    registry: dict[bytes, str] = {}
    real = enqueue_module.read_pdf

    def read(content: bytes, post: JournalPost) -> Read:
        if content not in registry:
            return real(content, post)
        sha = hashlib.sha256(content).hexdigest()
        path = f"{ARCHIVE_DIR}/{post.issue_no}. Sayı/{post.name}"
        record = parse_text(registry[content], path, sha)
        return Read(record, {"extractor": "fake"}, registry[content])

    monkeypatch.setattr(enqueue_module, "read_pdf", read)
    return registry


def pdf(texts: dict[bytes, str], esas: str, karar: str, **kwargs: str) -> bytes:
    """A distinct PDF whose parsed text is the synthetic decision of this E/K."""
    content = b"%PDF-1.4\n%" + f"{esas}|{karar}|{len(texts)}".encode() + b"\n%%EOF\n"
    texts[content] = decision_text(esas, karar, **kwargs)
    return content


def issue_posts(
    texts: dict[bytes, str], issue: int, count: int
) -> list[tuple[int, str, bytes | None]]:
    return [
        (issue * 100 + n, f"karar-{issue}-{n}", pdf(texts, f"2020/{issue}{n:02d}", f"2021/{n}"))
        for n in range(count)
    ]


async def archive(
    factory: Factory, issue: int = 90, esas: str = "2019/1", karar: str = "2020/1", **kw: str
) -> uuid.UUID:
    """A decision of the archive, loaded the way task 05 does (job kind `bulk`); its source id."""
    record = parse_text(
        decision_text(esas, karar, **kw),
        f"{ARCHIVE_DIR}/{issue}. Sayı/{esas.replace('/', '-')}.pdf",
        hashlib.sha256(f"{issue}{esas}{karar}".encode()).hexdigest(),
    )
    prepared, _ = prepare([record.to_dict()], {})
    await load(factory, prepared, LoadCounts())
    async with factory() as session:
        source_id = (
            await session.execute(
                select(Extraction.source_id)
                .join(IngestFile, IngestFile.id == Extraction.file_id)
                .where(IngestFile.sha256 == record.sha256)
            )
        ).scalar_one()
    assert source_id is not None
    return source_id


async def count(factory: Factory, model: Any) -> int:
    async with factory() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


def stored_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


@pytest.fixture
def store(tmp_path: Path) -> LocalFileStore:
    return LocalFileStore(tmp_path / "store")


async def test_a_new_issue_is_found_and_the_ones_of_the_archive_are_skipped(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    site = FakeSite(
        {
            89: issue_posts(texts, 89, 2),
            90: issue_posts(texts, 90, 2),
            91: issue_posts(texts, 91, 2),
        }
    )
    outcome = await scan(kb_factory, store, site)
    assert (outcome.status, outcome.new_issues) == ("completed", [91])
    assert [i.issue_no for i in outcome.report.issues] == [91]
    assert not [url for url in site.requests if "karar-89" in url or "karar-90" in url]


async def test_a_scanned_decision_waits_in_the_queue_with_its_provenance(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    posts = issue_posts(texts, 91, 5)
    site = FakeSite({91: posts}, per_page=2)  # the pages of the post list are followed
    outcome = await scan(kb_factory, store, site)
    assert (outcome.totals.discovered, outcome.totals.downloaded, outcome.totals.queued) == (
        5,
        5,
        5,
    )
    async with kb_factory() as session:
        scan_row = (await session.execute(select(JournalScan))).scalar_one()
        job = await session.get(IngestJob, scan_row.job_id)
        assert job is not None
        assert (job.kind, job.created_by, job.status) == (
            IngestKind.crawl,
            None,
            IngestStatus.completed,
        )
        assert (scan_row.trigger, scan_row.status, scan_row.new_issues) == (
            "schedule",
            "completed",
            [91],
        )
        assert (scan_row.discovered, scan_row.downloaded, scan_row.queued, scan_row.errors) == (
            5,
            5,
            5,
            0,
        )
        files = (
            (await session.execute(select(IngestFile).where(IngestFile.job_id == job.id)))
            .scalars()
            .all()
        )
        assert len(files) == 5
        first = min(files, key=lambda f: f.scan_result["journal"]["post_id"])  # type: ignore[index]
        post_id, slug, content = posts[0]
        sha = hashlib.sha256(content or b"").hexdigest()
        assert (first.sha256, first.storage_key, first.uploaded_by) == (sha, blob_key(sha), None)
        assert first.origin_url == site.pdf_url(91, post_id)
        assert first.scan_result["journal"] == {  # type: ignore[index]
            "issue_no": 91,
            "post_id": post_id,
            "page_url": site.page_url(slug),
            "pdf_url": site.pdf_url(91, post_id),
        }
        assert first.scan_result["text_key"] == text_key(sha)  # type: ignore[index]
        assert (first.scan_status, first.review_status) == (ScanStatus.done, ReviewStatus.approved)
        assert first.approved_by is None
        assert store.exists(blob_key(sha)) and store.exists(text_key(sha))
        extraction = (
            await session.execute(select(Extraction).where(Extraction.file_id == first.id))
        ).scalar_one()
        source = await session.get(Source, extraction.source_id)
        assert source is not None
        assert (source.status.value, source.source_rank, source.license) == (
            "analyzed",
            SourceRank.editorial,
            License.unknown,
        )
        assert extraction.fields["verification"] == "unverified"
        assert (extraction.journal_issue, extraction.esas_no) == (91, "2020/9100")
        assert extraction.confidence["band"] == "high"  # scored like an archive record
    assert await count(kb_factory, Decision) == 0  # nothing approved, nothing published


async def test_a_second_run_of_the_same_issue_writes_nothing(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    site = FakeSite({91: issue_posts(texts, 91, 3)})
    await scan(kb_factory, store, site, only_issue=91)
    before = [await count(kb_factory, m) for m in (IngestFile, Extraction, Source)]
    blobs = len(stored_files(store.root))
    again = await scan(kb_factory, store, site, only_issue=91)
    assert [await count(kb_factory, m) for m in (IngestFile, Extraction, Source)] == before
    assert len(stored_files(store.root)) == blobs
    assert (again.totals.downloaded, again.totals.queued, again.totals.duplicates) == (0, 0, 3)
    # the scheduled run no longer sees a new issue: the archive has 91 now
    assert (await scan(kb_factory, store, site)).new_issues == []
    assert await count(kb_factory, JournalScan) == 3


class Crash(BaseException):
    """The process dies: not an error the scan can catch."""


async def test_an_interrupted_scan_goes_on_where_it_stopped(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    posts = issue_posts(texts, 91, 4)
    site = FakeSite({91: posts})
    original = site.get

    async def dying(url: str, params: Any = None) -> Reply:
        if url == site.pdf_url(91, posts[2][0]):
            raise Crash
        return await original(url, params)

    site.get = dying  # type: ignore[method-assign]
    with pytest.raises(Crash):
        await scan(kb_factory, store, site)
    assert await count(kb_factory, Extraction) == 1 + 2  # the archive record and two decisions
    async with kb_factory() as session:
        assert (await session.execute(select(JournalScan.status))).scalar_one() == "running"

    site.get = original  # type: ignore[method-assign]
    outcome = await scan(kb_factory, store, site)  # not `--issue`: 91 is carried over
    assert (outcome.new_issues, outcome.status) == ([91], "completed")
    assert (outcome.totals.downloaded, outcome.totals.duplicates) == (2, 2)
    assert await count(kb_factory, Extraction) == 1 + 4
    async with kb_factory() as session:
        rows = (
            (await session.execute(select(JournalScan).order_by(JournalScan.started_at)))
            .scalars()
            .all()
        )
    assert [r.status for r in rows] == ["failed", "completed"]
    assert rows[0].report["failure"] == "interrupted" and rows[0].finished_at is not None


async def test_a_page_that_is_not_a_pdf_is_an_error_and_is_not_stored(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    posts = issue_posts(texts, 91, 3)
    site = FakeSite({91: posts})
    bad = site.pdf_url(91, posts[1][0])
    site.pdf_overrides[bad] = Reply(200, {}, b"<html><body>Hata</body></html>")
    outcome = await scan(kb_factory, store, site)
    assert outcome.status == "completed_with_errors"
    assert (outcome.totals.downloaded, outcome.totals.errors) == (2, 1)
    [error] = outcome.report.issues[0].errors
    assert (error.url, error.reason) == (bad, "not_a_pdf")
    assert await count(kb_factory, IngestFile) == 1 + 2
    assert len([p for p in stored_files(store.root) if p.parts[-4] == "sha256"]) == 2


async def test_a_decision_page_without_a_pdf_link_is_an_error(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    posts = issue_posts(texts, 91, 2)
    posts[1] = (posts[1][0], posts[1][1], None)
    site = FakeSite({91: posts})
    outcome = await scan(kb_factory, store, site)
    [error] = outcome.report.issues[0].errors
    assert (error.url, error.reason) == (site.page_url(posts[1][1]), "pdf_link_missing")
    assert (outcome.totals.queued, outcome.totals.errors) == (1, 1)


async def test_a_file_that_is_in_the_database_is_a_duplicate_and_adds_no_row(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    same = pdf(texts, "2022/5", "2022/6")
    site = FakeSite({91: [(9101, "bir", same), (9102, "iki", same)]})
    outcome = await scan(kb_factory, store, site)
    assert (outcome.totals.downloaded, outcome.totals.duplicates) == (1, 1)
    assert await count(kb_factory, IngestFile) == 2


async def test_a_decision_the_archive_has_is_queued_as_a_duplicate_candidate(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    old = await archive(kb_factory, issue=90, esas="2020/9100", karar="2021/0")
    await archive(kb_factory, issue=90, esas="2019/2", karar="2020/2")
    async with kb_factory() as session:
        await session.execute(
            text("UPDATE source SET status = 'approved' WHERE id = :id"), {"id": old}
        )
        await session.commit()
        before = (
            await session.execute(
                select(Extraction.id, Extraction.fields).where(Extraction.source_id == old)
            )
        ).all()
    site = FakeSite({91: issue_posts(texts, 91, 2)})  # the first one has the old E/K
    outcome = await scan(kb_factory, store, site)
    assert (outcome.totals.queued, outcome.report.issues[0].duplicate_candidates) == (2, 1)
    async with kb_factory() as session:
        groups = (
            await session.execute(
                select(Extraction.esas_no, Extraction.duplicate_group, Extraction.confidence)
                .join(IngestFile, IngestFile.id == Extraction.file_id)
                .where(IngestFile.origin_url.is_not(None))
                .order_by(Extraction.esas_no)
            )
        ).all()
        candidate, other = groups
        assert candidate.duplicate_group["key"][-2:] == ["2020/9100", "2021/0"]
        assert candidate.confidence["band"] != "high"  # the shorter, same text copy: not bulk
        assert other.duplicate_group is None
        # the record of the archive is as it was: still approved, same fields
        kept = await session.get(Source, old)
        assert kept is not None and kept.status.value == "approved"
        after = (
            await session.execute(
                select(Extraction.id, Extraction.fields).where(Extraction.source_id == old)
            )
        ).all()
    assert [tuple(r) for r in after] == [tuple(r) for r in before]


async def test_a_file_the_parser_cannot_read_still_reaches_the_queue(
    kb_factory: Factory, store: LocalFileStore, make_pdf: Any
) -> None:
    await archive(kb_factory, issue=90)
    site = FakeSite({91: [(9101, "okunamayan", make_pdf("just some plain words"))]})
    outcome = await scan(kb_factory, store, site)  # no registry: the real extraction runs
    assert (outcome.totals.queued, outcome.totals.errors) == (1, 0)
    async with kb_factory() as session:
        extraction = (
            await session.execute(
                select(Extraction).join(IngestFile).where(IngestFile.origin_url.is_not(None))
            )
        ).scalar_one()
    assert extraction.fields["esas_no"] == "" and extraction.journal_issue == 91
    assert extraction.confidence["band"] == "low" and extraction.confidence["reasons"]


async def test_a_dry_run_writes_nothing_and_reports_the_links(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    posts = issue_posts(texts, 91, 3)
    posts.append((9199, "linksiz", None))
    site = FakeSite({90: [], 91: posts})
    tables = (JournalScan, IngestJob, IngestFile, Extraction)
    before = [await count(kb_factory, m) for m in tables]
    outcome = await scan(kb_factory, None, site, dry_run=True)
    assert [await count(kb_factory, m) for m in tables] == before
    assert not stored_files(store.root)
    assert (outcome.status, outcome.new_issues) == ("dry_run", [91])
    [issue] = outcome.report.issues
    assert (issue.site_count, issue.pdf_links, issue.downloaded) == (4, 3, 0)
    assert [e.reason for e in issue.errors] == ["pdf_link_missing"]
    assert not [url for url in site.requests if url.endswith(".pdf")]  # no PDF was fetched
    assert "issue 91: 4 decisions on the site, 3 PDF links" in describe(outcome)


async def test_a_second_scan_at_the_same_time_is_skipped(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    site = FakeSite({91: issue_posts(texts, 91, 2)})
    async with kb_factory() as holder:
        await holder.execute(select(func.pg_advisory_lock(LOCK_KEY)))
        try:
            outcome = await scan(kb_factory, store, site)
        finally:
            await holder.execute(select(func.pg_advisory_unlock(LOCK_KEY)))
    assert outcome.status == "skipped"
    assert not site.requests
    assert await count(kb_factory, JournalScan) == 0
    assert (await scan(kb_factory, store, site)).status == "completed"  # the lock was let go


async def lock_is_free(factory: Factory) -> bool:
    async with factory() as probe:
        got = (await probe.execute(select(func.pg_try_advisory_lock(LOCK_KEY)))).scalar_one()
        if got:
            await probe.execute(select(func.pg_advisory_unlock(LOCK_KEY)))
        return bool(got)


class Boom(Exception):
    pass


class BoomSite:
    async def get(self, url: str, params: Params | None = None) -> Reply:
        raise Boom("site exploded")


async def test_the_lock_is_released_when_the_scan_raises(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    await archive(kb_factory, issue=90)
    with pytest.raises(Boom):
        await scan(kb_factory, store, BoomSite())
    assert await lock_is_free(kb_factory)


async def test_a_failed_unlock_drops_the_connection_and_keeps_the_original_error(
    kb_factory: Factory, store: LocalFileStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenUnlock:
        def __getattr__(self, name: str) -> Any:
            return getattr(func, name)

        def pg_advisory_unlock(self, key: int) -> Any:
            raise RuntimeError("unlock failed")

    await archive(kb_factory, issue=90)
    monkeypatch.setattr(scan_module, "func", BrokenUnlock())
    with pytest.raises(Boom):  # not the RuntimeError of the unlock
        await scan(kb_factory, store, BoomSite())
    monkeypatch.undo()
    assert await lock_is_free(kb_factory)  # the connection holding the lock is gone


async def test_a_site_whose_api_is_down_fails_the_scan_with_the_reason(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    await archive(kb_factory, issue=90)
    outcome = await scan(kb_factory, store, FakeSite(broken_api=True))
    assert outcome.status == "failed"
    async with kb_factory() as session:
        row = (await session.execute(select(JournalScan))).scalar_one()
        job = await session.get(IngestJob, row.job_id)
    assert (row.status, row.finished_at is not None) == ("failed", True)
    assert "http_503" in row.report["failure"]
    assert job is not None and job.status is IngestStatus.failed


async def test_an_empty_archive_is_not_scanned_but_an_issue_can_be_asked_for(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    site = FakeSite({1: issue_posts(texts, 1, 1), 2: issue_posts(texts, 2, 1)})
    refused = await scan(kb_factory, store, site)
    assert (refused.status, refused.report.failure) == ("failed", "archive_empty")
    assert await count(kb_factory, IngestFile) == 0
    manual = await scan(kb_factory, store, site, only_issue=2)
    assert (manual.status, manual.totals.queued) == ("completed", 1)
    async with kb_factory() as session:
        trigger = (
            (
                await session.execute(
                    select(JournalScan.trigger).order_by(JournalScan.started_at.desc())
                )
            )
            .scalars()
            .first()
        )
    assert trigger == "manual"


async def test_an_issue_the_site_does_not_have_fails_the_run(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    outcome = await scan(kb_factory, store, FakeSite({1: []}), only_issue=7)
    assert (outcome.status, outcome.report.failure) == ("failed", "issue_not_found:7")


async def test_an_old_issue_asked_for_by_number_still_meets_the_duplicate_rules(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90, esas="2020/8900", karar="2021/0")
    posts = issue_posts(texts, 89, 2)
    site = FakeSite({89: posts})
    outcome = await scan(kb_factory, store, site, only_issue=89)
    assert (outcome.totals.queued, outcome.report.issues[0].duplicate_candidates) == (2, 1)


def test_the_command_line_takes_dry_run_and_issue() -> None:
    args = _parser().parse_args(["--dry-run", "--issue", "91"])
    assert (args.dry_run, args.issue) == (True, 91)
    assert _parser().parse_args([]).issue is None


def test_the_site_address_is_the_journal() -> None:
    assert JournalPost(91, 1, f"{BASE}/a-b/", f"{BASE}/x.pdf").name == "a-b.pdf"


def test_outcome_text_names_the_failure() -> None:
    outcome = Outcome("failed")
    outcome.report.failure = "archive_empty"
    assert "failure: archive_empty" in describe(outcome)


async def test_a_manual_run_after_a_failed_scheduled_one_keeps_its_issues_for_the_next(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    posts = issue_posts(texts, 91, 3)
    site = FakeSite({85: issue_posts(texts, 85, 1), 91: posts})
    original = site.get

    async def dying(url: str, params: Any = None) -> Reply:
        if url == site.pdf_url(91, posts[1][0]):
            raise Crash
        return await original(url, params)

    site.get = dying  # type: ignore[method-assign]
    with pytest.raises(Crash):
        await scan(kb_factory, store, site)
    site.get = original  # type: ignore[method-assign]
    manual = await scan(kb_factory, store, site, only_issue=85)
    assert (manual.status, manual.new_issues) == ("completed", [85])

    outcome = await scan(kb_factory, store, site)  # the scheduled run retries 91
    assert (outcome.new_issues, outcome.status) == ([91], "completed")
    assert await count(kb_factory, Extraction) == 1 + 1 + 3
    again = await scan(kb_factory, store, site)  # a completed scheduled run ends the carry
    assert again.new_issues == []


async def test_the_report_names_the_archive_max_and_warns_when_the_site_is_behind_it(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=2026)  # a year read as the issue number
    outcome = await scan(kb_factory, store, FakeSite({90: issue_posts(texts, 90, 1)}))
    assert outcome.report.archive_max == 2026
    assert outcome.report.warnings == ["archive_max_above_site:2026"]
    assert "warning: archive_max_above_site:2026" in describe(outcome)
    sane = await scan(kb_factory, store, FakeSite({2027: []}))
    assert (sane.report.archive_max, sane.report.warnings) == (2026, [])


async def test_a_pdf_that_redirects_off_the_site_is_an_error_and_nothing_is_stored(
    kb_factory: Factory, store: LocalFileStore, texts: dict[bytes, str]
) -> None:
    await archive(kb_factory, issue=90)
    posts = issue_posts(texts, 91, 2)
    site = FakeSite({91: posts})
    original = site.get

    async def refusing(url: str, params: Any = None) -> Reply:
        if url == site.pdf_url(91, posts[0][0]):
            raise FetchError(url, "redirect_refused")  # what PoliteClient raises
        return await original(url, params)

    site.get = refusing  # type: ignore[method-assign]
    outcome = await scan(kb_factory, store, site)
    assert (outcome.status, outcome.totals.errors, outcome.totals.queued) == (
        "completed_with_errors",
        1,
        1,
    )
    assert [e.reason for e in outcome.report.issues[0].errors] == ["redirect_refused"]
    assert await count(kb_factory, Extraction) == 1 + 1
