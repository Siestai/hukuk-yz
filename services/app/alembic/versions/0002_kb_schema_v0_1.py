"""KB schema v0.1 (docs/data-model.md §3, §5, §8, §10)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02

Hand-written. Constraint and index names follow the naming convention of
app.models.common.NAMING_CONVENTION so that `alembic check` sees no drift.
Statements are issued one per op.execute(): asyncpg cannot run several commands in one call.

Design choices that deviate from a literal reading of the task spec are marked "NOTE".
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

EXTENSIONS = ("vector", "unaccent", "pgcrypto", "btree_gist")

# Postgres enum name -> labels. tests/test_orm_consistency.py checks these against the ORM enums.
ENUMS: dict[str, tuple[str, ...]] = {
    # data-model.md §2 (A..H spelled out)
    "source_category": (
        "statute",
        "treaty",
        "decision",
        "admin_act",
        "collective_agreement",
        "case_document",
        "doctrine",
        "calc",
    ),
    # §3 source
    "source_rank": ("official_primary", "official_secondary", "editorial", "academic"),
    "license": ("public", "licensed", "internal_only", "unknown"),
    # §4 state machine
    "record_status": (
        "draft",
        "analyzed",
        "approved",
        "published",
        "superseded",
        "withdrawn",
        "failed",
        "rejected",
    ),
    # §3 ingest_job / review
    "ingest_kind": ("upload", "crawl", "bulk"),
    # NOTE: the doc gives no values for ingest_job.status; a job lifecycle is used here.
    "ingest_status": ("queued", "running", "completed", "failed"),
    "review_decision": ("approve", "edit", "reject"),
    # §5.2 decision
    "court": (
        "aym",
        "yargitay",
        "danistay",
        "bam",
        "bim",
        "ilk_derece",
        "aihm",
        "abad",
        "foreign",
    ),
    "court_level": (
        "aym",
        "ibk",
        "hgk_iddk",
        "daire",
        "bam_bim",
        "ilk_derece",
        "international",
    ),
    "jurisdiction": ("adli", "idari"),
    "text_completeness": ("full", "excerpt", "summary_only"),
    "verification": (
        "unverified",
        "verified_official",
        "verified_uyap",
        "mismatch",
        "not_in_source",
    ),
    # §5.1 statute (labels ASCII-folded: yönetmelik -> yonetmelik, tüzük -> tuzuk, ...)
    "change_kind": ("original", "amended", "repealed", "added"),
    "statute_kind": ("kanun", "khk", "yonetmelik", "tuzuk", "teblig"),
    # §5.3 admin_act ("..." in the doc -> "other")
    "admin_issuer": ("sgk", "csgb", "hazine", "other"),
    "admin_kind": ("genelge", "teblig", "genel_yazi", "gorus", "talimat"),
    # §8 chunk
    "chunk_kind": ("body", "editorial_summary"),
}

# Tables in dependency order; downgrade drops them in reverse.
TABLES = (
    "source",
    "ingest_job",
    "ingest_file",
    "extraction",
    "review",
    "statute",
    "statute_article",
    "statute_article_version",
    "decision",
    "admin_act",
    "admin_act_version",
    "treaty",
    "treaty_article_version",
    "collective_agreement",
    "ca_article_version",
    "doctrine",
    "calc_method",
    "calc_parameter_version",
    "chunk",
)

# Strict "<": daterange(valid_from, valid_to) is [from, to), so from = to is an empty range that
# bypasses the EXCLUDE constraint and is never returned by an as_of query.
# Must equal app.models.common.VALID_RANGE (checked in tests/test_orm_consistency.py).
VALID_RANGE = "valid_to IS NULL OR valid_from < valid_to"


def _enum(name: str) -> pg.ENUM:
    """Reference to an enum created in upgrade(); never auto-created by create_table."""
    return pg.ENUM(*ENUMS[name], name=name, create_type=False)


def _now() -> sa.DateTime:
    return sa.DateTime(timezone=True)


def _id() -> sa.Column:  # type: ignore[type-arg]
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _fk(table: str, ref: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [f"{ref}.id"], name=f"fk_{table}_{column}_{ref}")


def _provenance() -> list[sa.Column]:  # type: ignore[type-arg]
    """Embedded provenance of typed records (data-model.md §3 'provenance')."""
    return [
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_id", sa.Uuid(), nullable=True),
        sa.Column("review_id", sa.Uuid(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_by", sa.Text(), nullable=True),
    ]


def _provenance_fks(table: str) -> list[sa.ForeignKeyConstraint]:
    return [
        _fk(table, "source", "source_id"),
        _fk(table, "extraction", "extraction_id"),
        _fk(table, "review", "review_id"),
    ]


def _provenance_indexes(table: str) -> None:
    """btree indexes on the provenance FKs (review-screen lookups per source/extraction)."""
    for column in ("source_id", "extraction_id", "review_id"):
        op.create_index(f"ix_{table}_{column}", table, [column])


def _valid_range_check() -> sa.CheckConstraint:
    # The naming convention turns "valid_range" into ck_<table>_valid_range.
    return sa.CheckConstraint(VALID_RANGE, name="valid_range")


def _no_overlap(table: str, key: str) -> None:
    """Forbid overlapping live versions of the same key (task 02, scope item 9).

    daterange(valid_from, valid_to) is [from, to) and an open-ended range when valid_to is
    NULL. Superseded rows (superseded_at set) are history and may overlap.
    """
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT ex_{table}_no_overlap "
        f"EXCLUDE USING gist ({key} WITH =, daterange(valid_from, valid_to) WITH &&) "
        "WHERE (superseded_at IS NULL)"
    )


def upgrade() -> None:
    for extension in EXTENSIONS:
        # vector: pgvector (§8); unaccent: dictionary of turkish_unaccent; pgcrypto:
        # gen_random_uuid() on older servers; btree_gist: uuid/text equality inside the
        # EXCLUDE constraints.
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension}")

    # Unaccent-then-stem Turkish configuration (the plain 'turkish' one cannot be changed).
    # Chain order matters: unaccent is a filtering dictionary that passes its output to
    # turkish_stem. Used by both tsv triggers and by every tsquery site.
    op.execute("CREATE TEXT SEARCH CONFIGURATION turkish_unaccent (COPY = turkish)")
    op.execute(
        "ALTER TEXT SEARCH CONFIGURATION turkish_unaccent "
        "ALTER MAPPING FOR hword, hword_part, word WITH unaccent, turkish_stem"
    )

    for name, labels in ENUMS.items():
        pg.ENUM(*labels, name=name).create(op.get_bind(), checkfirst=False)

    # ---- §3 common tables -------------------------------------------------------------

    # source: parent identity of every record. org_id null = shared KB (§11 proposal);
    # the org table and its FK come with a later task.
    op.create_table(
        "source",
        _id(),
        sa.Column("category", _enum("source_category"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("official_ref", sa.Text(), nullable=True),
        sa.Column("source_rank", _enum("source_rank"), nullable=False),
        sa.Column("license", _enum("license"), server_default="unknown", nullable=False),
        sa.Column("origin_url", sa.Text(), nullable=True),
        sa.Column("status", _enum("record_status"), server_default="draft", nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source"),
    )
    # The review queue always filters by category, then status.
    op.create_index("ix_source_category_status", "source", ["category", "status"])

    # ingest_job (§3). created_by has no FK: there is no user table yet.
    op.create_table(
        "ingest_job",
        _id(),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("kind", _enum("ingest_kind"), nullable=False),
        sa.Column("status", _enum("ingest_status"), server_default="queued", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats", pg.JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ingest_job"),
    )

    # ingest_file (§3); sha256 index serves duplicate-upload detection.
    op.create_table(
        "ingest_file",
        _id(),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=True),
        sa.Column("detected_type", sa.Text(), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_ingest_file"),
        _fk("ingest_file", "ingest_job", "job_id"),
    )
    op.create_index("ix_ingest_file_sha256", "ingest_file", ["sha256"])
    op.create_index("ix_ingest_file_job_id", "ingest_file", ["job_id"])

    # extraction (§3): raw parser output, kept apart from approved typed rows.
    op.create_table(
        "extraction",
        _id(),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        # Lets the review queue find pending extractions of an 'analyzed' source before any
        # typed row exists (§4). Nullable: not every extraction is tied to a source yet.
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("parser_name", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column(
            "extracted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("fields", pg.JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("confidence", pg.JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("warnings", pg.JSONB(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("raw_text_ref", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_extraction"),
        _fk("extraction", "ingest_file", "file_id"),
        _fk("extraction", "source", "source_id"),
    )
    op.create_index("ix_extraction_file_id", "extraction", ["file_id"])
    op.create_index("ix_extraction_source_id", "extraction", ["source_id"])

    # review (§3): the human approval gate. reviewer_id has no FK yet (no user table).
    op.create_table(
        "review",
        _id(),
        sa.Column("extraction_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column("decision", _enum("review_decision"), nullable=False),
        sa.Column("edits", pg.JSONB(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_review"),
        _fk("review", "extraction", "extraction_id"),
    )
    op.create_index("ix_review_extraction_id", "review", ["extraction_id"])

    # ---- §5.1 mevzuat (A) -------------------------------------------------------------

    # statute. NOTE: number is text (yönetmelik numbers are not always integers).
    op.create_table(
        "statute",
        _id(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Text(), nullable=True),
        sa.Column("kind", _enum("statute_kind"), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=True),
        sa.Column("full_title", sa.Text(), nullable=False),
        sa.Column("rg_date", sa.Date(), nullable=True),
        sa.Column("rg_number", sa.Text(), nullable=True),
        sa.Column("repealed_at", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_statute"),
        _fk("statute", "source", "source_id"),
    )
    # One statute per (kind, number): a second row for the same law (e.g. from Eskiler/) would
    # make every /citation/resolve "ambiguous"; fail at load time instead.
    op.create_index(
        "uq_statute_kind_number",
        "statute",
        ["kind", "number"],
        unique=True,
        postgresql_where=sa.text("number IS NOT NULL"),
    )

    # statute_article: article_no is text ("18", "Ek 2", "Geçici 4").
    op.create_table(
        "statute_article",
        _id(),
        sa.Column("statute_id", sa.Uuid(), nullable=False),
        sa.Column("article_no", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_statute_article"),
        _fk("statute_article", "statute", "statute_id"),
        sa.UniqueConstraint(
            "statute_id", "article_no", name="uq_statute_article_statute_id_article_no"
        ),
    )

    # statute_article_version: the bitemporal core (§1 rule 2, §5.1).
    op.create_table(
        "statute_article_version",
        _id(),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("amending_ref", sa.Text(), nullable=True),
        sa.Column("change_kind", _enum("change_kind"), nullable=False),
        *_provenance(),
        sa.PrimaryKeyConstraint("id", name="pk_statute_article_version"),
        _fk("statute_article_version", "statute_article", "article_id"),
        *_provenance_fks("statute_article_version"),
        _valid_range_check(),
    )
    _no_overlap("statute_article_version", "article_id")
    _provenance_indexes("statute_article_version")
    # The gist EXCLUDE index is partial (superseded_at IS NULL): history needs its own index.
    op.create_index(
        "ix_statute_article_version_article_id", "statute_article_version", ["article_id"]
    )

    # ---- §5.2 yargı kararları (C) -----------------------------------------------------

    # decision. jurisdiction is nullable: AYM / AİHM / ABAD fit neither adli nor idari.
    # decision_kind and outcome stay free text: the doc lists open-ended values ("...").
    op.create_table(
        "decision",
        _id(),
        sa.Column("court", _enum("court"), nullable=False),
        sa.Column("court_level", _enum("court_level"), nullable=False),
        # NOT NULL DEFAULT '' (not NULL): Postgres unique indexes treat NULLs as distinct, so
        # chamber-less courts (HGK, İBK, AYM, İDDK) would never collide on the index below.
        # A plain column keeps the index a simple column index that `alembic check` compares
        # reliably; an expression index over coalesce(chamber, '') would not be.
        sa.Column("chamber", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("decision_kind", sa.Text(), nullable=True),
        sa.Column("esas_no", sa.Text(), nullable=True),
        sa.Column("karar_no", sa.Text(), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=True),
        sa.Column("event_date_hint", sa.Date(), nullable=True),
        sa.Column("jurisdiction", _enum("jurisdiction"), nullable=True),
        sa.Column("related_articles", pg.JSONB(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("keywords", pg.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("editorial_summary", sa.Text(), nullable=True),
        sa.Column("text_completeness", _enum("text_completeness"), nullable=False),
        sa.Column(
            "verification", _enum("verification"), server_default="unverified", nullable=False
        ),
        sa.Column("verification_source", sa.Text(), nullable=True),
        sa.Column("verification_ref", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("journal_issue", sa.Integer(), nullable=True),
        sa.Column("journal_page", sa.Integer(), nullable=True),
        sa.Column("tsv", pg.TSVECTOR(), nullable=True),
        *_provenance(),
        sa.PrimaryKeyConstraint("id", name="pk_decision"),
        *_provenance_fks("decision"),
    )
    # One live record per (court, chamber, esas_no, karar_no). esas_no / karar_no NULLs stay
    # distinct on purpose: ~4% of the archive lacks them and those must not collide.
    op.create_index(
        "uq_decision_court_chamber_esas_no_karar_no_live",
        "decision",
        ["court", "chamber", "esas_no", "karar_no"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL"),
    )
    op.create_index(
        "ix_decision_court_level_decision_date", "decision", ["court_level", "decision_date"]
    )
    op.create_index("ix_decision_tsv", "decision", ["tsv"], postgresql_using="gin")
    _provenance_indexes("decision")

    # NOTE (tsv design): a generated column cannot be used because to_tsvector with a config
    # that contains unaccent is not IMMUTABLE, and generated expressions must be. A trigger has
    # no such restriction and needs no wrapper function marked IMMUTABLE by hand (which would
    # silently break if the unaccent dictionary changed). The 'turkish_unaccent' configuration
    # (created above) unaccents tokens first and stems them afterwards, so the query side only
    # needs plainto_tsquery('turkish_unaccent', q).
    op.execute(
        """
        CREATE FUNCTION decision_tsv_refresh() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.tsv := to_tsvector('turkish_unaccent', coalesce(NEW.full_text, ''));
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER decision_tsv_refresh BEFORE INSERT OR UPDATE OF full_text ON decision "
        "FOR EACH ROW EXECUTE FUNCTION decision_tsv_refresh()"
    )

    # ---- §5.3 idari düzenleme (D) -----------------------------------------------------

    op.create_table(
        "admin_act",
        _id(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("issuer", _enum("admin_issuer"), nullable=False),
        sa.Column("kind", _enum("admin_kind"), nullable=False),
        sa.Column("number", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_admin_act"),
        _fk("admin_act", "source", "source_id"),
    )

    op.create_table(
        "admin_act_version",
        _id(),
        sa.Column("act_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("superseded_by_ref", sa.Text(), nullable=True),
        *_provenance(),
        sa.PrimaryKeyConstraint("id", name="pk_admin_act_version"),
        _fk("admin_act_version", "admin_act", "act_id"),
        *_provenance_fks("admin_act_version"),
        _valid_range_check(),
    )
    _no_overlap("admin_act_version", "act_id")
    _provenance_indexes("admin_act_version")
    op.create_index("ix_admin_act_version_act_id", "admin_act_version", ["act_id"])

    # ---- §5.4 B, E, G, H: schema only, no data in Phase 1 ------------------------------
    # case_document (F) is deliberately not created: outside the KB (§2), separate task.

    # B: treaty + treaty_article_version
    op.create_table(
        "treaty",
        _id(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_treaty"),
        _fk("treaty", "source", "source_id"),
    )
    op.create_table(
        "treaty_article_version",
        _id(),
        sa.Column("treaty_id", sa.Uuid(), nullable=False),
        sa.Column("article_no", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        *_provenance(),
        sa.PrimaryKeyConstraint("id", name="pk_treaty_article_version"),
        _fk("treaty_article_version", "treaty", "treaty_id"),
        *_provenance_fks("treaty_article_version"),
        _valid_range_check(),
    )
    _provenance_indexes("treaty_article_version")
    op.create_index("ix_treaty_article_version_treaty_id", "treaty_article_version", ["treaty_id"])

    # E: collective_agreement (TİS) + ca_article_version
    op.create_table(
        "collective_agreement",
        _id(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("parties", pg.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_collective_agreement"),
        _fk("collective_agreement", "source", "source_id"),
    )
    op.create_table(
        "ca_article_version",
        _id(),
        sa.Column("ca_id", sa.Uuid(), nullable=False),
        sa.Column("article_no", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        *_provenance(),
        sa.PrimaryKeyConstraint("id", name="pk_ca_article_version"),
        _fk("ca_article_version", "collective_agreement", "ca_id"),
        *_provenance_fks("ca_article_version"),
        _valid_range_check(),
    )
    _provenance_indexes("ca_article_version")
    op.create_index("ix_ca_article_version_ca_id", "ca_article_version", ["ca_id"])

    # G: doctrine (single table; carries provenance itself, license check via source)
    op.create_table(
        "doctrine",
        _id(),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("published_year", sa.Integer(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        *_provenance(),
        sa.PrimaryKeyConstraint("id", name="pk_doctrine"),
        *_provenance_fks("doctrine"),
    )
    _provenance_indexes("doctrine")

    # H: calc_method + calc_parameter_version
    op.create_table(
        "calc_method",
        _id(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_calc_method"),
        _fk("calc_method", "source", "source_id"),
        sa.UniqueConstraint("key", name="uq_calc_method_key"),
    )
    # NOTE: no FK to calc_method; parameters such as asgari_ucret_brut are global and the
    # no-overlap rule is per param name.
    op.create_table(
        "calc_parameter_version",
        _id(),
        sa.Column("param", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        *_provenance(),
        sa.PrimaryKeyConstraint("id", name="pk_calc_parameter_version"),
        *_provenance_fks("calc_parameter_version"),
        _valid_range_check(),
    )
    _no_overlap("calc_parameter_version", "param")
    _provenance_indexes("calc_parameter_version")

    # ---- §8 chunk ---------------------------------------------------------------------

    # Derived search index. parent_kind/parent_id are polymorphic, hence no FK.
    # The vector dimension (1024) lives here, not in settings; a model with another
    # dimension needs a new migration. No HNSW index yet: pointless without data.
    op.create_table(
        "chunk",
        _id(),
        sa.Column("category", _enum("source_category"), nullable=False),
        sa.Column("parent_kind", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=True),
        sa.Column("kind", _enum("chunk_kind"), nullable=False),
        sa.Column("license", _enum("license"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("header", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("tsv", pg.TSVECTOR(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_chunk"),
    )
    op.create_index("ix_chunk_parent_kind_parent_id", "chunk", ["parent_kind", "parent_id"])
    op.create_index("ix_chunk_category_kind_license", "chunk", ["category", "kind", "license"])
    # as_of filtering happens per chunk via version_id (§8).
    op.create_index("ix_chunk_version_id", "chunk", ["version_id"])
    op.create_index("ix_chunk_tsv", "chunk", ["tsv"], postgresql_using="gin")
    # Same trigger approach as decision.tsv; indexes the body text only, not the header.
    op.execute(
        """
        CREATE FUNCTION chunk_tsv_refresh() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.tsv := to_tsvector('turkish_unaccent', coalesce(NEW.text, ''));
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER chunk_tsv_refresh BEFORE INSERT OR UPDATE OF text ON chunk "
        "FOR EACH ROW EXECUTE FUNCTION chunk_tsv_refresh()"
    )


def downgrade() -> None:
    # Dropping a table drops its indexes, constraints and triggers.
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute("DROP FUNCTION chunk_tsv_refresh()")
    op.execute("DROP FUNCTION decision_tsv_refresh()")
    op.execute("DROP TEXT SEARCH CONFIGURATION turkish_unaccent")
    for name in reversed(ENUMS):
        op.execute(f"DROP TYPE {name}")
    # Extensions are left installed on purpose: they may be shared with other schemas and
    # dropping them needs superuser rights.
