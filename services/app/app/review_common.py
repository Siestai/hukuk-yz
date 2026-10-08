"""What the decision review API (`app.review`) and the statute review API (`app.review_statutes`)
share: the role dependency, the page query and the bulk-approval run."""

import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated, Any

from fastapi import Depends, Query
from sqlalchemy import Select, func, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.errors import ApiError
from app.kb import BatchResult
from app.models.user import AppUser
from hukuk_models import Band, BulkApproveResponse, BulkFailure, ErrorCode

reviewer_check = require_role("reviewer")
Reviewer = Annotated[AppUser, Depends(reviewer_check)]

Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


async def count(db: AsyncSession, stmt: Select[Any]) -> int:
    return (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()


async def page(
    db: AsyncSession, stmt: Select[Any], limit: int, offset: int
) -> tuple[int, Sequence[Row[Any]]]:
    """(total, rows of the page) in one query; a page past the last needs a second one for the
    total."""
    rows = (
        await db.execute(
            stmt.add_columns(func.count().over().label("total")).limit(limit).offset(offset)
        )
    ).all()
    if rows:
        total = rows[0].total
    elif offset:  # past the last page
        total = await count(db, stmt)
    else:
        total = 0
    return total, rows


async def bulk_approve[Cursor](
    db: AsyncSession,
    *,
    band: Band,
    cursor: Cursor | None,
    expected_count: int,
    limit: int,
    pending: Callable[[Cursor | None], Select[Any]],
    cursor_of: Callable[[Row[Any]], Cursor],
    publish: Callable[[list[uuid.UUID]], Awaitable[BatchResult]],
) -> BulkApproveResponse:
    """One call of a bulk run over the high band. `pending(after)` selects the records (column
    `id`, in cursor order) after the cursor; their number must be `expected_count`, else
    `bulk_count_changed`. The first `limit` are published by `publish`, which does not commit;
    this does."""
    if band != "high":
        raise ApiError(422, ErrorCode.bulk_band_not_allowed)
    total = await count(db, pending(cursor))
    if total != expected_count:
        raise ApiError(
            409, ErrorCode.bulk_count_changed, {"total": total, "expected": expected_count}
        )
    rows = (await db.execute(pending(cursor).limit(limit))).all()
    result = await publish([row.id for row in rows])
    await db.commit()
    last = cursor_of(rows[-1]) if rows else None
    remaining = await count(db, pending(last)) if last is not None else 0
    return BulkApproveResponse(
        published=result.published,
        conflicts=result.conflicts,
        failed=[BulkFailure(extraction_id=i, reason=reason) for i, reason in result.failed],
        remaining=remaining,
        next_cursor=str(last) if remaining else None,
    )
