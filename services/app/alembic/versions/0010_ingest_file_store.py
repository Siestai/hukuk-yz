"""ingest_file: stored, typed and scanned files (task 12a)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-11

Hand-written (docs/tasks/12-file-management.md). Adds the enums `document_type` and
`scan_status` and the columns of a file managed by the app to `ingest_file`: storage key, original
name, document type / date / official reference / origin / note, uploader, upload time, the
previous version, the scan status and result, and the soft-delete time.

Existing rows are the archive loaders' (task 05): they have no storage key (12c fills it) and
count as scanned, so `scan_status` is NOT NULL with the server default 'done' (kept: the loaders
still insert without naming it). Uploads set 'queued' explicitly, so the default never marks an
unscanned upload as scanned.

Indexes: `sha256` is unique among rows that have a storage key, which makes the duplicate-upload
check race-safe (the loaders may hold one content twice, as separate rows without a key, so a
plain unique index would not fit); `supersedes_id` is unique, so a file has one next version and
the chain never branches; a small partial index serves the worker's claim and requeue queries.
The downgrade drops the columns, the indexes and the enums (uploaded files lose their metadata,
the stored blobs stay on disk).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

ENUMS = {
    "document_type": (
        "kanun",
        "cbk",
        "yonetmelik",
        "teblig",
        "genelge",
        "genel_yazi",
        "ic_emri",
        "karar",
        "kitap",
        "hesap_tablosu",
        "diger",
    ),
    "scan_status": ("queued", "running", "done", "needs_ocr", "unsupported", "failed"),
}
TABLE = "ingest_file"


def _enum(name: str) -> pg.ENUM:
    return pg.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    for name, labels in ENUMS.items():
        pg.ENUM(*labels, name=name).create(op.get_bind(), checkfirst=False)
    op.add_column(TABLE, sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("original_name", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("doc_type", _enum("document_type"), nullable=True))
    op.add_column(TABLE, sa.Column("doc_date", sa.Date(), nullable=True))
    op.add_column(TABLE, sa.Column("official_ref", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("origin_url", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("note", sa.Text(), nullable=True))
    op.add_column(TABLE, sa.Column("uploaded_by", sa.Uuid(), nullable=True))
    op.add_column(
        TABLE,
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(TABLE, sa.Column("supersedes_id", sa.Uuid(), nullable=True))
    op.add_column(
        TABLE,
        sa.Column(
            "scan_status",
            _enum("scan_status"),
            server_default=sa.text("'done'"),
            nullable=False,
        ),
    )
    op.add_column(TABLE, sa.Column("scan_result", pg.JSONB(), nullable=True))
    op.add_column(TABLE, sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_ingest_file_uploaded_by_app_user", TABLE, "app_user", ["uploaded_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_ingest_file_supersedes_id_ingest_file", TABLE, TABLE, ["supersedes_id"], ["id"]
    )
    op.create_index(
        "uq_ingest_file_sha256_stored",
        TABLE,
        ["sha256"],
        unique=True,
        postgresql_where=sa.text("storage_key IS NOT NULL"),
    )
    op.create_index(
        "uq_ingest_file_supersedes_id",
        TABLE,
        ["supersedes_id"],
        unique=True,
        postgresql_where=sa.text("supersedes_id IS NOT NULL"),
    )
    op.create_index(
        "ix_ingest_file_scan_pending",
        TABLE,
        ["scan_status"],
        postgresql_where=sa.text("scan_status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("ix_ingest_file_scan_pending", table_name=TABLE)
    op.drop_index("uq_ingest_file_supersedes_id", table_name=TABLE)
    op.drop_index("uq_ingest_file_sha256_stored", table_name=TABLE)
    op.drop_constraint("fk_ingest_file_supersedes_id_ingest_file", TABLE, type_="foreignkey")
    op.drop_constraint("fk_ingest_file_uploaded_by_app_user", TABLE, type_="foreignkey")
    for column in (
        "archived_at",
        "scan_result",
        "scan_status",
        "supersedes_id",
        "uploaded_at",
        "uploaded_by",
        "note",
        "origin_url",
        "official_ref",
        "doc_date",
        "doc_type",
        "original_name",
        "storage_key",
    ):
        op.drop_column(TABLE, column)
    for name in ENUMS:
        op.execute(f"DROP TYPE {name}")
