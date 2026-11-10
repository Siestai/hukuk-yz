"""The journal scan API (task 20): the runs of the weekly scan and the numbers of the last one."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ScanTrigger = Literal["schedule", "manual"]
ScanStatus = Literal["running", "completed", "completed_with_errors", "failed"]


class JournalError(BaseModel):
    """One decision of the scan that was not queued: the address and why (`pdf_link_missing`,
    `not_a_pdf`, `too_large`, `http_<status>`, `timeout`, `connect_error`, `db_error`)."""

    url: str
    reason: str


class JournalIssueReport(BaseModel):
    """What the scan did with one journal issue. `site_count` is the number of decision pages the
    site lists, `duplicates` the ones it already had (same post or same file),
    `duplicate_candidates` the queued ones that share court, chamber and E/K with a record of the
    archive."""

    issue_no: int
    site_count: int
    pdf_links: int
    downloaded: int
    duplicates: int
    queued: int
    duplicate_candidates: int
    errors: list[JournalError]


class JournalReport(BaseModel):
    """`failure` is set when the scan could not go on (the site's API did not answer); the
    issues done up to then are in `issues`."""

    issues: list[JournalIssueReport] = []
    failure: str | None = None


class JournalScanItem(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    trigger: ScanTrigger
    started_at: datetime
    finished_at: datetime | None
    status: ScanStatus
    new_issues: list[int]
    discovered: int
    downloaded: int
    duplicates: int
    queued: int
    errors: int


class JournalScanDetail(JournalScanItem):
    report: JournalReport


class JournalScanListResponse(BaseModel):
    total: int
    items: list[JournalScanItem]


class JournalScanSummary(BaseModel):
    """Numbers only (the message to the group is written outside the app)."""

    status: ScanStatus
    finished_at: datetime | None
    issues: list[int]
    queued: int
    duplicates: int
    duplicate_candidates: int
    errors: int
