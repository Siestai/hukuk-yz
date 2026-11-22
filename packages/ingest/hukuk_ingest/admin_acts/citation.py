"""How a genelge and its sections are named in titles, headers and citations."""

from hukuk_ingest.admin_acts.split import INTRO

ISSUER_LABELS = {"sgk": "SGK"}


def act_label(ref: str, issuer: str | None) -> str:
    """ "SGK Genelgesi 2020/8"; "Genelge 2020/8" for an issuer without a short name."""
    label = ISSUER_LABELS.get(issuer or "")
    return f"{label} Genelgesi {ref}" if label else f"Genelge {ref}"


def section_label(section_no: str) -> str:
    """ "m.2.6.2.5"; the opening text ("Giriş") stands as it is."""
    return section_no if section_no == INTRO else f"m.{section_no}"


def citation(ref: str, section_no: str) -> str:
    """ "2020/8 m.2.6.2.5": the künye the agent reads a section by."""
    return f"{ref} {section_label(section_no)}"
