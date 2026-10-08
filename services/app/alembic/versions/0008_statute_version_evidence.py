"""statute_article_version: evidence, confidence, warnings, footnotes (task 11b)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-08

Hand-written (docs/tasks/11-statute-versioning.md, 11b). A published version keeps what dated
it, so the review screen and the citation gate can show it without reading the extraction:
`evidence` (basis, snapshot dates, the amendment notes), `confidence` (the 11a band; text with a
CHECK like `decision_verification`, NULL for rows not written by the statute pipeline),
`warnings` and `footnotes`. The defaults make the migration safe on existing rows. Additive; the
downgrade drops the columns.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TABLE = "statute_article_version"
BANDS = ("high", "medium", "low")
CHECK = "ck_statute_article_version_confidence"


def upgrade() -> None:
    op.add_column(
        TABLE, sa.Column("evidence", pg.JSONB(), server_default=sa.text("'{}'"), nullable=False)
    )
    op.add_column(TABLE, sa.Column("confidence", sa.Text(), nullable=True))
    op.add_column(
        TABLE, sa.Column("warnings", pg.JSONB(), server_default=sa.text("'[]'"), nullable=False)
    )
    op.add_column(
        TABLE, sa.Column("footnotes", pg.JSONB(), server_default=sa.text("'[]'"), nullable=False)
    )
    op.create_check_constraint(
        CHECK, TABLE, "confidence IN (" + ", ".join(f"'{b}'" for b in BANDS) + ")"
    )


def downgrade() -> None:
    op.drop_constraint(CHECK, TABLE, type_="check")
    for column in ("footnotes", "warnings", "confidence", "evidence"):
        op.drop_column(TABLE, column)
