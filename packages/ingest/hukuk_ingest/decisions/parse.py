"""One decision file: cached clean text in, `DecisionRecord` out."""

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from hukuk_ingest.decisions import qa
from hukuk_ingest.decisions.clean import clean_journal
from hukuk_ingest.decisions.fields import extract_fields
from hukuk_ingest.decisions.layout import detect_layout
from hukuk_ingest.pipeline import cache_base

# Bump when the parser's rules change the output.
PARSER_VERSION = "4"
ARCHIVE_DIR = "Yargi_Kararlari_Arsivi"
_ISSUE_RE = re.compile(rf"^{ARCHIVE_DIR}/(\d+)\.\s*Sayı")


@dataclass
class DecisionRecord:
    """`decision` row fields of docs/data-model.md §5.2 plus provenance. Beyond §5.2:
    `source_chamber`, `bam_region`, `layout`, `journal_year`, `journal_no`, `status`,
    `missing`, `warnings`, `sha256`, `source_path`, `parser_version`."""

    source_path: str
    sha256: str
    status: str = "ok"
    error: str | None = None
    journal_issue: int | None = None
    journal_year: int | None = None
    journal_no: int | None = None
    journal_page: int | None = None
    layout: str = ""
    parser_version: str = PARSER_VERSION
    court: str = ""
    court_level: str = ""
    chamber: str = ""
    source_chamber: str = ""
    bam_region: str = ""
    decision_kind: str = "karar"
    jurisdiction: str = ""
    esas_no: str = ""
    karar_no: str = ""
    decision_date: str = ""
    related_articles: list[dict[str, Any]] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    outcome: str = ""
    editorial_summary: str = ""
    full_text: str = ""
    text_completeness: str = "summary_only"
    verification: str = "unverified"  # official-source verification is task 05
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def issue_of(source_path: str) -> int | None:
    m = _ISSUE_RE.match(source_path)
    return int(m[1]) if m else None


def parse_text(text: str, source_path: str, sha256: str) -> DecisionRecord:
    journal = clean_journal(text)
    layout = detect_layout(journal)
    fields = extract_fields(journal, layout)
    record = DecisionRecord(
        source_path=source_path,
        sha256=sha256,
        journal_issue=issue_of(source_path),
        journal_year=journal.journal_year,
        journal_no=journal.journal_no,
        journal_page=journal.journal_page,
        layout=layout.value,
    )
    for name in (
        "court", "court_level", "chamber", "source_chamber", "bam_region", "decision_kind",
        "jurisdiction", "esas_no", "karar_no", "decision_date", "related_articles", "keywords",
        "outcome", "editorial_summary", "full_text", "text_completeness",
    ):  # fmt: skip
        setattr(record, name, getattr(fields, name))
    record.warnings = qa.record_warnings(fields.warnings, layout, record.to_dict())
    record.missing = qa.missing_fields(record.to_dict())
    return record


def parse_row(row: dict[str, Any], text_cache: Path) -> DecisionRecord:
    """Parse one `files.jsonl` row; a failure becomes an error record, never an exception."""
    path, sha = str(row["path"]), str(row["sha256"])
    try:
        text = cache_base(text_cache, sha).with_suffix(".clean.txt").read_text(encoding="utf-8")
        return parse_text(text, path, sha)
    except Exception as exc:  # one bad file must not stop the run
        return DecisionRecord(
            source_path=path,
            sha256=sha,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            journal_issue=issue_of(path),
        )
