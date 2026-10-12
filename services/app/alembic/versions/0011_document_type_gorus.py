"""document_type: the label 'gorus' (task 12d)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-12

Hand-written (docs/tasks/12-file-management.md, 12d). SGK and ministry opinions (the Drive folder
`Mevzuat/Görüş`) are a source type of their own (md. 28), not `diger`. Postgres cannot drop an
enum label, so the downgrade turns the `gorus` rows into `diger` (the only data the label
carries) and swaps in the old type. Schema only: the rows of the archive get their type from
`python -m app.files.backfill_doc_type`, not from this migration.
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

OLD_LABELS = (
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
)


def upgrade() -> None:
    op.execute("ALTER TYPE document_type ADD VALUE 'gorus'")


def downgrade() -> None:
    op.execute("UPDATE ingest_file SET doc_type = 'diger' WHERE doc_type = 'gorus'")
    op.execute("ALTER TYPE document_type RENAME TO document_type_old")
    labels = ", ".join(f"'{label}'" for label in OLD_LABELS)
    op.execute(f"CREATE TYPE document_type AS ENUM ({labels})")
    op.execute(
        "ALTER TABLE ingest_file ALTER COLUMN doc_type TYPE document_type "
        "USING doc_type::text::document_type"
    )
    op.execute("DROP TYPE document_type_old")
