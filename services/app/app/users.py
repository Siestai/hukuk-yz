"""Manage users (task 08). The password is asked on the terminal, never taken from an argument
or the environment.

    python -m app.users create --email E --name N --role {admin,reviewer}
    python -m app.users set-password --email E    (also revokes the open sessions)
    python -m app.users deactivate --email E
    python -m app.users list
    python -m app.users prune-login-attempts      (deletes login attempts older than 30 days)
"""

import argparse
import asyncio
import getpass
import sys
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from functools import partial

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_password, normalize_email
from app.db import make_engine, make_session_factory
from app.models.user import AppUser, LoginAttempt, UserRole, UserSession
from app.settings import get_settings

LOGIN_ATTEMPT_RETENTION = timedelta(days=30)


def _ask_password() -> str:
    password = getpass.getpass("Parola: ")
    if getpass.getpass("Parola (tekrar): ") != password:
        sys.exit("Parolalar eşleşmiyor")
    try:
        return hash_password(password)
    except ValueError as exc:
        sys.exit(str(exc))


async def _find(session: AsyncSession, email: str) -> AppUser:
    user = (
        await session.execute(select(AppUser).where(AppUser.email == normalize_email(email)))
    ).scalar_one_or_none()
    if user is None:
        sys.exit(f"Kullanıcı yok: {normalize_email(email)}")
    return user


async def _create(session: AsyncSession, *, args: argparse.Namespace, password_hash: str) -> None:
    session.add(
        AppUser(
            email=normalize_email(args.email),
            display_name=args.name,
            role=UserRole(args.role),
            password_hash=password_hash,
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        sys.exit(f"Bu e-posta zaten kayıtlı: {normalize_email(args.email)}")
    print(f"Oluşturuldu: {normalize_email(args.email)} ({args.role})")


async def _revoke_sessions(session: AsyncSession, user: AppUser) -> None:
    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def _set_password(
    session: AsyncSession, *, args: argparse.Namespace, password_hash: str
) -> None:
    user = await _find(session, args.email)
    user.password_hash = password_hash
    await _revoke_sessions(session, user)
    await session.commit()
    print(f"Parola güncellendi: {normalize_email(args.email)}")


async def _deactivate(session: AsyncSession, *, args: argparse.Namespace) -> None:
    user = await _find(session, args.email)
    user.is_active = False
    await _revoke_sessions(session, user)
    await session.commit()
    print(f"Pasifleştirildi: {user.email}")


async def _list(session: AsyncSession) -> None:
    for user in (await session.execute(select(AppUser).order_by(AppUser.email))).scalars():
        state = "aktif" if user.is_active else "pasif"
        print(f"{user.email}\t{user.display_name}\t{user.role.value}\t{state}")


async def _prune_login_attempts(session: AsyncSession) -> None:
    result = await session.execute(
        delete(LoginAttempt)
        .where(LoginAttempt.attempted_at < datetime.now(UTC) - LOGIN_ATTEMPT_RETENTION)
        .returning(LoginAttempt.id)
    )
    deleted = len(result.all())
    await session.commit()
    print(f"Silinen giriş denemesi: {deleted}")


async def _run(operation: Callable[[AsyncSession], Awaitable[None]]) -> None:
    engine = make_engine(get_settings().database_url)
    try:
        async with make_session_factory(engine)() as session:
            await operation(session)
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.users", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--role", required=True, choices=[r.value for r in UserRole])
    commands.add_parser("set-password").add_argument("--email", required=True)
    commands.add_parser("deactivate").add_argument("--email", required=True)
    commands.add_parser("list")
    commands.add_parser("prune-login-attempts")
    args = parser.parse_args(argv)
    operation: Callable[[AsyncSession], Awaitable[None]]
    match args.command:
        case "create":
            operation = partial(_create, args=args, password_hash=_ask_password())
        case "set-password":
            operation = partial(_set_password, args=args, password_hash=_ask_password())
        case "deactivate":
            operation = partial(_deactivate, args=args)
        case "prune-login-attempts":
            operation = _prune_login_attempts
        case _:
            operation = _list
    asyncio.run(_run(operation))


if __name__ == "__main__":
    main()
