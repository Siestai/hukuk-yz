"""Journal scan runs (docs/tasks/20-journal-scan.md).

One row per run of the weekly scan of Çalışma ve Toplum; its `ingest_job` (kind `crawl`) holds
the downloaded files. Counters live here, not in `ingest_job.stats`.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_scan",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(), sa.ForeignKey("ingest_job.id"), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "new_issues",
            ARRAY(sa.Integer()),
            nullable=False,
            server_default=sa.text("'{}'::integer[]"),
        ),
        sa.Column("discovered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("downloaded", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("duplicates", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("queued", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("errors", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("report", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.CheckConstraint("trigger IN ('schedule', 'manual')", name="ck_journal_scan_trigger"),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'completed_with_errors', 'failed')",
            name="ck_journal_scan_status",
        ),
    )
    op.create_index("ix_journal_scan_job_id", "journal_scan", ["job_id"])
    op.create_index("ix_journal_scan_started_at", "journal_scan", ["started_at"])


def downgrade() -> None:
    op.drop_table("journal_scan")
