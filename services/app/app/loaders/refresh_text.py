"""Refresh the text of approved decisions from a newer parser run (task 04b).

    python -m app.loaders.refresh_text [--dry-run]

After a parser fix, `app.loaders.decisions` adds a new extraction per file, but the `decision`
row an approval published is never rewritten. This command copies the text fields of the newest
extraction into the approved decisions whose live row was published from an older parser
version: `full_text`, `text_completeness`, and `outcome` only where the live row has none. A key
in the source's edits (`source_edits`, those of all its reviews) is never overwritten (a human
wrote it), and a new extraction with no text never blanks a live text. Nothing else moves:
approval, the reviewer's edits, `review_id`, `recorded_by`, the verification columns and every
other field are copied as they are.

The live row is closed with `superseded_at` and a copy with the refreshed fields takes its
place, in one transaction per decision. The copy's `extraction_id` is the newest extraction (the
source of its text); its `review_id` stays that of the approval, which belongs to the older
extraction. `decision_verification` rows stay on the closed row as its history; the copy starts
with none (do not run the verification loader at the same time: a result written for the closed
row would not reach the live one). Rejected and pending sources are not touched. A second run
changes nothing: the live rows already point at the newest extraction, except that the
`skipped_*` rows (same text, or covered by edits) keep their old `extraction_id` and are counted
again; `refreshed` is 0. A live row with no `extraction_id` counts as older than any extraction.
A source that fails (`IntegrityError`, a bad completeness value) is rolled back alone, counted as
`failed` and reported on stderr; the others go on and the exit code is 1.

`--dry-run` writes nothing. Both modes print `refreshed`, `skipped_same` (the new text equals
the live one), `skipped_edits` (every change is covered by an edit), `failed` and the completeness
transitions of the refreshed rows (`summary_only->full: 50`).
"""

import argparse
import asyncio
import re
import sys
import uuid
from collections import Counter
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chunk_index import sync_decision
from app.db import make_engine, make_session_factory
from app.kb import STATUS_GROUPS, newest_extractions, source_edits
from app.models.common import Extraction, Source, TextCompleteness
from app.models.decision import Decision
from app.settings import get_settings

# Not copied to the new row: its own key, the trigger's column, and the two the new row sets.
_NOT_COPIED = frozenset({"id", "tsv", "recorded_at", "superseded_at", "extraction_id"})


def _version_key(version: str) -> tuple[int, ...]:
    """Parser versions are counters ("5", "6"); a version without digits is the oldest."""
    return tuple(int(n) for n in re.findall(r"\d+", version))


def _wanted(live: Decision, fields: dict[str, Any]) -> dict[str, Any]:
    """The text fields the newest extraction would change on the live row, edits aside."""
    text = fields["full_text"] or None
    if text is None:  # a parser that found no text must not blank the one we have
        return {}
    wanted: dict[str, Any] = {
        "full_text": text,
        "text_completeness": TextCompleteness(fields["text_completeness"]),
    }
    if not live.outcome and fields["outcome"]:
        wanted["outcome"] = fields["outcome"]
    return {k: v for k, v in wanted.items() if getattr(live, k) != v}


async def _refresh_one(session: AsyncSession, source_id: uuid.UUID, dry_run: bool) -> Counter[str]:
    """Refresh the live decision of one source under the source's and the decision's row locks;
    the caller commits. Empty when the source has moved on since the candidate query."""
    counts: Counter[str] = Counter()
    source = (
        await session.execute(
            select(Source)
            .where(Source.id == source_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    live = (
        await session.execute(
            select(Decision)
            .where(Decision.source_id == source_id, Decision.superseded_at.is_(None))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if source.status not in STATUS_GROUPS["approved"] or live is None:
        return counts
    newest_id = (await session.execute(select(newest_extractions(source_id).c.id))).scalar_one()
    newest = await session.get(Extraction, newest_id)
    # A live row without an extraction (published by hand) counts as older than any parser run.
    published = await session.get(Extraction, live.extraction_id) if live.extraction_id else None
    assert newest is not None
    if _version_key(newest.parser_version) <= _version_key(
        published.parser_version if published else ""
    ):
        return counts

    wanted = _wanted(live, newest.fields)
    edited = await source_edits(session, source_id)
    changes = {k: v for k, v in wanted.items() if k not in edited}
    if not changes:
        counts["skipped_edits" if wanted else "skipped_same"] += 1
        return counts

    counts["refreshed"] += 1
    before, after = live.text_completeness, changes.get("text_completeness", live.text_completeness)
    if before is not after:
        counts[f"{before.value}->{after.value}"] += 1
    if dry_run:
        return counts
    columns = {
        attr.key: getattr(live, attr.key)
        for attr in inspect(Decision).column_attrs
        if attr.key not in _NOT_COPIED
    }
    await session.execute(
        update(Decision).where(Decision.id == live.id).values(superseded_at=func.now())
    )
    session.add(Decision(**{**columns, **changes, "extraction_id": newest.id}))
    await session.flush()
    await sync_decision(session, source_id)
    return counts


async def refresh_text(
    factory: async_sessionmaker[AsyncSession], *, dry_run: bool = False
) -> Counter[str]:
    """Counts by `refreshed`, `skipped_same`, `skipped_edits`, `failed`, completeness transition."""
    newest = newest_extractions()
    async with factory() as session:
        source_ids = (
            (
                await session.execute(
                    select(newest.c.source_id)
                    .join(Decision, Decision.source_id == newest.c.source_id)
                    .where(
                        newest.c.status.in_(STATUS_GROUPS["approved"]),
                        Decision.superseded_at.is_(None),
                        Decision.extraction_id.is_distinct_from(newest.c.id),
                    )
                    .order_by(newest.c.source_id)
                )
            )
            .scalars()
            .all()
        )
    total: Counter[str] = Counter()
    for source_id in source_ids:
        try:
            async with factory() as session:
                total += await _refresh_one(session, source_id, dry_run)
                if not dry_run:
                    await session.commit()
        except (IntegrityError, ValueError) as error:  # the session rolled back on leaving
            total["failed"] += 1
            print(f"failed {source_id}: {type(error).__name__}: {error}", file=sys.stderr)
    return total


async def _main(dry_run: bool) -> int:
    engine = make_engine(get_settings().database_url)
    try:
        counts = await refresh_text(make_session_factory(engine), dry_run=dry_run)
    finally:
        await engine.dispose()
    print(f"{counts['refreshed']} decisions {'would be refreshed' if dry_run else 'refreshed'}")
    for key in ("refreshed", "skipped_same", "skipped_edits", "failed"):
        print(f"  {key}: {counts[key]}")
    for key, count in sorted(counts.items()):
        if "->" in key:
            print(f"  {key}: {count}")
    return 1 if counts["failed"] else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="count the changes, write nothing")
    args = parser.parse_args(argv)
    return asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
