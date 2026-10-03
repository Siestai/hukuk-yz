"""login_attempt (docs/tasks/10a-dashboard-api-prep.md §2)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-03

Hand-written. Adds `login_attempt`, the log the login rate limit counts failed attempts in. A
table rather than an in-memory counter because several `app` replicas may run. Indexed by
(email, attempted_at) and (ip, attempted_at), the two lookups of the limit, and by
(attempted_at) for the prune of old rows. The downgrade drops the table.
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_attempt",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_login_attempt"),
    )
    op.create_index(
        "ix_login_attempt_email_attempted_at", "login_attempt", ["email", "attempted_at"]
    )
    op.create_index("ix_login_attempt_ip_attempted_at", "login_attempt", ["ip", "attempted_at"])
    op.create_index("ix_login_attempt_attempted_at", "login_attempt", ["attempted_at"])


def downgrade() -> None:
    op.drop_table("login_attempt")
