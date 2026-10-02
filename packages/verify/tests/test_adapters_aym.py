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


def site(*search: Reply) -> Site:
    return Site({"/api/core/public/search": list(search)})


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


async def test_individual_application_row_has_no_esas_or_karar_number() -> None:
    fake = site(Reply.fixture("aym_search_individual.json"), Reply.fixture("aym_search_by_id.json"))
    key = replace(
        KEY,
        decision_kind="bireysel_basvuru",
        esas_no="2024/41763",
        karar_no=None,
        decision_date=date(2025, 7, 8),
    )
    result = await verify(make_adapter(AymAdapter, fake), key)
    assert result.outcome is Outcome.verified_official
    assert fake.bodies("/api/core/public/search")[1]["kararTipi"] == "BireyselBasvuru"


async def test_found_verifies_and_hashes_the_text_of_the_search_by_id() -> None:
    fake = site(Reply.fixture("aym_search_found.json"), Reply.fixture("aym_search_by_id.json"))
    result = await verify(make_adapter(AymAdapter, fake), KEY)
    assert result.outcome is Outcome.verified_official
    assert result.official_ref == UUID
    assert result.official_text is not None
    assert "FIXTURE TEXT" in result.official_text.body
    assert len(fake.requests) == 3  # robots.txt, search, search by id
    assert fake.bodies("/api/core/public/search")[1] == {
        "id": UUID,
        "size": 1,
        "kararTipi": "NormDenetimi",
    }


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


async def test_a_decision_without_icerik_has_no_text() -> None:
    for answer in ('{"data": [{"id": "x"}]}', '{"data": [{"id": "x", "icerik": ""}]}'):
        fake = site(Reply(200, answer))
        assert await make_adapter(AymAdapter, fake).fetch_text(UUID) is None
