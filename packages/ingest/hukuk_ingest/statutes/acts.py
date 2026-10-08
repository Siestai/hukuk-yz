"""Registry of amending acts (`amending_acts.toml`): in-force dates by (law, kabul date)."""

import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_ACTS = Path(__file__).with_name("amending_acts.toml")


@dataclass(frozen=True)
class ArticleException:
    """An article whose in-force date differs from the act's."""

    statute: str
    article: str
    scope: str
    yururluk: date
    source: str


@dataclass(frozen=True)
class Act:
    law: str  # "6552", "KHK-665"
    kabul_tarihi: date
    rg_tarihi: date | None
    rg_sayisi: str | None
    yururluk: date | None
    source_url: str | None
    note: str
    exceptions: tuple[ArticleException, ...] = ()


@dataclass
class Registry:
    acts: dict[tuple[str, date], Act] = field(default_factory=dict)

    def get(self, law: str, kabul: date) -> Act | None:
        return self.acts.get((law, kabul))

    def effective_dates(
        self, law: str, kabul: date, statute: str, article: str
    ) -> tuple[set[date], str] | None:
        """In-force dates of the act for one article and where they come from ("exception" or
        "act"); None when the act is unknown or has no in-force date."""
        act = self.get(law, kabul)
        if act is None:
            return None
        exc = {e.yururluk for e in act.exceptions if e.statute == statute and e.article == article}
        if exc:
            return exc, "exception"
        return ({act.yururluk}, "act") if act.yururluk else None

    def without_yururluk(self) -> list[Act]:
        return [a for a in self.acts.values() if a.yururluk is None]


def _req(table: dict[str, Any], key: str, where: str) -> Any:
    if key not in table:
        raise ValueError(f"{where}: missing `{key}`")
    return table[key]


def _date(value: Any, key: str, where: str) -> date:
    if not isinstance(value, date):
        raise ValueError(f"{where}: `{key}` must be a TOML date, got {value!r}")
    return value


def parse_acts(data: dict[str, Any]) -> Registry:
    registry = Registry()
    for i, table in enumerate(data.get("act", [])):
        where = f"act #{i + 1}"
        law = str(_req(table, "law", where))
        kabul = _date(_req(table, "kabul_tarihi", where), "kabul_tarihi", where)
        where = f"act {law} {kabul}"
        if (law, kabul) in registry.acts:
            raise ValueError(f"{where}: duplicate (law, kabul_tarihi)")
        yururluk = _date(table["yururluk"], "yururluk", where) if "yururluk" in table else None
        source_url = table.get("source_url")
        if (yururluk or table.get("exception")) and not source_url:
            raise ValueError(f"{where}: `source_url` is required when `yururluk` is set")
        exceptions = []
        for exc in table.get("exception", []):
            exc_where = f"{where} exception"
            exceptions.append(
                ArticleException(
                    statute=str(_req(exc, "statute", exc_where)),
                    article=str(_req(exc, "article", exc_where)),
                    scope=str(exc.get("scope", "")),
                    yururluk=_date(_req(exc, "yururluk", exc_where), "yururluk", exc_where),
                    source=str(_req(exc, "source", exc_where)),
                )
            )
        rg = table.get("rg_tarihi")
        registry.acts[(law, kabul)] = Act(
            law=law,
            kabul_tarihi=kabul,
            rg_tarihi=_date(rg, "rg_tarihi", where) if rg is not None else None,
            rg_sayisi=str(table["rg_sayisi"]) if "rg_sayisi" in table else None,
            yururluk=yururluk,
            source_url=source_url,
            note=str(table.get("note", "")),
            exceptions=tuple(exceptions),
        )
    return registry


def load_acts(path: Path = DEFAULT_ACTS) -> Registry:
    with path.open("rb") as fh:
        return parse_acts(tomllib.load(fh))
