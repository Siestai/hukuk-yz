"""Registry of amending acts (`amending_acts.toml`): in-force dates by (law, kabul date)."""

import tomllib
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_ACTS = Path(__file__).with_name("amending_acts.toml")
BASIS_ACT, BASIS_EXCEPTION, BASIS_PARTIAL = "act", "exception", "partial"


@dataclass(frozen=True)
class ArticleException:
    """An article whose in-force date differs from the act's.

    `yururluk` empty: the date is vague ("ödeme dönemi başında"), so it is unknown.
    `partial`: only the part named in `scope` enters into force on `yururluk`; the rest of the
    article follows the act's date (the article is partly in force in between)."""

    statute: str
    article: str
    scope: str
    yururluk: date | None
    source: str
    partial: bool = False


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
    alias_of: date | None = None  # kabul date of the entry this one repeats (a typo in a note)


@dataclass
class Registry:
    acts: dict[tuple[str, date], Act] = field(default_factory=dict)

    def get(self, law: str, kabul: date) -> Act | None:
        return self.acts.get((law, kabul))

    def effective_dates(
        self, law: str, kabul: date, statute: str, article: str
    ) -> tuple[set[date], str] | None:
        """In-force dates of the act for one article and their basis: "act", "exception" (the
        article's own dates) or "partial" (act date plus the date of a part that enters into force
        at another time). None when the act is unknown, has no date, or the article has an
        exception without a date."""
        act = self.get(law, kabul)
        if act is None:
            return None
        exc = [e for e in act.exceptions if e.statute == statute and e.article == article]
        if any(e.yururluk is None for e in exc):
            return None
        whole = {e.yururluk for e in exc if not e.partial and e.yururluk}
        parts = {e.yururluk for e in exc if e.partial and e.yururluk}
        base = whole or ({act.yururluk} if act.yururluk else set())
        if not base:
            return None
        if parts:
            return base | parts, BASIS_PARTIAL
        return (base, BASIS_EXCEPTION) if whole else (base, BASIS_ACT)

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
                    yururluk=_date(exc["yururluk"], "yururluk", exc_where)
                    if "yururluk" in exc
                    else None,
                    source=str(_req(exc, "source", exc_where)),
                    partial=bool(exc.get("partial", False)),
                )
            )
            if exceptions[-1].partial and not (exceptions[-1].scope and exceptions[-1].yururluk):
                raise ValueError(f"{exc_where}: `partial` needs a `scope` and a `yururluk`")
        rg = table.get("rg_tarihi")
        alias = _date(table["alias_of"], "alias_of", where) if "alias_of" in table else None
        rg_date = _date(rg, "rg_tarihi", where) if rg is not None else None
        if alias is None and rg_date is not None and kabul > rg_date:
            raise ValueError(f"{where}: kabul_tarihi is after rg_tarihi {rg_date}")
        registry.acts[(law, kabul)] = Act(
            law=law,
            kabul_tarihi=kabul,
            rg_tarihi=rg_date,
            rg_sayisi=str(table["rg_sayisi"]) if "rg_sayisi" in table else None,
            yururluk=yururluk,
            source_url=source_url,
            note=str(table.get("note", "")),
            exceptions=tuple(exceptions),
            alias_of=alias,
        )
    return _resolve_aliases(registry)


def _resolve_aliases(registry: Registry) -> Registry:
    """An alias entry takes everything but its kabul date from the entry it repeats."""
    for key, act in list(registry.acts.items()):
        if act.alias_of is None:
            continue
        where = f"act {act.law} {act.kabul_tarihi}"
        target = registry.acts.get((act.law, act.alias_of))
        if target is None or target.alias_of is not None:
            raise ValueError(f"{where}: `alias_of` {act.alias_of} is not a plain entry of the law")
        if act.yururluk or act.exceptions or act.rg_tarihi:
            raise ValueError(f"{where}: an alias carries no dates or exceptions of its own")
        registry.acts[key] = replace(target, kabul_tarihi=act.kabul_tarihi, alias_of=act.alias_of)
    return registry


def load_acts(path: Path = DEFAULT_ACTS) -> Registry:
    with path.open("rb") as fh:
        return parse_acts(tomllib.load(fh))
