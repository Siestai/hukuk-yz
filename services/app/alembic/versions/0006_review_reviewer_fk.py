"""review_reviewer_fk (docs/tasks/09-review-api.md §6)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-03

Hand-written. Adds `review.reviewer_id -> app_user.id` as NOT VALID: new and updated rows must
name a real user, while the reviews the task 05 CLI wrote with a free UUID are not checked (and
VALIDATE CONSTRAINT would fail on them). Alembic cannot express NOT VALID, hence `op.execute`.
No index: nothing queries reviews by reviewer, and the list query reads `extraction`.
The downgrade drops the constraint.
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE review ADD CONSTRAINT fk_review_reviewer_id_app_user "
        "FOREIGN KEY (reviewer_id) REFERENCES app_user (id) NOT VALID"
    )


def downgrade() -> None:
    op.drop_constraint("fk_review_reviewer_id_app_user", "review", type_="foreignkey")
