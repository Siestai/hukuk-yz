"""Load the decision archive (task 04 `decisions.jsonl`) into the KB review queue (task 05).

    python -m app.loaders.decisions decisions.jsonl [--files files.jsonl] [--dry-run]
        [--report DIR] [--approve-band BAND --reviewer USER_ID]

Every decision file becomes `ingest_file` + `source` (status `analyzed`) + `extraction` with a
confidence score, all under one `ingest_job`. No `decision` row is written unless
`--approve-band` is given; that flag is for tests and development.
"""

import argparse
import asyncio
import json
import sys
import time
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field, fields
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import make_engine, make_session_factory
from app.kb import publish_decision
from app.loaders.confidence import confidence
from app.loaders.normalize import normalize
from app.loaders.report import LoadCounts, PreparedRecord, build_summary, write_report
from app.models.common import (
    Extraction,
    IngestFile,
    IngestJob,
    IngestKind,
    IngestStatus,
    License,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
    SourceCategory,
    SourceRank,
)
from app.settings import get_settings
from hukuk_ingest.decisions.parse import DecisionRecord
from hukuk_ingest.decisions.report import dup_kind

PARSER_NAME = "decisions"
BATCH = 500
REQUIRED_KEYS = frozenset(f.name for f in fields(DecisionRecord))
COURT_LABELS = {
    "yargitay": "Yargıtay",
    "danistay": "Danıştay",
    "bam": "BAM",
    "bim": "BİM",
    "aym": "AYM",
    "aihm": "AİHM",
    "abad": "ABAD",
    "ilk_derece": "İlk derece",
    "foreign": "Yabancı mahkeme",
}


