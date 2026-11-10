"""The weekly scan of the journal Çalışma ve Toplum (task 20)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, UuidPkMixin

SCAN_TRIGGERS = ("schedule", "manual")
SCAN_STATUSES = ("running", "completed", "completed_with_errors", "failed")


class JournalScan(UuidPkMixin, Base):
    """One run of `python -m app.journal.scan`. Its `ingest_job` (kind `crawl`) carries the
    files; the counters live here only, `ingest_job.stats` stays empty."""

    __tablename__ = "journal_scan"
    __table_args__ = (
        CheckConstraint("trigger IN ('schedule', 'manual')", name="trigger"),
        CheckConstraint(
            "status IN ('running', 'completed', 'completed_with_errors', 'failed')", name="status"
        ),
        Index("ix_journal_scan_started_at", "started_at"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingest_job.id"), index=True)
    trigger: Mapped[str]
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
    status: Mapped[str]
    new_issues: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), server_default=text("'{}'::integer[]")
    )
    discovered: Mapped[int] = mapped_column(server_default=text("0"))
    downloaded: Mapped[int] = mapped_column(server_default=text("0"))
    duplicates: Mapped[int] = mapped_column(server_default=text("0"))
    queued: Mapped[int] = mapped_column(server_default=text("0"))
    errors: Mapped[int] = mapped_column(server_default=text("0"))
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
