"""Build the search index (task 14): chunk the decisions and statute articles, embed the chunks.

    python -m app.loaders.chunks [--category decision|statute] [--dry-run] [--limit N]

Per record (a decision source, a statute article) the chunks are rebuilt as `app.chunk_index`
says; then the chunks without a vector of the current model are embedded (OpenAI, `OPENAI_API_KEY`
required unless `--dry-run`). A second run finds nothing to write and nothing to embed. `--dry-run`
writes nothing and calls nothing: it counts the chunks and estimates the tokens and the cost.
`--limit N` stops after N records (and embeds only their chunks). The review paths refresh a
record's chunks themselves; this command is for the first build and for a change of model or of
the chunking rules.

Exit code 0 when done, 1 when some record or batch failed, 2 when the key is missing.
"""

import argparse
import asyncio
import sys
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chunk_index import (
    Row,
    decision_rows,
    embed_pending,
    review_status,
    statute_article_rows,
    sync_decision,
    sync_statute_article,
)
from app.db import make_engine, make_session_factory
from app.embeddings import Embedder, estimate_cost, make_embedder
from app.models.common import STATUTE_PARSER_NAME, Extraction, Source, SourceCategory
from app.settings import get_settings
from hukuk_ingest.index.chunking import embedding_input, estimate_tokens

BATCH = 50
Category = Literal["decision", "statute"]
# A decision source, or a statute article as (statute number, article no).
Unit = uuid.UUID | tuple[str, str]


@dataclass
class IndexReport:
    # chunks by (category, review status, kind), after the run (dry run: as they would be)
    chunks: Counter[tuple[str, str, str]] = field(default_factory=Counter)
    records: int = 0
    empty: int = 0  # records without a chunk: rejected, not indexed, no text
    unchanged: int = 0  # records whose chunks were already as wanted
    estimated_tokens: int = 0
    embedded_chunks: int = 0
    embedded_tokens: int = 0
    embed_failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.errors or self.embed_failed)

    def lines(self, dry_run: bool) -> list[str]:
        out = ["chunks (category / review status / kind):"]
        out += [
            f"  {category:9} {status:9} {kind:18} {count:>8}"
            for (category, status, kind), count in sorted(self.chunks.items())
        ]
        out.append(f"  total {sum(self.chunks.values()):>38}")
        out.append(
            f"records: {self.records} (without chunks: {self.empty}, unchanged: {self.unchanged})"
        )
        if dry_run:
            out.append(
                f"dry run, nothing written: ~{self.estimated_tokens:,} tokens to embed, "
                f"~${estimate_cost(self.estimated_tokens):.2f}"
            )
        else:
            out.append(
                f"embedded: {self.embedded_chunks} chunks, {self.embedded_tokens:,} tokens, "
                f"~${estimate_cost(self.embedded_tokens):.2f}; failed batches' chunks: "
                f"{self.embed_failed}"
            )
        out += [f"error: {e}" for e in self.errors]
        return out


def _tally(report: IndexReport, rows: Sequence[Row]) -> None:
    report.records += 1
    if not rows:
        report.empty += 1
    for row in rows:
        key = (row.category.value, review_status(row.parent_kind), row.kind.value)
        report.chunks[key] += 1
        report.estimated_tokens += estimate_tokens(embedding_input(row.header, row.text))


async def _statute_articles(session: AsyncSession) -> list[tuple[str, str]]:
    number = Extraction.fields["statute_number"].as_string()
    article_no = Extraction.fields["article_no"].as_string()
    rows = await session.execute(
        select(number, article_no)
        .where(Extraction.parser_name == STATUTE_PARSER_NAME)
        .distinct()
        .order_by(number, article_no)
    )
    return [(str(n), str(a)) for n, a in rows.all()]


async def _record(session: AsyncSession, unit: Unit, dry_run: bool) -> tuple[list[Row], bool]:
    """The chunks of a decision source or a statute article (number, article no), and whether
    the sync had to write them."""
    if isinstance(unit, uuid.UUID):
        if dry_run:
            return await decision_rows(session, unit), True
        result = await sync_decision(session, unit)
    else:
        if dry_run:
            return await statute_article_rows(session, *unit), True
        result = await sync_statute_article(session, *unit)
    return result.rows, result.written


async def build(
    factory: async_sessionmaker[AsyncSession],
    embedder: Embedder | None,
    *,
    categories: Sequence[Category] = ("decision", "statute"),
    dry_run: bool = False,
    limit: int | None = None,
) -> IndexReport:
    """Rebuild the chunks of every record of `categories` and embed what lacks a vector
    (`embedder` None: not at all). Each batch of records commits on its own."""
    report = IndexReport()
    async with factory() as session:
        decisions: list[uuid.UUID] = []
        if "decision" in categories:
            decisions = list(
                (
                    await session.execute(
                        select(Source.id)
                        .where(Source.category == SourceCategory.decision)
                        .order_by(Source.id)
                    )
                )
                .scalars()
                .all()
            )
        articles = await _statute_articles(session) if "statute" in categories else []
    units: list[Unit] = [*decisions, *articles]
    if limit is not None:
        units = units[:limit]

    touched: set[uuid.UUID] = set()
    for start in range(0, len(units), BATCH):
        async with factory() as session:
            for unit in units[start : start + BATCH]:
                try:
                    async with session.begin_nested():
                        rows, written = await _record(session, unit, dry_run)
                except Exception as error:  # one record must not stop the build
                    report.errors.append(f"{unit}: {type(error).__name__}: {error}")
                    continue
                touched.update(row.source_id for row in rows)
                _tally(report, rows)
                if not (written or dry_run):
                    report.unchanged += 1
            await session.commit()

    if embedder is not None and not dry_run:
        async with factory() as session:
            embedded = await embed_pending(
                session,
                embedder,
                source_ids=list(touched) if limit is not None else None,
            )
        report.embedded_chunks = embedded.chunks
        report.embedded_tokens = embedded.tokens
        report.embed_failed = embedded.failed
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--category", choices=("decision", "statute"), help="default: both")
    parser.add_argument("--dry-run", action="store_true", help="count and estimate, write nothing")
    parser.add_argument("--limit", type=int, help="stop after this many records")
    return parser


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    embedder = None if args.dry_run else make_embedder(settings)
    if embedder is None and not args.dry_run:
        print("OPENAI_API_KEY is not set: nothing to embed with (use --dry-run to count)")
        return 2
    categories: tuple[Category, ...] = (
        (args.category,) if args.category else ("decision", "statute")
    )
    engine = make_engine(settings.database_url)
    try:
        report = await build(
            make_session_factory(engine),
            embedder,
            categories=categories,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    finally:
        await engine.dispose()
    print("\n".join(report.lines(args.dry_run)))
    return 1 if report.failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(_run(_parser().parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
