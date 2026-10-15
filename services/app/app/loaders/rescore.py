"""Recompute `extraction.confidence` of the loaded decisions with the current rule table.

    python -m app.loaders.rescore [--dry-run]

Run it after `app.loaders.confidence` changes (task 10l). It reads each decision extraction's
stored `fields` and `warnings` and writes only the `confidence` column, and only where the
result differs, so a second run changes nothing. `review` rows, `fields` and the decisions
already published are not touched: an approved record stays approved, with its band updated.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import make_engine, make_session_factory
from app.kb import PARSER_NAME
from app.loaders.confidence import confidence
from app.models.common import Extraction, Source, SourceCategory
from app.settings import get_settings


async def rescore(factory: async_sessionmaker[AsyncSession], *, dry_run: bool = False) -> int:
    """Number of extractions whose confidence changed (written unless `dry_run`)."""
    async with factory() as session:
        rows = (
            await session.execute(
                select(Extraction.id, Extraction.fields, Extraction.warnings, Extraction.confidence)
                .join(Source, Source.id == Extraction.source_id)
                .where(
                    Extraction.parser_name == PARSER_NAME,
                    Source.category == SourceCategory.decision,
                )
            )
        ).all()
        changed = 0
        for id_, fields, warnings, stored in rows:
            fresh = confidence(fields, warnings)
            if fresh != stored:
                changed += 1
                if not dry_run:
                    await session.execute(
                        update(Extraction).where(Extraction.id == id_).values(confidence=fresh)
                    )
        await session.commit()
    return changed


async def _main(dry_run: bool) -> int:
    engine = make_engine(get_settings().database_url)
    try:
        changed = await rescore(make_session_factory(engine), dry_run=dry_run)
    finally:
        await engine.dispose()
    print(f"{changed} extractions {'would change' if dry_run else 'rescored'}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="count the changes, write nothing")
    args = parser.parse_args(argv)
    return asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
