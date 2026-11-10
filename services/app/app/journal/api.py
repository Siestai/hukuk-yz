"""The journal scan API (task 20): the runs of the weekly scan and the numbers of the last one.
Reviewers and admins only."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.auth import Db
from app.errors import ApiError
from app.models.journal import JournalScan
from app.review_common import Limit, Offset, page, reviewer_check
from hukuk_models import ErrorCode
from hukuk_models.journal import (
    JournalReport,
    JournalScanDetail,
    JournalScanItem,
    JournalScanListResponse,
    JournalScanSummary,
)

router = APIRouter(
    prefix="/journal-scans", tags=["journal"], dependencies=[Depends(reviewer_check)]
)


def _item(scan: JournalScan) -> JournalScanItem:
    return JournalScanItem.model_validate(scan, from_attributes=True)


@router.get("")
async def list_scans(db: Db, limit: Limit = 50, offset: Offset = 0) -> JournalScanListResponse:
    stmt = select(JournalScan).order_by(JournalScan.started_at.desc(), JournalScan.id)
    total, rows = await page(db, stmt, limit, offset)
    return JournalScanListResponse(total=total, items=[_item(row.JournalScan) for row in rows])


@router.get("/latest/summary")
async def latest_summary(db: Db) -> JournalScanSummary:
    """Numbers of the latest finished scan, for the message to the group. 404 before the first."""
    scan = (
        await db.execute(
            select(JournalScan)
            .where(JournalScan.status != "running")
            .order_by(JournalScan.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if scan is None:
        raise ApiError(404, ErrorCode.not_found)
    report = JournalReport.model_validate(scan.report)
    return JournalScanSummary.model_validate(
        {
            "status": scan.status,
            "finished_at": scan.finished_at,
            "issues": scan.new_issues,
            "queued": scan.queued,
            "duplicates": scan.duplicates,
            "duplicate_candidates": sum(i.duplicate_candidates for i in report.issues),
            "errors": scan.errors,
        }
    )


@router.get("/{scan_id}")
async def get_scan(scan_id: uuid.UUID, db: Db) -> JournalScanDetail:
    scan = await db.get(JournalScan, scan_id)
    if scan is None:
        raise ApiError(404, ErrorCode.not_found)
    return JournalScanDetail(
        **_item(scan).model_dump(), report=JournalReport.model_validate(scan.report)
    )
