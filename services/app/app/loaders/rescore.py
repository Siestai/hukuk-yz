"""Recompute `extraction.confidence` of the loaded decisions with the current rule table.

    python -m app.loaders.rescore [--dry-run]

Run it after `app.loaders.confidence` changes (task 10l). It reads each decision extraction's
stored `fields` and `warnings` and writes only the `confidence` column, and only where the
result differs, so a second run changes nothing. `review` rows, `fields` and the decisions
already published are not touched: an approved record stays approved, with its band updated.
It works in keyset batches of 500 and commits per batch; the rewrite is idempotent, so a rerun
after a mid-run failure is safe. `--dry-run` never writes or commits. It prints the band
transitions (`low->high: 28`) so the operator sees that nothing else moved.
"""

import argparse
import asyncio
import sys
import uuid
from collections import Counter
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import make_engine, make_session_factory
from app.kb import PARSER_NAME
from app.loaders.confidence import confidence
from app.models.common import Extraction, Source, SourceCategory
from app.settings import get_settings

BATCH = 500


async def rescore(
    factory: async_sessionmaker[AsyncSession], *, dry_run: bool = False
) -> Counter[str]:
    """Changed extractions by band transition (`"low->high"`; written unless `dry_run`)."""
    transitions: Counter[str] = Counter()
    last: uuid.UUID | None = None
    while True:
        async with factory() as session:
            query = (
                select(Extraction.id, Extraction.fields, Extraction.warnings, Extraction.confidence)
                .join(Source, Source.id == Extraction.source_id)
                .where(
                    Extraction.parser_name == PARSER_NAME,
                    Source.category == SourceCategory.decision,
                )
                .order_by(Extraction.id)
                .limit(BATCH)
            )
            if last is not None:
                query = query.where(Extraction.id > last)
            rows = (await session.execute(query)).all()
            if not rows:
                return transitions
            last = rows[-1][0]
            for id_, fields, warnings, stored in rows:
                fresh = confidence(fields, warnings)
                if fresh == stored:
                    continue
                transitions[f"{(stored or {}).get('band')}->{fresh['band']}"] += 1
                if not dry_run:
                    await session.execute(
                        update(Extraction).where(Extraction.id == id_).values(confidence=fresh)
                    )
            if not dry_run:
                await session.commit()


async def _main(dry_run: bool) -> int:
    engine = make_engine(get_settings().database_url)
    try:
        transitions = await rescore(make_session_factory(engine), dry_run=dry_run)
    finally:
        await engine.dispose()
    print(f"{sum(transitions.values())} extractions {'would change' if dry_run else 'rescored'}")
    for transition, count in sorted(transitions.items()):
        print(f"  {transition}: {count}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="count the changes, write nothing")
    args = parser.parse_args(argv)
    return asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
