"""Login, logout and the session dependencies (task 08).

Sessions are server-side: the client holds an opaque token (cookie `hukuk_session` or
`Authorization: Bearer`), the database holds its SHA-256. The lifetime is fixed
(`SESSION_TTL_HOURS`) and not extended by use.

CSRF: a state-changing request authenticated by the cookie must declare
`Content-Type: application/json` (else 415). A cross-site HTML form cannot send that type, and
a cross-site `fetch` with it needs a CORS preflight, which this app never grants; SameSite=Lax
already keeps the cookie off cross-site POSTs. Together that is enough for Phase 1. Requests
authenticated by Bearer are exempt: the browser never adds that header by itself.
"""

import asyncio
import hashlib
import math
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import make_session_factory
from app.errors import ApiError
from app.models.user import AppUser, LoginAttempt, UserRole, UserSession
from app.settings import Settings, get_settings
from hukuk_models import ErrorCode, LoginRequest, UserOut

COOKIE_NAME = "hukuk_session"
MIN_PASSWORD_LENGTH = 12
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LAST_SEEN_INTERVAL = timedelta(minutes=5)

router = APIRouter(prefix="/auth", tags=["auth"])

_hasher = PasswordHasher()
# Verified against when the e-mail is unknown, so that the response time does not tell.
_DUMMY_HASH = _hasher.hash("dummy password for timing")


class LoginResponse(BaseModel):
    user: UserOut
    token: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must have at least {MIN_PASSWORD_LENGTH} characters")
    return _hasher.hash(password)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _user_out(user: AppUser) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, display_name=user.display_name, role=user.role.value
    )


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with make_session_factory(request.app.state.engine)() as session:
        yield session


Db = Annotated[AsyncSession, Depends(get_db)]


def _unauthorized() -> ApiError:
    return ApiError(401, ErrorCode.unauthorized)


def _request_token(request: Request) -> str:
    """The session token of the request: Bearer first, else the cookie (CSRF-checked).

    When both are present, Bearer wins and the cookie is ignored: an invalid Bearer does not
    fall back to the cookie, and the CSRF check applies only to the cookie path.
    """
    scheme, _, bearer = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and bearer.strip():
        return bearer.strip()
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise _unauthorized()
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if request.method in UNSAFE_METHODS and content_type != "application/json":
        raise ApiError(415, ErrorCode.unsupported_media_type)
    return token


async def current_session(
    token: Annotated[str, Depends(_request_token)], db: Db
) -> tuple[AppUser, UserSession]:
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(AppUser, UserSession)
            .join(UserSession, UserSession.user_id == AppUser.id)
            .where(
                UserSession.token_hash == _token_hash(token),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                AppUser.is_active.is_(True),
            )
        )
    ).one_or_none()
    if row is None:
        raise _unauthorized()
    user, session = row.tuple()
    if session.last_seen_at is None or now - session.last_seen_at > LAST_SEEN_INTERVAL:
        session.last_seen_at = now
        await db.commit()
    return user, session


CurrentSession = Annotated[tuple[AppUser, UserSession], Depends(current_session)]


async def current_user(auth: CurrentSession) -> AppUser:
    return auth[0]


CurrentUser = Annotated[AppUser, Depends(current_user)]


def require_role(role: Literal["admin", "reviewer"]) -> Callable[[AppUser], Awaitable[AppUser]]:
    """Dependency: 403 unless the user has `role`; an admin passes every role check."""
    required = UserRole(role)

    async def check(user: CurrentUser) -> AppUser:
        if user.role not in (required, UserRole.admin):
            raise ApiError(403, ErrorCode.forbidden)
        return user

    return check


async def login_retry_after(
    db: AsyncSession, email: str, ip: str | None, now: datetime, settings: Settings
) -> int | None:
    """Seconds until a login may be tried again, or None when it may be tried now.

    Blocked when, inside the window ending at `now`, the e-mail has `login_max_fails_per_email`
    failed attempts or the IP has `login_max_fails_per_ip`. A success does not clear them: the
    window just slides. The block lifts when the oldest failure that still counts leaves it.
    """
    window = timedelta(minutes=settings.login_window_minutes)
    scopes: list[tuple[ColumnElement[bool], int]] = [
        (LoginAttempt.email == email, settings.login_max_fails_per_email)
    ]
    if ip is not None:
        scopes.append((LoginAttempt.ip == ip, settings.login_max_fails_per_ip))
    waits: list[int] = []
    for scope, limit in scopes:
        newest_failures = (
            (
                await db.execute(
                    select(LoginAttempt.attempted_at)
                    .where(
                        scope,
                        LoginAttempt.succeeded.is_(False),
                        LoginAttempt.attempted_at > now - window,
                    )
                    .order_by(LoginAttempt.attempted_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        if len(newest_failures) >= limit:
            waits.append(max(1, math.ceil((newest_failures[-1] + window - now).total_seconds())))
    return max(waits) if waits else None


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response, db: Db) -> LoginResponse:
    settings = get_settings()
    email = normalize_email(body.email)
    ip = request.client.host if request.client else None
    now = datetime.now(UTC)
    retry_after = await login_retry_after(db, email, ip, now, settings)
    if retry_after is not None:
        raise ApiError(
            429,
            ErrorCode.too_many_attempts,
            {"retry_after": retry_after},
            {"Retry-After": str(retry_after)},
        )
    user = (await db.execute(select(AppUser).where(AppUser.email == email))).scalar_one_or_none()
    try:
        await asyncio.to_thread(
            _hasher.verify, user.password_hash if user else _DUMMY_HASH, body.password
        )
        password_ok = True
    except (VerificationError, InvalidHashError):
        password_ok = False
    succeeded = user is not None and password_ok and user.is_active
    db.add(LoginAttempt(email=email, ip=ip, succeeded=succeeded, attempted_at=now))
    if user is None or not succeeded:
        await db.commit()
        raise _unauthorized()

    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = await asyncio.to_thread(_hasher.hash, body.password)
    user.last_login_at = now
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=_token_hash(token),
            expires_at=now + timedelta(hours=settings.session_ttl_hours),
        )
    )
    await db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return LoginResponse(user=_user_out(user), token=token)


@router.post("/logout", status_code=204)
async def logout(response: Response, auth: CurrentSession, db: Db) -> None:
    auth[1].revoked_at = datetime.now(UTC)
    await db.commit()
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
    )


@router.get("/me")
async def me(user: CurrentUser) -> UserOut:
    return _user_out(user)
