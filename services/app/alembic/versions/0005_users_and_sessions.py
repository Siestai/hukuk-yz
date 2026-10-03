"""users_and_sessions (docs/data-model.md §3, task 08)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-03

Hand-written. Adds `app_user`, `user_session` and the `user_role` enum. `review.reviewer_id`
gets no FK to `app_user` here, so that reviews written by the CLI before this task stay valid.
The downgrade drops both tables and the enum.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

USER_ROLES = ("admin", "reviewer")


def upgrade() -> None:
    pg.ENUM(*USER_ROLES, name="user_role").create(op.get_bind(), checkfirst=False)
    op.create_table(
        "app_user",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "role", pg.ENUM(*USER_ROLES, name="user_role", create_type=False), nullable=False
        ),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_app_user"),
        sa.UniqueConstraint("email", name="uq_app_user_email"),
    )
    op.create_table(
        "user_session",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_user_session"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name="fk_user_session_user_id_app_user"
        ),
        sa.UniqueConstraint("token_hash", name="uq_user_session_token_hash"),
    )
    op.create_index("ix_user_session_user_id", "user_session", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_session")
    op.drop_table("app_user")
    op.execute("DROP TYPE user_role")
