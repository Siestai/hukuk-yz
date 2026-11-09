"""Persistent beta chat records (task 18; md. 25, 31)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, UuidPkMixin


class ChatConversation(UuidPkMixin, Base):
    __tablename__ = "chat_conversation"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), index=True)
    delivery: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    title: Mapped[str]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class ChatTurn(UuidPkMixin, Base):
    __tablename__ = "chat_turn"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        CheckConstraint("mode IN ('short', 'detailed', 'reasoned')", name="mode"),
        Index("ix_chat_turn_conversation_created", "conversation_id", "created_at"),
        Index(
            "uq_chat_turn_conversation_request",
            "conversation_id",
            "request_id",
            unique=True,
            postgresql_where=text("request_id IS NOT NULL"),
        ),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_conversation.id"))
    # The client's delivery id of a user turn (idempotency key); never the primary key.
    request_id: Mapped[uuid.UUID | None]
    role: Mapped[str]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    mode: Mapped[str]
    trace_id: Mapped[str | None]
    model: Mapped[str | None]
    tokens: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cost: Mapped[float | None]
    latency_ms: Mapped[int | None]
    created_at: Mapped[datetime]


class ChatFeedback(UuidPkMixin, Base):
    __tablename__ = "chat_feedback"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR rating IN ('up', 'down')", name="rating"),
        CheckConstraint("point_index IS NULL OR point_index >= 0", name="point_index"),
    )
    turn_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_turn.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    rating: Mapped[str | None]
    point_index: Mapped[int | None]
    kind: Mapped[str | None]
    comment: Mapped[str]
    correction: Mapped[str]
    created_at: Mapped[datetime]
