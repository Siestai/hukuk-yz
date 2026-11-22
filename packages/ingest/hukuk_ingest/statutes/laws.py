"""Registry of the statutes `hukuk-ingest statutes` reads: which files belong to a law, its name,
and its own entry in `amending_acts.toml` (the original in-force date).

A law that is not listed here is never picked up from the archive."""

import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Law:
    number: str
    name: str  # official title; written to the record instead of the title parsed from the file
    kabul_tarihi: date  # (number, kabul_tarihi) is the law's own entry in amending_acts.toml
    file_pattern: str = ""  # regex searched in the file name; default: the number standing alone
    # Non-empty: the law is repealed except for these articles, and only they are kept (the
    # source prints the rest as range stubs such as `Madde 15-110- (Mülga: ...)`).
    only_articles: tuple[str, ...] = ()
    # The timelines of 4857 and 5510 were reviewed as parser version 1 produced them, so the
    # rules added for the single-snapshot laws are off for them: their output must not change.
    # With the rules on, the in-force table printed at the end of the text is cut off, and an
    # amendment recorded only in a footnote dates the snapshot and the start of the first version.
    legacy_rules: bool = False

    def matches(self, file_name: str) -> bool:
        pattern = self.file_pattern or rf"(?<!\d){self.number}(?!\d)"
        return re.search(pattern, file_name) is not None


LAWS: tuple[Law, ...] = (
    Law("1475", "İŞ KANUNU", date(1971, 8, 25), only_articles=("14",)),
    Law("4857", "İŞ KANUNU", date(2003, 5, 22), legacy_rules=True),
    Law(
        "5510",
        "SOSYAL SİGORTALAR VE GENEL SAĞLIK SİGORTASI KANUNU",
        date(2006, 5, 31),
        legacy_rules=True,
    ),
    Law("6356", "SENDİKALAR VE TOPLU İŞ SÖZLEŞMESİ KANUNU", date(2012, 10, 18)),
    Law("7036", "İŞ MAHKEMELERİ KANUNU", date(2017, 10, 12)),
)


def law_for_file(file_name: str) -> Law | None:
    return next((law for law in LAWS if law.matches(file_name)), None)


def law_by_number(number: str) -> Law | None:
    return next((law for law in LAWS if law.number == number), None)
