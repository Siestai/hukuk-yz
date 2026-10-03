"""Declarative base, shared enums, mixins and the common tables (data-model.md §3).

Enum values are the Postgres enum labels (snake_case, ASCII). The migration repeats the
labels literally; tests/test_orm_consistency.py checks that the two stay in sync.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        str: Text,
        datetime: DateTime(timezone=True),
        list[str]: ARRAY(Text),
        dict[str, Any]: JSONB,
    }


class PgEnum(enum.Enum):
    """Enum whose members are named after, and valued as, their Postgres labels."""

    @classmethod
    def pg_type(cls, name: str) -> ENUM:
        return ENUM(
            cls,
            name=name,
            create_type=False,
            values_callable=lambda e: [m.value for m in e],
        )


class SourceCategory(PgEnum):
    """A..H of data-model.md §2."""

    statute = "statute"  # A
    treaty = "treaty"  # B
    decision = "decision"  # C
    admin_act = "admin_act"  # D
    collective_agreement = "collective_agreement"  # E
    case_document = "case_document"  # F (not a KB table; label reserved)
    doctrine = "doctrine"  # G
    calc = "calc"  # H


class SourceRank(PgEnum):
    official_primary = "official_primary"
    official_secondary = "official_secondary"
    editorial = "editorial"
    academic = "academic"


class License(PgEnum):
    public = "public"
    licensed = "licensed"
    internal_only = "internal_only"
    unknown = "unknown"


class RecordStatus(PgEnum):
    draft = "draft"
    analyzed = "analyzed"
    approved = "approved"
    published = "published"
    superseded = "superseded"
    withdrawn = "withdrawn"
    failed = "failed"
    rejected = "rejected"


class IngestKind(PgEnum):
    upload = "upload"
    crawl = "crawl"
    bulk = "bulk"


class IngestStatus(PgEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class ReviewDecision(PgEnum):
    approve = "approve"
    edit = "edit"
    reject = "reject"


class Court(PgEnum):
    aym = "aym"
    yargitay = "yargitay"
    danistay = "danistay"
    bam = "bam"
    bim = "bim"
    ilk_derece = "ilk_derece"
    aihm = "aihm"
    abad = "abad"
    foreign = "foreign"


class CourtLevel(PgEnum):
    aym = "aym"
    ibk = "ibk"
    hgk_iddk = "hgk_iddk"
    daire = "daire"
    bam_bim = "bam_bim"
    ilk_derece = "ilk_derece"
    international = "international"


class Jurisdiction(PgEnum):
    adli = "adli"
    idari = "idari"


class TextCompleteness(PgEnum):
    full = "full"
    excerpt = "excerpt"
    summary_only = "summary_only"


class Verification(PgEnum):
    unverified = "unverified"
    verified_official = "verified_official"
    verified_uyap = "verified_uyap"
    mismatch = "mismatch"
    not_in_source = "not_in_source"


class ChangeKind(PgEnum):
    original = "original"
    amended = "amended"
    repealed = "repealed"
    added = "added"


class StatuteKind(PgEnum):
    kanun = "kanun"
    khk = "khk"
    yonetmelik = "yonetmelik"
    tuzuk = "tuzuk"
    teblig = "teblig"


class AdminIssuer(PgEnum):
    sgk = "sgk"
    csgb = "csgb"
    hazine = "hazine"
    other = "other"


class AdminKind(PgEnum):
    genelge = "genelge"
    teblig = "teblig"
    genel_yazi = "genel_yazi"
    gorus = "gorus"
    talimat = "talimat"


class ChunkKind(PgEnum):
    body = "body"
    editorial_summary = "editorial_summary"


# Enum class -> Postgres type name; the migration creates exactly these.
ENUM_TYPES: dict[str, type[PgEnum]] = {
    "source_category": SourceCategory,
    "source_rank": SourceRank,
    "license": License,
    "record_status": RecordStatus,
    "ingest_kind": IngestKind,
    "ingest_status": IngestStatus,
    "review_decision": ReviewDecision,
    "court": Court,
    "court_level": CourtLevel,
    "jurisdiction": Jurisdiction,
    "text_completeness": TextCompleteness,
    "verification": Verification,
    "change_kind": ChangeKind,
    "statute_kind": StatuteKind,
    "admin_issuer": AdminIssuer,
    "admin_kind": AdminKind,
    "chunk_kind": ChunkKind,
}


class UuidPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )


class ProvenanceMixin:
    """Embedded provenance of every typed KB record (data-model.md §3, §1 rule 2-3)."""

    # Indexed: every "which typed row belongs to this source / extraction / review" lookup
    # on the review screen would otherwise be a seq scan.
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source.id"), index=True)
    extraction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("extraction.id"), index=True)
    review_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("review.id"), index=True)
    recorded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    superseded_at: Mapped[datetime | None]
    # No user table yet; free text so system actors ("bulk-import") fit too.
    recorded_by: Mapped[str | None]


class BitemporalMixin:
    """Legal validity axis; null valid_to = still in force (data-model.md §1 rule 2)."""

    valid_from: Mapped[date]
    valid_to: Mapped[date | None]


# Strict: daterange(valid_from, valid_to) is [from, to), so from = to would be an empty range
# that never overlaps anything (bypassing the EXCLUDE) and is never returned by an as_of query.
# The migration repeats this literal; tests/test_orm_consistency.py checks they match.
VALID_RANGE = "valid_to IS NULL OR valid_from < valid_to"


def valid_range_check() -> CheckConstraint:
    """CHECK for every *_version table; the naming convention yields ck_<table>_valid_range."""
    return CheckConstraint(VALID_RANGE, name="valid_range")


def no_overlap(table: str, key_column: str) -> ExcludeConstraint:
    """Forbid overlapping live versions of one key (named ex_<table>_no_overlap).

    Superseded rows (superseded_at set) are history and may overlap. Needs btree_gist.
    """
    return ExcludeConstraint(
        (key_column, "="),
        (text("daterange(valid_from, valid_to)"), "&&"),
        using="gist",
        where=text("superseded_at IS NULL"),
        name=f"ex_{table}_no_overlap",
    )


class Source(UuidPkMixin, Base):
    """data-model.md §3: parent identity of every source record."""

    __tablename__ = "source"
    # The review queue always filters by category, then status.
    __table_args__ = (Index("ix_source_category_status", "category", "status"),)

    category: Mapped[SourceCategory] = mapped_column(SourceCategory.pg_type("source_category"))
    title: Mapped[str]
    official_ref: Mapped[str | None]
    source_rank: Mapped[SourceRank] = mapped_column(SourceRank.pg_type("source_rank"))
    license: Mapped[License] = mapped_column(
        License.pg_type("license"), server_default=text("'unknown'")
    )
    origin_url: Mapped[str | None]
    status: Mapped[RecordStatus] = mapped_column(
        RecordStatus.pg_type("record_status"), server_default=text("'draft'")
    )
    # null = shared KB (data-model.md §11); the org table and FK arrive later.
    org_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class IngestJob(UuidPkMixin, Base):
    """data-model.md §3."""

    __tablename__ = "ingest_job"

    org_id: Mapped[uuid.UUID | None]
    created_by: Mapped[uuid.UUID | None]
    kind: Mapped[IngestKind] = mapped_column(IngestKind.pg_type("ingest_kind"))
    status: Mapped[IngestStatus] = mapped_column(
        IngestStatus.pg_type("ingest_status"), server_default=text("'queued'")
    )
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))


class IngestFile(UuidPkMixin, Base):
    """data-model.md §3. sha256 is indexed for duplicate-upload detection."""

    __tablename__ = "ingest_file"
    __table_args__ = (Index("ix_ingest_file_sha256", "sha256"),)

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingest_job.id"), index=True)
    path: Mapped[str]
    sha256: Mapped[str]
    mime: Mapped[str | None]
    detected_type: Mapped[str | None]
    size: Mapped[int] = mapped_column(BigInteger)
    error: Mapped[str | None]


class Extraction(UuidPkMixin, Base):
    """data-model.md §3: raw parser output; copied to typed tables only after review."""

    __tablename__ = "extraction"

    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingest_file.id"), index=True)
    # Lets the review queue find pending extractions of an 'analyzed' source before any typed
    # row exists (data-model.md §4). Nullable: not every extraction is tied to a source yet.
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source.id"), index=True)
    parser_name: Mapped[str]
    parser_version: Mapped[str]
    extracted_at: Mapped[datetime] = mapped_column(server_default=func.now())
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    confidence: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    warnings: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'"))
    raw_text_ref: Mapped[str | None]


class Review(UuidPkMixin, Base):
    """data-model.md §3: human approval gate (§1 rule 4)."""

    __tablename__ = "review"

    extraction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("extraction.id"), index=True)
    # The migration (0006) adds the FK NOT VALID: CLI reviews of task 05 may name a reviewer
    # that is no user; every new row must name one.
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    decision: Mapped[ReviewDecision] = mapped_column(ReviewDecision.pg_type("review_decision"))
    edits: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    note: Mapped[str | None]
    reviewed_at: Mapped[datetime] = mapped_column(server_default=func.now())
