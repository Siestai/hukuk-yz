"""ingest_file: review status, suggestions and matches; file_deletion (task 13a)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-12

Hand-written (docs/tasks/13-upload-detect-approve.md). An uploaded file is `pending` until a
human approves it; the detector's suggestions and the matches with earlier versions / similar
files live in two JSONB columns, `approved_by` / `approved_at` say who confirmed, `title` is the
document's title. The rows that exist now (the archive import of task 12c and earlier uploads) are
`approved`: their type came from the folder tree, `approved_by` NULL means the system import. The
column keeps the server default 'approved' (the loaders insert without naming it); an upload
says 'pending' explicitly.

`file_deletion` keeps the trace of a deleted upload (md. 25): the whole row as JSON. `file_id`
has no foreign key, the row it names is gone. The downgrade drops the table, the columns and the
enum; the suggestions and matches are lost, the approval trail with them.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

REVIEW_STATUS = ("pending", "approved")
TABLE = "ingest_file"
DOCUMENT_TYPE = "document_type"


def _review_status() -> pg.ENUM:
    return pg.ENUM(*REVIEW_STATUS, name="review_status", create_type=False)


def upgrade() -> None:
    pg.ENUM(*REVIEW_STATUS, name="review_status").create(op.get_bind(), checkfirst=False)
    op.add_column(
        TABLE,
        sa.Column(
            "review_status", _review_status(), server_default=sa.text("'approved'"), nullable=False
        ),
    )
    # The default only backfills the rows there are; later inserts must name the status.
    op.alter_column(TABLE, "review_status", server_default=None)
    op.add_column(TABLE, sa.Column("approved_by", sa.Uuid(), nullable=True))
    op.add_column(TABLE, sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABLE, sa.Column("title", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("suggestions", pg.JSONB(), nullable=True))
    op.add_column(TABLE, sa.Column("matches", pg.JSONB(), nullable=True))
    op.create_foreign_key(
        "fk_ingest_file_approved_by_app_user", TABLE, "app_user", ["approved_by"], ["id"]
    )
    op.create_index(
        "ix_ingest_file_review_pending",
        TABLE,
        ["review_status"],
        postgresql_where=sa.text("review_status = 'pending'"),
    )
    op.create_table(
        "file_deletion",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=True),
        sa.Column("doc_type", pg.ENUM(name=DOCUMENT_TYPE, create_type=False), nullable=True),
        sa.Column("review_status", _review_status(), nullable=False),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("snapshot", pg.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["app_user.id"], name="fk_file_deletion_deleted_by_app_user"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_file_deletion"),
    )


def downgrade() -> None:
    op.drop_table("file_deletion")
    op.drop_index("ix_ingest_file_review_pending", table_name=TABLE)
    op.drop_constraint("fk_ingest_file_approved_by_app_user", TABLE, type_="foreignkey")
    for column in (
        "matches",
        "suggestions",
        "title",
        "approved_at",
        "approved_by",
        "review_status",
    ):
        op.drop_column(TABLE, column)
    op.execute("DROP TYPE review_status")
