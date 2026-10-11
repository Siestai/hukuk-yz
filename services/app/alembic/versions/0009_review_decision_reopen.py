"""review_decision: the label 'reopen' (task 10h)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-10

Hand-written (docs/tasks/10h-reopen-review.md). A reviewer can take an approved or rejected
decision back to review; that is written as a `review` row with decision `reopen`. Postgres
cannot drop an enum label, so the downgrade deletes the `reopen` rows (the only data the
label carries) and swaps in the old type.
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

OLD_LABELS = ("approve", "edit", "reject")


def upgrade() -> None:
    op.execute("ALTER TYPE review_decision ADD VALUE 'reopen'")


def downgrade() -> None:
    op.execute("DELETE FROM review WHERE decision = 'reopen'")
    op.execute("ALTER TYPE review_decision RENAME TO review_decision_old")
    labels = ", ".join(f"'{label}'" for label in OLD_LABELS)
    op.execute(f"CREATE TYPE review_decision AS ENUM ({labels})")
    op.execute(
        "ALTER TABLE review ALTER COLUMN decision TYPE review_decision "
        "USING decision::text::review_decision"
    )
    op.execute("DROP TYPE review_decision_old")
