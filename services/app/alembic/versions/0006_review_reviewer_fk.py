"""review_reviewer_fk and review queue columns (docs/tasks/09-review-api.md §6, §4)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-03

Hand-written. Two changes for the review API:

* `review.reviewer_id -> app_user.id` as NOT VALID: new and updated rows must name a real user,
  while the reviews the task 05 CLI wrote with a free UUID are not checked (and VALIDATE
  CONSTRAINT would fail on them). Alembic cannot express NOT VALID, hence `op.execute`.
* STORED generated columns on `extraction` for what the queue filters and shows. They are cut
  out of `fields` when the row is written, so the list never detoasts the ~25 KB decision text
  of every row (370-580 ms on 6.3k rows with the court / journal_issue / q filters). Only
  `duplicate_key` gets an index (the detail endpoint looks a group up by it); the queue itself
  scans the few thousand narrow rows in memory.

The downgrade drops the constraint, the index and the columns.
"""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# column -> (type, expression over `fields`)
GENERATED: dict[str, tuple[sa.types.TypeEngine[Any], str]] = {
    "court": (sa.Text(), "fields ->> 'court'"),
    "chamber": (sa.Text(), "fields ->> 'chamber'"),
    "esas_no": (sa.Text(), "fields ->> 'esas_no'"),
    "karar_no": (sa.Text(), "fields ->> 'karar_no'"),
    "decision_date": (sa.Text(), "fields ->> 'decision_date'"),
    "journal_issue": (sa.Integer(), "(fields ->> 'journal_issue')::integer"),
    "duplicate_group": (pg.JSONB(), "fields -> 'duplicate_group'"),
    "duplicate_key": (sa.Text(), "fields #>> '{duplicate_group,key}'"),
}


def upgrade() -> None:
    op.execute(
        "ALTER TABLE review ADD CONSTRAINT fk_review_reviewer_id_app_user "
        "FOREIGN KEY (reviewer_id) REFERENCES app_user (id) NOT VALID"
    )
    for name, (type_, expression) in GENERATED.items():
        op.add_column("extraction", sa.Column(name, type_, sa.Computed(expression, persisted=True)))
    op.create_index(
        "ix_extraction_duplicate_key",
        "extraction",
        ["duplicate_key"],
        postgresql_where=sa.text("duplicate_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_extraction_duplicate_key", "extraction")
    for name in GENERATED:
        op.drop_column("extraction", name)
    op.drop_constraint("fk_review_reviewer_id_app_user", "review", type_="foreignkey")
