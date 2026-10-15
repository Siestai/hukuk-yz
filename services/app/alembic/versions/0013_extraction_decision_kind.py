"""extraction.decision_kind: generated column for the review queue (task 10l)

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-15

Hand-written (docs/tasks/10l-aym-application-no.md). The queue shows an AYM individual
application by its Başvuru No instead of E/K, so it needs `decision_kind`; like the other queue
columns (0006) it is a STORED generated column cut out of `fields`, so the list never detoasts
the decision text. Adding it rewrites `extraction` once (a few thousand rows). The downgrade
drops the column.
"""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "extraction",
        sa.Column(
            "decision_kind", sa.Text(), sa.Computed("fields ->> 'decision_kind'", persisted=True)
        ),
    )


def downgrade() -> None:
    op.drop_column("extraction", "decision_kind")
