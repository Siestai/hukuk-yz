"""`python -m app.users` (task 08). Skipped when DATABASE_URL is unset; CI sets it.

`main` runs its own event loop, so the tests call it in a thread. A SystemExit must not cross
into the test's own loop (asyncio re-raises it there), so `_run` returns its message instead."""

import asyncio
import getpass
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import users
from app.models.user import AppUser, UserRole, UserSession

PASSWORD = "correct horse battery"
SessionFactory = async_sessionmaker[AsyncSession]


def _typed(monkeypatch: pytest.MonkeyPatch, *answers: str) -> None:
    replies = iter(answers)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": next(replies))


def _main(argv: tuple[str, ...]) -> str | None:
    try:
        users.main(argv)
    except SystemExit as exit_:
        return str(exit_.code)
    return None


async def _run(*argv: str) -> str | None:
    """The message `main` exited with, or None when it finished normally."""
    return await asyncio.to_thread(_main, argv)


async def _create(
    monkeypatch: pytest.MonkeyPatch, email: str = "orhan@x.test", role: str = "admin"
) -> str | None:
    _typed(monkeypatch, PASSWORD, PASSWORD)
    return await _run("create", "--email", email, "--name", "Orhan", "--role", role)


async def _all_users(factory: SessionFactory) -> list[AppUser]:
    async with factory() as session:
        return list((await session.execute(select(AppUser))).scalars())


async def test_create_stores_a_lowercased_email_and_an_argon2id_hash(
    users_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _create(monkeypatch, email="Orhan@X.test")
    (user,) = await _all_users(users_factory)
    assert user.email == "orhan@x.test"
    assert user.role is UserRole.admin
    assert user.is_active
    assert user.password_hash.startswith("$argon2id$")
    assert PasswordHasher().verify(user.password_hash, PASSWORD)


async def test_the_same_email_cannot_be_created_twice_whatever_its_case(
    users_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _create(monkeypatch, email="Orhan@X.test")
    assert "zaten kayıtlı" in str(await _create(monkeypatch, email="orhan@x.test"))
    assert len(await _all_users(users_factory)) == 1


@pytest.mark.parametrize(
    ("answers", "message"),
    [
        (("short", "short"), "at least 12"),
        ((PASSWORD, PASSWORD + "x"), "eşleşmiyor"),
    ],
)
async def test_a_short_or_mismatched_password_creates_nothing(
    users_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
    answers: tuple[str, str],
    message: str,
) -> None:
    _typed(monkeypatch, *answers)
    exit_message = await _run("create", "--email", "a@x.test", "--name", "A", "--role", "reviewer")
    assert message in str(exit_message)
    assert await _all_users(users_factory) == []


async def test_set_password_replaces_the_hash(
    users_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _create(monkeypatch)
    new_password = "another long passphrase"
    _typed(monkeypatch, new_password, new_password)
    await _run("set-password", "--email", "ORHAN@x.test")
    (user,) = await _all_users(users_factory)
    assert PasswordHasher().verify(user.password_hash, new_password)


async def test_set_password_for_an_unknown_user_fails(
    users_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _typed(monkeypatch, PASSWORD, PASSWORD)
    assert "Kullanıcı yok" in str(await _run("set-password", "--email", "nobody@x.test"))


async def _open_a_session_per_user(users_factory: SessionFactory) -> None:
    async with users_factory() as session:
        for user in (await session.execute(select(AppUser))).scalars():
            session.add(
                UserSession(
                    user_id=user.id,
                    token_hash=f"hash-{user.email}",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        await session.commit()


async def _revocation_state(users_factory: SessionFactory) -> dict[str, tuple[bool, bool]]:
    """email -> (is_active, session revoked)"""
    async with users_factory() as session:
        rows = (
            await session.execute(
                select(AppUser.email, AppUser.is_active, UserSession.revoked_at).join(
                    UserSession, UserSession.user_id == AppUser.id
                )
            )
        ).all()
    return {email: (active, revoked is not None) for email, active, revoked in rows}


async def test_set_password_revokes_the_open_sessions_of_that_user_only(
    users_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _create(monkeypatch)
    await _create(monkeypatch, email="baran@x.test", role="reviewer")
    await _open_a_session_per_user(users_factory)

    _typed(monkeypatch, PASSWORD, PASSWORD)
    await _run("set-password", "--email", "orhan@x.test")

    assert await _revocation_state(users_factory) == {
        "orhan@x.test": (True, True),
        "baran@x.test": (True, False),
    }


async def test_deactivate_revokes_the_open_sessions(
    users_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _create(monkeypatch)
    await _create(monkeypatch, email="baran@x.test", role="reviewer")
    await _open_a_session_per_user(users_factory)

    await _run("deactivate", "--email", "orhan@x.test")

    assert await _revocation_state(users_factory) == {
        "orhan@x.test": (False, True),
        "baran@x.test": (True, False),
    }


async def test_list_prints_every_user(
    users_factory: SessionFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await _create(monkeypatch)
    await _create(monkeypatch, email="baran@x.test", role="reviewer")
    await _run("deactivate", "--email", "baran@x.test")
    capsys.readouterr()
    await _run("list")
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "baran@x.test\tOrhan\treviewer\tpasif",
        "orhan@x.test\tOrhan\tadmin\taktif",
    ]


def test_the_password_is_not_an_argument() -> None:
    with pytest.raises(SystemExit):
        users.main(
            ["create", "--email", "a@x.test", "--name", "A", "--role", "admin", "--password", "x"]
        )