def read_rows(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]], int]:
    """Usable rows (all parser keys, status `ok`), error refs, and the total of lines read."""
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    total = 0
    with path.open(encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            total += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                errors.append({"ref": f"satır {number}", "error": "invalid JSON"})
                continue
            if not isinstance(row, dict) or not REQUIRED_KEYS <= row.keys():
                errors.append({"ref": f"satır {number}", "error": "missing parser keys"})
            elif row["status"] != "ok":
                errors.append(
                    {"ref": f"satır {number} · {row['sha256'][:12]}", "error": "parse error"}
                )
            else:
                rows.append(row)
    return rows, errors, total


def read_files(path: Path) -> dict[str, dict[str, Any]]:
    """Task 03 `files.jsonl` rows by sha256."""
    with path.open(encoding="utf-8") as fh:
        return {row["sha256"]: row for row in map(json.loads, fh) if row["sha256"]}


def official_ref(f: dict[str, Any]) -> str | None:
    """ "Yargıtay 9. HD, E. 2017/16188 K. 2019/1234, 12.03.2019"; a missing part is left out."""
    court = " ".join(
        p for p in (f["bam_region"], COURT_LABELS.get(f["court"], ""), f["chamber"]) if p
    )
    numbers = " ".join(
        p
        for p in (
            f"E. {f['esas_no']}" if f["esas_no"] else "",
            f"K. {f['karar_no']}" if f["karar_no"] else "",
        )
        if p
    )
    when = date.fromisoformat(f["decision_date"]).strftime("%d.%m.%Y") if f["decision_date"] else ""
    return ", ".join(p for p in (court, numbers, when) if p) or None


def _group_key(f: dict[str, Any]) -> tuple[str, str, str, str, str] | None:
    if not (f["esas_no"] and f["karar_no"]):
        return None
    return (f["court"], f["bam_region"], f["chamber"], f["esas_no"], f["karar_no"])


def prepare(
    rows: Sequence[dict[str, Any]], files: dict[str, dict[str, Any]]
) -> tuple[list[PreparedRecord], int]:
    """Normalize, group duplicates and score. A sha256 seen twice is one record (the second
    occurrence is only counted; returned as the second value)."""
    seen: set[str] = set()
    normalized: list[tuple[dict[str, Any], dict[str, Any], list[str]]] = []
    for row in rows:
        if row["sha256"] in seen:
            continue
        seen.add(row["sha256"])
        fields_, added = normalize(row)
        normalized.append((row, fields_, [*row["warnings"], *added]))

    groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for i, (_, f, _) in enumerate(normalized):
        if group_key := _group_key(f):
            groups[group_key].append(i)
    for key, members in groups.items():
        if len(members) < 2:
            continue
        kind = dup_kind(
            [
                DecisionRecord(
                    source_path="",
                    sha256="",
                    decision_date=normalized[i][1]["decision_date"],
                    full_text=normalized[i][1]["full_text"],
                )
                for i in members
            ]
        )
        longest = max(members, key=lambda i: len(normalized[i][1]["full_text"]))
        for i in members:
            normalized[i][1]["duplicate_group"] = {"key": list(key), "dup_kind": kind}
            if kind == "same_text" and i != longest:
                normalized[i][2].append("duplicate_of")

    prepared = []
    for row, f, warnings in normalized:
        meta = files.get(row["sha256"], {})
        sha = row["sha256"]
        prepared.append(
            PreparedRecord(
                sha256=sha,
                source_path=row["source_path"],
                title=Path(row["source_path"]).stem,
                official_ref=official_ref(f),
                size=meta.get("size", 0),
                detected_type=meta.get("detected_type"),
                parser_version=row["parser_version"],
                fields=f,
                warnings=warnings,
                confidence=confidence(f, warnings),
                raw_text_ref=f"data/extracted/{sha[:2]}/{sha}.clean.txt",
            )
        )
    return prepared, len(rows) - len(seen)


@dataclass
class _Existing:
    file_id: uuid.UUID
    source_id: uuid.UUID
    versions: set[str] = field(default_factory=set)


async def _existing(
    factory: async_sessionmaker[AsyncSession], shas: list[str]
) -> dict[str, _Existing]:
    """Files already extracted by this parser, by sha256."""
    found: dict[str, _Existing] = {}
    async with factory() as session:
        for start in range(0, len(shas), BATCH):
            result = await session.execute(
                select(
                    IngestFile.sha256,
                    IngestFile.id,
                    Extraction.source_id,
                    Extraction.parser_version,
                )
                .join(Extraction, Extraction.file_id == IngestFile.id)
                .where(
                    Extraction.parser_name == PARSER_NAME,
                    IngestFile.sha256.in_(shas[start : start + BATCH]),
                )
            )
            for sha, file_id, source_id, version in result:
                if source_id is None:
                    continue
                found.setdefault(sha, _Existing(file_id, source_id)).versions.add(version)
    return found


async def _write(
    session: AsyncSession,
    items: list[PreparedRecord],
    existing: dict[str, _Existing],
    job_id: uuid.UUID,
) -> None:
    """One batch with executemany inserts. A file already loaded under an older parser version
    keeps its ingest_file and source; only a new extraction is added."""
    new_files: list[dict[str, Any]] = []
    new_sources: list[dict[str, Any]] = []
    extractions: list[dict[str, Any]] = []
    for p in items:
        if old := existing.get(p.sha256):
            file_id, source_id = old.file_id, old.source_id
        else:
            file_id, source_id = uuid.uuid4(), uuid.uuid4()
            new_sources.append(
                {
                    "id": source_id,
                    "category": SourceCategory.decision,
                    "title": p.title,
                    "official_ref": p.official_ref,
                    "source_rank": SourceRank.editorial,
                    "license": License.unknown,
                    "status": RecordStatus.analyzed,
                }
            )
            new_files.append(
                {
                    "id": file_id,
                    "job_id": job_id,
                    "path": p.source_path,
                    "sha256": p.sha256,
                    "detected_type": p.detected_type,
                    "size": p.size,
                }
            )
        extractions.append(
            {
                "file_id": file_id,
                "source_id": source_id,
                "parser_name": PARSER_NAME,
                "parser_version": p.parser_version,
                "fields": p.fields,
                "confidence": p.confidence,
                "warnings": p.warnings,
                "raw_text_ref": p.raw_text_ref,
            }
        )
    if new_sources:
        await session.execute(insert(Source), new_sources)
        await session.execute(insert(IngestFile), new_files)
    await session.execute(insert(Extraction), extractions)


def _error_name(exc: Exception) -> str:
    """Exception class only: SQLAlchemy messages carry the statement parameters (decision text)."""
    return type(getattr(exc, "orig", None) or exc).__name__


async def load(
    factory: async_sessionmaker[AsyncSession], prepared: list[PreparedRecord], counts: LoadCounts
) -> uuid.UUID | None:
    """Write what is not in the database yet (key: sha256 + parser name + parser version) in
    batches of 500, one commit each; a failed batch is retried row by row so that only the bad
    rows end up in `counts.errors`. Returns the job id, or None when nothing was new."""
    existing = await _existing(factory, [p.sha256 for p in prepared])
    pending = [
        p
        for p in prepared
        if p.sha256 not in existing or p.parser_version not in existing[p.sha256].versions
    ]
    counts.skipped_existing = len(prepared) - len(pending)
    if not pending:
        return None
    async with factory() as session:
        job = IngestJob(
            kind=IngestKind.bulk, status=IngestStatus.running, started_at=datetime.now(UTC)
        )
        session.add(job)
        await session.commit()
    for start in range(0, len(pending), BATCH):
        batch = pending[start : start + BATCH]
        try:
            async with factory() as session:
                await _write(session, batch, existing, job.id)
                await session.commit()
            counts.new += len(batch)
        except Exception:
            for p in batch:
                try:
                    async with factory() as session:
                        await _write(session, [p], existing, job.id)
                        await session.commit()
                    counts.new += 1
                except Exception as exc:
                    counts.errors.append({"ref": p.ref, "error": _error_name(exc)})
    return job.id


async def finish_job(
    factory: async_sessionmaker[AsyncSession], job_id: uuid.UUID, summary: dict[str, Any]
) -> None:
    async with factory() as session:
        await session.execute(
            update(IngestJob)
            .where(IngestJob.id == job_id)
            .values(status=IngestStatus.completed, finished_at=datetime.now(UTC), stats=summary)
        )
        await session.commit()


@dataclass
class ApproveResult:
    published: int = 0
    conflicts: list[str] = field(default_factory=list)


async def approve_band(
    factory: async_sessionmaker[AsyncSession], band: str, reviewer_id: uuid.UUID
) -> ApproveResult:
    """Approve every `analyzed` decision extraction of a band and publish it (kb.py). A live-key
    collision rolls that one back and is listed in `conflicts` (sha256 prefix). Development and
    tests only: bulk approval belongs to the review screen."""
    result = ApproveResult()
    async with factory() as session:
        queue = (
            await session.execute(
                select(Extraction.id, IngestFile.sha256)
                .join(IngestFile, IngestFile.id == Extraction.file_id)
                .join(Source, Source.id == Extraction.source_id)
                .where(
                    Extraction.parser_name == PARSER_NAME,
                    Extraction.confidence["band"].as_string() == band,
                    Source.category == SourceCategory.decision,
                    Source.status == RecordStatus.analyzed,
                )
                .order_by(IngestFile.sha256)
            )
        ).all()
        for extraction_id, sha in queue:
            try:
                async with session.begin_nested():
                    review = Review(
                        extraction_id=extraction_id,
                        reviewer_id=reviewer_id,
                        decision=ReviewDecision.approve,
                    )
                    session.add(review)
                    await session.flush()
                    await publish_decision(session, extraction_id, review.id)
                result.published += 1
            except IntegrityError:
                result.conflicts.append(sha[:12])
            if (result.published + len(result.conflicts)) % BATCH == 0:
                await session.commit()
        await session.commit()
    return result


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.loaders.decisions", description=__doc__)
    p.add_argument("decisions", type=Path, help="decisions.jsonl of `hukuk-ingest decisions parse`")
    p.add_argument("--files", type=Path, help="files.jsonl of `hukuk-ingest scan` (size, type)")
    p.add_argument("--dry-run", action="store_true", help="no database: only prepare and report")
    p.add_argument("--report", type=Path, help="directory for load-summary.md / .json")
    p.add_argument("--approve-band", choices=["high", "medium", "low"], help="dev/test only")
    p.add_argument("--reviewer", type=uuid.UUID, help="reviewer user id for --approve-band")
    return p


async def _load_to_db(
    args: argparse.Namespace, prepared: list[PreparedRecord], counts: LoadCounts, start: float
) -> dict[str, Any]:
    engine = make_engine(get_settings().database_url)
    factory = make_session_factory(engine)
    try:
        job_id = await load(factory, prepared, counts)
        summary = build_summary(prepared, counts, time.perf_counter() - start, dry_run=False)
        if job_id:
            await finish_job(factory, job_id, summary)
        if args.approve_band:
            approved = await approve_band(factory, args.approve_band, args.reviewer)
            print(f"published {approved.published}, conflicts {len(approved.conflicts)}")
            for sha in approved.conflicts:
                print(f"conflict: {sha}")
        return summary
    finally:
        await engine.dispose()


async def _run(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    rows, errors, total = read_rows(args.decisions)
    files = read_files(args.files) if args.files else {}
    prepared, duplicate_sha = prepare(rows, files)
    counts = LoadCounts(total=total, skipped_duplicate_sha256=duplicate_sha, errors=errors)
    if args.dry_run:
        counts.new = len(prepared)
        summary = build_summary(prepared, counts, time.perf_counter() - start, dry_run=True)
    else:
        summary = await _load_to_db(args, prepared, counts, start)
    if args.report:
        write_report(summary, args.report)
    print(
        f"total {summary['total']}, new {summary['new']}, skipped {summary['skipped']}, "
        f"errors {summary['errors']}, bands {summary['bands']}"
    )
    return 1 if summary["errors"] else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.approve_band and (args.dry_run or not args.reviewer):
        parser.error("--approve-band needs --reviewer and cannot be combined with --dry-run")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
