"""`hukuk-ingest admin-acts`: the SGK genelges in scope -> admin-acts.jsonl (handoff 2026-11-22,
A3).

The text comes from the scan report and its text cache (`hukuk-ingest scan`), so a scanned file
has gone through the OCR of task 07 there. A file the scan left as `needs_ocr` is written as a
record with that status and no sections; a page without text inside the body lowers the band of
the section it belongs to. No text is made up.

Dates are read from the document. A genelge is taken to apply from its own date ("Sayı : ...
01/04/2020"). The file is the consolidated text: a section that carries an amendment note
("(Değişik, 17/09/2021 tarihli ve 2021/32 sayılı Genelge)") has its present wording from the
newest note on, and the time before that is a gap (the earlier wording is not on file).
"""

import json
import re
from pathlib import Path
from typing import Any

from hukuk_ingest.admin_acts import confidence
from hukuk_ingest.admin_acts.split import Section, Split, amendments, is_repealed, split_act

ACT_DIR = "Mevzuat/Genelge/"
# Written into every record; the loader keys its idempotency on it. Bump it when a change here
# or in split.py alters the sections.
PARSER_VERSION = "1"
# The genelges in scope, by the number in the file name ("2018_38 ...", "2020-08 ...").
IN_SCOPE = ("2018/38", "2020/8")
_FILE_REF_RE = re.compile(r"^(\d{4})[_-]0*(\d+)(?!\d)")
_ISSUER = "SOSYAL GÜVENLİK KURUMU"


def discover(scan_report: Path) -> list[dict[str, Any]]:
    """The scan rows of the genelges in scope (current files only, not `Eskiler/`), each with the
    `ref` its file name gives."""
    rows = []
    for line in scan_report.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        path = row["path"]
        if not path.startswith(ACT_DIR) or "/" in path[len(ACT_DIR) :]:
            continue
        if (m := _FILE_REF_RE.match(Path(path).name)) and (
            ref := f"{m.group(1)}/{m.group(2)}"
        ) in IN_SCOPE:
            rows.append({**row, "ref": ref})
    return sorted(rows, key=lambda r: r["path"])


def _section_record(
    section: Section, split: Split, latest: str | None, ocr: bool
) -> dict[str, Any]:
    notes, unread = amendments(section.text)
    warnings = list(section.warnings)
    if ocr:
        warnings.append("ocr_text")
    if unread:
        warnings.append("unparsed_amendment_note")
    issued = split.issue_date.isoformat() if split.issue_date else None
    valid_from = max((n["date"] for n in notes), default=issued)
    gaps = []
    if notes:
        warnings.append("amended_in_place")
        gaps.append({"from": issued, "to": valid_from, "reason": "amended_in_place"})
    if valid_from is None:
        warnings.append("issue_date_unknown")
    repealed = is_repealed(section)
    return {
        "section_no": section.section_no,
        "ordinal": section.ordinal,
        "heading": section.heading,
        "children": section.children,
        "pages": section.pages,
        "latest_snapshot_date": latest,
        "versions": [
            {
                "text": section.text,
                "heading": section.heading,
                "valid_from": valid_from,
                "valid_to": None,
                "change_kind": "repealed" if repealed else "amended" if notes else "original",
                "amendments": notes,
            }
        ],
        "gaps": gaps,
        "warnings": sorted(warnings),
        "confidence": confidence.band(warnings),
    }


def build_record(row: dict[str, Any], text: str | None) -> dict[str, Any]:
    """The record of one genelge: `text` None (the scan has no usable text) gives a record with
    the scan's status and no sections."""
    record: dict[str, Any] = {
        "ref": row["ref"],
        "parser_version": PARSER_VERSION,
        "status": row["status"],
        "file": {
            "path": row["path"],
            "sha256": row["sha256"],
            "size": row.get("size", 0),
            "detected_type": row.get("detected_type"),
        },
        "sections": [],
    }
    if text is None:
        return record
    split = split_act(text)
    if split.ref != row["ref"]:
        return {**record, "status": "ref_mismatch", "document_ref": split.ref}
    ocr = "ocr" in row.get("warnings", [])
    dates = [n["date"] for n in split.incorporated]
    dates += [n["date"] for s in split.sections for n in amendments(s.text)[0]]
    if split.issue_date:
        dates.append(split.issue_date.isoformat())
    latest = max(dates, default=None)
    return {
        **record,
        "issuer": "sgk" if _ISSUER in text else "other",
        "kind": "genelge",
        "subject": split.subject,
        "date": split.issue_date.isoformat() if split.issue_date else None,
        "latest_snapshot_date": latest,
        "incorporated": split.incorporated,
        "pages": split.pages,
        "ocr": ocr,
        "pages_without_text": split.pages_without_text,
        "annex_pages": split.annex_pages,
        "toc_entries": split.toc_entries,
        "toc_unmatched": split.toc_unmatched,
        "warnings": split.warnings,
        "sections": [_section_record(s, split, latest, ocr) for s in split.sections],
    }


def summarize(record: dict[str, Any]) -> str:
    """One report line per genelge: sections, bands and what needs OCR."""
    if not record["sections"]:
        return f"{record['ref']}: {record['status']}, no sections ({record['file']['path']})"
    bands = dict.fromkeys(("high", "medium", "low"), 0)
    for s in record["sections"]:
        bands[s["confidence"]] += 1
    return (
        f"{record['ref']}: {len(record['sections'])} sections, bands {bands}, "
        f"pages {record['pages']}, pages without text (needs_ocr) {record['pages_without_text']}, "
        f"annex pages not split {record['annex_pages']}, "
        f"toc entries {record['toc_entries']} (not found {len(record['toc_unmatched'])})"
    )


def run(scan_report: Path, text_cache: Path, out: Path) -> list[dict[str, Any]]:
    records = []
    for row in discover(scan_report):
        usable = row["status"] == "ok" and row.get("text_ref")
        text = (text_cache / row["text_ref"]).read_text(encoding="utf-8") if usable else None
        records.append(build_record(row, text))
    out.mkdir(parents=True, exist_ok=True)
    with (out / "admin-acts.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return records
