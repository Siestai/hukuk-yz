from dataclasses import replace
from datetime import date

from fakes import Reply, Site, make_adapter, make_key

from hukuk_verify import Outcome, verify
from hukuk_verify.adapters import AymAdapter

KEY = make_key(
    court="aym",
    court_level="aym",
    chamber="",
    esas_no="2024/157",
    karar_no="2025/121",
    decision_date=date(2025, 6, 3),
    decision_kind="norm_denetimi",
)
UUID = "fa0eb0dc-de88-f3b2-1262-16401f035f00"
FILE = "/files/normdenetimi/ee5093c9-f74e-4bbf-b279-fa85e22b0ff9.html"


def site(*search: Reply) -> Site:
    return Site(
        {
            "/api/core/public/search": list(search),
            f"/api/core/public/kararlar/{UUID}/dosyalar": Reply.fixture("aym_dosyalar.json"),
            FILE: Reply.fixture("aym_dosya.html"),
        }
    )


async def test_found_is_searched_by_kararTipi_esas_and_karar() -> None:
    fake = site(Reply.fixture("aym_search_found.json"))
    result = await make_adapter(AymAdapter, fake).lookup(KEY)
    body = fake.bodies("/api/core/public/search")[0]
    assert {k: body[k] for k in ("kararTipi", "esasNo", "kararNo", "sort", "order")} == {
        "kararTipi": "NormDenetimi",
        "esasNo": "2024/157",
        "kararNo": "2025/121",
        "sort": "yayinTarihi",
        "order": "desc",
    }
    assert isinstance(body["_timestamp"], int)
    [row] = result.rows
    assert (row.ref, row.esas_no, row.karar_no, row.chamber) == (UUID, "2024/157", "2025/121", "")
    assert row.decision_date == date(2025, 6, 3)
    assert row.url.endswith("&type=NormDenetimi")
    assert "id=a2JiOmZhMGViMGRjLWRlODgtZjNiMi0xMjYyLTE2NDAxZjAzNWYwMA&" in row.url  # no padding


async def test_decision_kind_maps_to_kararTipi() -> None:
    adapter = make_adapter(AymAdapter, site())
    for kind in ("norm_denetimi", "iptal", "red"):
        assert adapter.supports(replace(KEY, decision_kind=kind))
    assert not adapter.supports(replace(KEY, decision_kind="karar"))
    assert not adapter.supports(replace(KEY, decision_kind=None))
    assert not adapter.supports(replace(KEY, karar_no=None))


async def test_an_individual_application_is_searched_by_its_number() -> None:
    fake = site(Reply.fixture("aym_search_empty.json"))
    key = replace(KEY, decision_kind="bireysel_basvuru", esas_no="2019/1234", karar_no=None)
    adapter = make_adapter(AymAdapter, fake)
    assert adapter.supports(key)
    await adapter.lookup(key)
    body = fake.bodies("/api/core/public/search")[0]
    assert (body["kararTipi"], body["basvuruNo"]) == ("BireyselBasvuru", "2019/1234")
    assert "esasNo" not in body


async def test_found_verifies_and_hashes_the_first_html_file() -> None:
    fake = site(Reply.fixture("aym_search_found.json"))
    result = await verify(make_adapter(AymAdapter, fake), KEY)
    assert result.outcome is Outcome.verified_official
    assert result.official_ref == UUID
    assert result.official_text is not None
    assert "FIXTURE TEXT" in result.official_text.body
    dosyalar = fake.requests[-2]
    assert dosyalar.url.params["kararTipi"] == "NormDenetimi"
    assert fake.requests[-1].url.path == FILE


async def test_not_found_is_not_in_source() -> None:
    result = await verify(
        make_adapter(AymAdapter, site(Reply.fixture("aym_search_empty.json"))), KEY
    )
    assert result.outcome is Outcome.not_in_source


async def test_a_different_date_is_a_mismatch() -> None:
    fake = site(Reply.fixture("aym_search_found.json"))
    result = await verify(
        make_adapter(AymAdapter, fake),
        replace(KEY, decision_date=date(2025, 7, 1)),
    )
    assert result.outcome is Outcome.mismatch


async def test_a_decision_without_html_files_has_no_text() -> None:
    fake = site(Reply.fixture("aym_search_found.json"))
    fake._routes[f"/api/core/public/kararlar/{UUID}/dosyalar"] = Reply(
        200, '{"success": true, "data": []}'
    )
    assert await make_adapter(AymAdapter, fake).fetch_text(UUID) is None
