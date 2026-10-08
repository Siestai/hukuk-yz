"""Load statute timelines (task 11a `statutes.jsonl`) into the KB review queue (task 11b).

    python -m app.loaders.statutes statutes.jsonl [--files files.jsonl] [--dry-run]
        [--report DIR] [--approve-band BAND --reviewer USER_ID]

Every snapshot file becomes an `ingest_file` (one per sha256), every statute one `source`
(category `statute`, `official_secondary`, `public`, status `analyzed`) and every article
timeline one `extraction` (parser `statutes`), all under one bulk `ingest_job`. The review unit
is the article, not the statute. No `statute` row is written unless `--approve-band` is given;
that flag is for tests and development (bulk approval belongs to the review screen, 11c).

Idempotency: an article is loaded once per (sha256 set of its statute's snapshots, parser
version, article number); a rerun adds nothing, a new parser version or a new snapshot adds
extractions and leaves the old ones and the published rows alone. As in the decision loader it
is a read-then-insert: concurrent runs are not supported.
"""

import argparse
import asyncio
import json
import sys
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import make_engine, make_session_factory
from app.kb import (
    STATUTE_PARSER_NAME,
    approve_statute_article,
    unpublished_statute_articles,
)
from app.loaders.decisions import error_name, finish_job, is_row_error, read_files
from app.loaders.report import BANDS
from app.loaders.statutes_report import (
    PreparedArticle,
    PreparedStatute,
    StatuteCounts,
    build_summary,
    write_report,
)
from app.models.common import (
    Extraction,
    IngestFile,
    IngestJob,
    IngestKind,
    IngestStatus,
    License,
    RecordStatus,
    Source,
    SourceCategory,
    SourceRank,
)
from app.models.user import AppUser
from app.settings import get_settings
from hukuk_ingest.statutes import confidence as band_rules
from hukuk_models import Band

REQUIRED_KEYS = frozenset(
    {"number", "parser_version", "title", "header", "latest_snapshot_date", "snapshots", "articles"}
)
Key = tuple[str, str, tuple[str, ...]]  # (parser version, article number, sha256 set)


