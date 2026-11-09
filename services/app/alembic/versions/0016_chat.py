"""Persistent conversations, turns and feedback (docs/tasks/18-chat-wiring.md).

Revision ID: 0016; Revises: 0015. Personal beta data is separate from the KB.
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def pk() -> sa.Column[uuid.UUID]:
    return sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def upgrade() -> None:
    op.create_table(
        "chat_conversation",
        pk(),
        sa.Column("user_id", UUID(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_conversation_user_id", "chat_conversation", ["user_id"])
    op.create_table(
        "chat_turn",
        pk(),
        sa.Column("conversation_id", UUID(), sa.ForeignKey("chat_conversation.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text()),
        sa.Column("model", sa.Text()),
        sa.Column("tokens", JSONB()),
        sa.Column("cost", sa.Float()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_turn_role"),
        sa.CheckConstraint("mode IN ('short', 'detailed', 'reasoned')", name="ck_chat_turn_mode"),
    )
    op.create_index(
        "ix_chat_turn_conversation_created", "chat_turn", ["conversation_id", "created_at"]
    )
    op.create_table(
        "chat_feedback",
        pk(),
        sa.Column("turn_id", UUID(), sa.ForeignKey("chat_turn.id"), nullable=False),
        sa.Column("user_id", UUID(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("rating", sa.Text()),
        sa.Column("point_index", sa.Integer()),
        sa.Column("kind", sa.Text()),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("correction", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rating IS NULL OR rating IN ('up', 'down')", name="ck_chat_feedback_rating"
        ),
        sa.CheckConstraint(
            "point_index IS NULL OR point_index >= 0", name="ck_chat_feedback_point_index"
        ),
    )
    op.create_index("ix_chat_feedback_turn_id", "chat_feedback", ["turn_id"])


def downgrade() -> None:
    op.drop_table("chat_feedback")
    op.drop_table("chat_turn")
    op.drop_table("chat_conversation")
