"""The command line: gating, request caps and the database-free `--keys` mode."""

import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.verification.__main__ as cli
from app.models.common import Court, CourtLevel, Source, SourceRank, Verification
from app.models.decision import Decision
from app.settings import get_verify_settings
from hukuk_verify.adapters import AymAdapter, DanistayAdapter, UyapEmsalAdapter, YargitayAdapter
from hukuk_verify.ratelimit import RateLimiter

AYM_KEY = {
    "court": "aym",
    "esas_no": "2024/157",
    "karar_no": "2025/121",
    "decision_date": "2025-06-03",
    "decision_kind": "norm_denetimi",
}
SEARCH = {
    "data": [
        {
            "id": "u-1",
            "esasNo": "2024/157",
            "kararNo": "2025/121",
            "kararTarihi": "2025-06-03",
            "icerik": "<p>x</p>",
        }
    ]
}


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """A fake AYM behind every client the CLI builds, and a limiter that does not sleep."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path == "/api/core/public/search":
            return httpx.Response(200, json=SEARCH)
        return httpx.Response(404, json={"error": "No static resource"})

    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(
        cli,
        "build_client",
        lambda proxy, agent: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(cli, "RateLimiter", lambda **kw: RateLimiter(sleep=no_sleep, **kw))
    monkeypatch.setenv("LIVE", "1")
    monkeypatch.setenv("VERIFY_CONTACT", "test@example.invalid")
    get_verify_settings.cache_clear()
    return requests


def keys_file(tmp_path: Path, n: int = 1) -> Path:
    path = tmp_path / "keys.jsonl"
    path.write_text("\n".join(json.dumps(AYM_KEY) for _ in range(n)) + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("limit", "dry_run", "permission", "expected"),
    [
        (None, False, False, 20),
        (50, False, False, 20),
        (5, False, False, 5),
        (None, False, True, None),
        (200, False, True, 200),
        (None, True, True, 20),
        (100, True, True, 100),
    ],
)
def test_request_budget(
    limit: int | None, dry_run: bool, permission: bool, expected: int | None
) -> None:
    assert cli.request_budget(limit, dry_run, permission) == expected


@pytest.mark.parametrize("value", ["0", "-3"])
def test_a_limit_below_one_is_refused(value: str, tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["--keys", str(keys_file(tmp_path)), "--limit", value])
    assert raised.value.code == 2


def test_the_client_ignores_the_proxy_variables_of_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://env-proxy.invalid:3128")
    assert cli.build_client(None, "agent")._mounts == {}
    assert cli.build_client("http://given.invalid:3128", "agent")._mounts != {}


async def test_each_proxy_setting_reaches_only_its_sources_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proxies = {
        "VERIFY_PROXY_YARGITAY": "http://yargitay.invalid:1",
        "VERIFY_PROXY_EMSAL": "http://emsal.invalid:2",
        "VERIFY_PROXY_AYM": "http://aym.invalid:3",
        "VERIFY_PROXY_DANISTAY": "http://danistay.invalid:4",
    }
    for name, value in proxies.items():
        monkeypatch.setenv(name, value)
    get_verify_settings.cache_clear()
    sent: dict[int, str | None] = {}

    def build(proxy: str | None, agent: str) -> httpx.AsyncClient:
        client = httpx.AsyncClient()
        sent[id(client)] = proxy
        return client

    monkeypatch.setattr(cli, "build_client", build)
    expected = {
        "yargitay": ("http://yargitay.invalid:1", YargitayAdapter),
        "bam": ("http://emsal.invalid:2", UyapEmsalAdapter),
        "aym": ("http://aym.invalid:3", AymAdapter),
        "danistay": ("http://danistay.invalid:4", DanistayAdapter),
    }
    for court, (proxy, adapter_class) in expected.items():
        adapter, client = cli._adapter(court, get_verify_settings(), None)
        assert type(adapter) is adapter_class
        assert adapter._client is client
        assert sent[id(client)] == proxy
        await client.aclose()


def test_the_user_agent_identifies_us_and_is_a_valid_header() -> None:
    agent = cli.user_agent("orhan@example.invalid")
    assert agent.startswith("hukuk-yz-verify/")
    assert "orhan@example.invalid" in agent
    cli.build_client(None, agent)  # httpx refuses a header value that is not ASCII


def test_keys_default_to_the_courts_level_and_kind(tmp_path: Path) -> None:
    path = tmp_path / "k.jsonl"
    path.write_text(
        json.dumps({"court": "yargitay", "esas_no": "2017/1", "karar_no": "2020/2"}) + "\n",
        encoding="utf-8",
    )
    [candidate] = cli.read_keys(path)["yargitay"]
    key = candidate.key
    assert (candidate.id, key.court_level, key.decision_kind, key.chamber) == (
        None,
        "daire",
        "karar",
        "",
    )
    assert key.decision_date is None


def test_an_unknown_court_in_the_keys_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "k.jsonl"
    path.write_text(json.dumps({"court": "aihm"}) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="unknown court"):
        cli.read_keys(path)


def test_without_live_nothing_is_sent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*args: object) -> httpx.AsyncClient:
        raise AssertionError("a client was built without LIVE=1")

    monkeypatch.setattr(cli, "build_client", forbidden)
    monkeypatch.delenv("LIVE", raising=False)
    assert cli.main(["--keys", str(keys_file(tmp_path, 3))]) == 0
    assert "aym: 3 due; LIVE=1 is needed" in capsys.readouterr().out


def test_live_runs_need_a_contact_address(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, site: list[httpx.Request]
) -> None:
    monkeypatch.delenv("VERIFY_CONTACT")
    get_verify_settings.cache_clear()
    with pytest.raises(SystemExit, match="VERIFY_CONTACT"):
        cli.main(["--keys", str(keys_file(tmp_path))])
    assert site == []


def test_keys_mode_prints_the_outcome_and_needs_no_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    site: list[httpx.Request],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    report = tmp_path / "report"
    assert cli.main(["--keys", str(keys_file(tmp_path)), "--report", str(report)]) == 0
    out = capsys.readouterr().out
    assert "aym E. 2024/157 K. 2025/121 -> verified_official" in out
    assert (report / "verify-summary.json").exists()


def test_keys_mode_names_the_mismatched_field(
    tmp_path: Path, site: list[httpx.Request], capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "keys.jsonl"
    path.write_text(json.dumps({**AYM_KEY, "decision_date": "2025-07-01"}) + "\n", encoding="utf-8")
    assert cli.main(["--keys", str(path)]) == 0
    assert "-> mismatch (decision_date)" in capsys.readouterr().out


def test_without_permission_a_source_gets_at_most_20_requests(
    tmp_path: Path, site: list[httpx.Request]
) -> None:
    assert cli.main(["--keys", str(keys_file(tmp_path, 30))]) == 1  # the budget stops the source
    assert len(site) == 20


def test_limit_lowers_the_cap_and_permission_lifts_it(
    tmp_path: Path, site: list[httpx.Request]
) -> None:
    cli.main(["--keys", str(keys_file(tmp_path, 30)), "--limit", "7"])
    assert len(site) == 7
    site.clear()
    cli.main(["--keys", str(keys_file(tmp_path, 30)), "--limit", "40", "--i-have-permission"])
    assert len(site) == 40


def test_keys_cannot_be_combined_with_recheck(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--keys", str(keys_file(tmp_path)), "--recheck", "mismatch"])


async def test_a_database_run_stores_the_result_and_the_official_cache(
    kb_factory: async_sessionmaker[AsyncSession],
    new_decision: Callable[..., Awaitable[uuid.UUID]],
    site: list[httpx.Request],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VERIFY_CACHE_DIR", str(tmp_path / "official"))
    get_verify_settings.cache_clear()
    async with kb_factory() as session:
        decision_id = await new_decision(
            session,
            court=Court.aym,
            court_level=CourtLevel.aym,
            chamber="",
            esas_no="2024/157",
            karar_no="2025/121",
            decision_kind="norm_denetimi",
            decision_date=date(2025, 6, 3),
        )
        await session.commit()

    assert await cli._run(cli._parser().parse_args(["--court", "aym"])) == 0

    async with kb_factory() as session:
        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert decision.verification is Verification.verified_official
        assert (decision.verification_source, decision.verification_ref) == ("aym_kbb", "u-1")
        source = await session.get(Source, decision.source_id)
        assert source is not None
        assert source.source_rank is SourceRank.official_primary
    assert (tmp_path / "official" / "aym_kbb" / "u-1.json").exists()