def read_records(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Usable statute records (all keys) and error refs."""
    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                errors.append({"ref": f"satır {number}", "error": "invalid JSON"})
                continue
            if not isinstance(row, dict) or not REQUIRED_KEYS <= row.keys():
                errors.append({"ref": f"satır {number}", "error": "missing record keys"})
            elif any(a["confidence"] not in BANDS for a in row["articles"]):
                errors.append({"ref": f"satır {number} · {row['number']}", "error": "unknown band"})
            else:
                records.append(row)
    return records, errors


def official_ref(number: str, header: dict[str, Any]) -> str:
    """ "4857 sayılı Kanun, RG 10.06.2003 - 25134"; a missing part is left out."""
    parts = [f"{number} sayılı Kanun"]
    if header.get("rg_tarihi"):
        rg = f"RG {date.fromisoformat(header['rg_tarihi']).strftime('%d.%m.%Y')}"
        parts.append(f"{rg} - {header['rg_sayisi']}" if header.get("rg_sayisi") else rg)
    return ", ".join(parts)


def prepare(records: Sequence[dict[str, Any]]) -> list[PreparedStatute]:
    prepared = []
    for r in records:
        shas = sorted(s["sha256"] for s in r["snapshots"])
        articles = []
        for a in r["articles"]:
            reasons = sorted(
                {
                    band_rules.code(w)
                    for w in a["warnings"]
                    if band_rules.RULES.get(band_rules.code(w), band_rules.HIGH) != band_rules.HIGH
                }
            )
            articles.append(
                PreparedArticle(
                    article_no=a["article_no"],
                    fields={
                        **a,
                        "statute_number": r["number"],
                        "statute": r["header"],
                        "snapshot_sha256": shas,
                    },
                    warnings=a["warnings"],
                    confidence={"band": a["confidence"], "reasons": reasons},
                )
            )
        prepared.append(
            PreparedStatute(
                number=r["number"],
                parser_version=r["parser_version"],
                title=r["header"]["title"] or f"{r['number']} sayılı Kanun",
                official_ref=official_ref(r["number"], r["header"]),
                snapshots=[{k: s[k] for k in ("path", "sha256", "date")} for s in r["snapshots"]],
                articles=articles,
            )
        )
    return prepared


@dataclass
class _Known:
    source_id: uuid.UUID | None = None
    keys: set[Key] = field(default_factory=set)


async def _known(
    factory: async_sessionmaker[AsyncSession], numbers: list[str]
) -> dict[str, _Known]:
    """The statutes' source ids and loaded article keys, by statute number."""
    found = {n: _Known() for n in numbers}
    number = Extraction.fields["statute_number"].as_string()
    async with factory() as session:
        result = await session.execute(
            select(
                number,
                Extraction.source_id,
                Extraction.parser_version,
                Extraction.fields["article_no"].as_string(),
                Extraction.fields["snapshot_sha256"],
            )
            .where(Extraction.parser_name == STATUTE_PARSER_NAME, number.in_(numbers))
            .order_by(Extraction.extracted_at)
        )
        for n, source_id, version, article_no, shas in result:
            found[n].source_id = source_id
            found[n].keys.add((version, article_no, tuple(shas)))
    return found


def _key(st: PreparedStatute, a: PreparedArticle) -> Key:
    return (st.parser_version, a.article_no, tuple(st.sha256s))


async def _write_statute(
    session: AsyncSession,
    st: PreparedStatute,
    pending: list[PreparedArticle],
    known: _Known,
    files: dict[str, dict[str, Any]],
    job_id: uuid.UUID,
    counts: StatuteCounts,
) -> None:
    """The files, the source (unless the statute has one) and the pending extractions of one
    statute, in the caller's transaction. `counts` is a scratch copy that the caller merges after
    the commit."""
    file_ids: list[uuid.UUID] = []
    for snap in st.snapshots:
        file_id = (
            await session.execute(
                select(IngestFile.id).where(IngestFile.sha256 == snap["sha256"]).limit(1)
            )
        ).scalar_one_or_none()
        if file_id is None:
            file_id = uuid.uuid4()
            meta = files.get(snap["sha256"], {})
            await session.execute(
                insert(IngestFile),
                {
                    "id": file_id,
                    "job_id": job_id,
                    "path": snap["path"],
                    "sha256": snap["sha256"],
                    "detected_type": meta.get("detected_type"),
                    "size": meta.get("size", 0),
                },
            )
            counts.files_new += 1
        else:
            counts.files_existing += 1
        file_ids.append(file_id)
    source_id = known.source_id
    if source_id is None:
        source_id = uuid.uuid4()
        await session.execute(
            insert(Source),
            {
                "id": source_id,
                "category": SourceCategory.statute,
                "title": st.title,
                "official_ref": st.official_ref,
                "source_rank": SourceRank.official_secondary,
                "license": License.public,
                "status": RecordStatus.analyzed,
            },
        )
        counts.sources_new += 1
    await session.execute(
        insert(Extraction),
        [
            {
                "file_id": file_ids[-1],  # the newest snapshot: the text of the live version
                "source_id": source_id,
                "parser_name": STATUTE_PARSER_NAME,
                "parser_version": st.parser_version,
                "fields": a.fields,
                "confidence": a.confidence,
                "warnings": a.warnings,
            }
            for a in pending
        ],
    )


async def load(
    factory: async_sessionmaker[AsyncSession],
    statutes: list[PreparedStatute],
    files: dict[str, dict[str, Any]],
    counts: StatuteCounts,
) -> uuid.UUID | None:
    """Write what is not in the database yet, one transaction per statute; a statute whose write
    fails for a database reason lands in `counts.errors` and the others go on. Returns the job id,
    or None when nothing was new."""
    known = await _known(factory, [st.number for st in statutes])
    todo = []
    for st in statutes:
        pending = [a for a in st.articles if _key(st, a) not in known[st.number].keys]
        counts.skipped_existing += len(st.articles) - len(pending)
        if pending:
            todo.append((st, pending))
    if not todo:
        return None
    async with factory() as session:
        job = IngestJob(
            kind=IngestKind.bulk, status=IngestStatus.running, started_at=datetime.now(UTC)
        )
        session.add(job)
        await session.commit()
    for st, pending in todo:
        # Counted on a copy, merged after the commit: a rolled-back statute adds nothing.
        done = StatuteCounts()
        try:
            async with factory() as session:
                await _write_statute(session, st, pending, known[st.number], files, job.id, done)
                await session.commit()
        except DBAPIError as exc:
            if not is_row_error(exc):
                raise
            counts.errors.append({"ref": f"{st.number} sayılı Kanun", "error": error_name(exc)})
            continue
        counts.new += len(pending)
        counts.sources_new += done.sources_new
        counts.files_new += done.files_new
        counts.files_existing += done.files_existing
    return job.id


async def approve_band(
    factory: async_sessionmaker[AsyncSession],
    band: Band,
    reviewer_id: uuid.UUID,
    counts: StatuteCounts,
) -> None:
    """Approve and publish (app.kb) the newest unpublished extraction of every article in
    `band`. A record `approve_statute_article` refuses goes to `counts.publish_failed`
    (extraction id, reason); each has its own savepoint, so none stops the run. Development
    and tests only."""
    async with factory() as session:
        ids = (await session.execute(unpublished_statute_articles(band))).scalars().all()
        for extraction_id in ids:
            try:
                await approve_statute_article(session, extraction_id, reviewer_id)
                counts.published += 1
            except ValueError as exc:
                counts.publish_failed.append((str(extraction_id), str(exc)))
        await session.commit()


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.loaders.statutes", description=__doc__)
    p.add_argument("statutes", type=Path, help="statutes.jsonl of `hukuk-ingest statutes`")
    p.add_argument("--files", type=Path, help="files.jsonl of `hukuk-ingest scan` (size, type)")
    p.add_argument("--dry-run", action="store_true", help="no database: only prepare and report")
    p.add_argument("--report", type=Path, help="directory for load-summary.md / .json")
    p.add_argument("--approve-band", choices=list(BANDS), help="dev/test only")
    p.add_argument("--reviewer", type=uuid.UUID, help="id of an existing user, for --approve-band")
    return p


async def _load_to_db(
    args: argparse.Namespace,
    statutes: list[PreparedStatute],
    files: dict[str, dict[str, Any]],
    counts: StatuteCounts,
    start: float,
) -> dict[str, Any]:
    engine = make_engine(get_settings().database_url)
    factory = make_session_factory(engine)
    try:
        if args.approve_band:  # fail before anything is written
            async with factory() as session:
                if await session.get(AppUser, args.reviewer) is None:
                    raise SystemExit(f"no user with id {args.reviewer}")
        job_id = await load(factory, statutes, files, counts)
        if args.approve_band:
            await approve_band(factory, args.approve_band, args.reviewer, counts)
        summary = build_summary(statutes, counts, time.perf_counter() - start, dry_run=False)
        if job_id:
            await finish_job(factory, job_id, summary)
        return summary
    finally:
        await engine.dispose()


async def _run(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    records, errors = read_records(args.statutes)
    files = read_files(args.files) if args.files else {}
    statutes = prepare(records)
    counts = StatuteCounts(errors=errors)
    if args.dry_run:
        counts.new = sum(len(st.articles) for st in statutes)
        counts.sources_new = len(statutes)
        counts.files_new = sum(len(st.snapshots) for st in statutes)
        summary = build_summary(statutes, counts, time.perf_counter() - start, dry_run=True)
    else:
        summary = await _load_to_db(args, statutes, files, counts, start)
    if args.report:
        write_report(summary, args.report)
    print(
        f"articles {summary['articles']}, new {summary['new']}, skipped {summary['skipped']}, "
        f"errors {summary['errors']}, bands {summary['bands']}, versions {summary['versions']}, "
        f"gaps {summary['gaps']}, published {summary['published']}"
    )
    for ref, reason in counts.publish_failed:
        print(f"publish_failed: {ref}: {reason}")
    return 1 if summary["errors"] else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.approve_band and (args.dry_run or not args.reviewer):
        parser.error("--approve-band needs --reviewer and cannot be combined with --dry-run")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
