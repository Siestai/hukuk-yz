"""Users and server-side sessions (data-model.md §3, task 08)."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, PgEnum, UuidPkMixin


class UserRole(PgEnum):
    admin = "admin"
    reviewer = "reviewer"


# The migration (0005) repeats the labels literally; tests/test_orm_consistency.py checks them.
USER_ROLE_TYPE = "user_role"


class AppUser(UuidPkMixin, Base):
    __tablename__ = "app_user"

    # Stored lower-cased (app.auth.normalize_email); unique on that value.
    email: Mapped[str] = mapped_column(unique=True)
    display_name: Mapped[str]
    role: Mapped[UserRole] = mapped_column(UserRole.pg_type(USER_ROLE_TYPE))
    password_hash: Mapped[str]
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    last_login_at: Mapped[datetime | None]


class UserSession(UuidPkMixin, Base):
    __tablename__ = "user_session"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), index=True)
    # SHA-256 hex of the opaque token; the raw token is never stored.
    token_hash: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    last_seen_at: Mapped[datetime | None]
