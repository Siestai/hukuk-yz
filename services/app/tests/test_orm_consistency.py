"""ORM / migration consistency checks that need no database."""

import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy import CheckConstraint

from app.models.common import ENUM_TYPES, VALID_RANGE, Base
from app.models.user import USER_ROLE_TYPE, UserRole

VERSIONS = Path(__file__).parents[1] / "alembic" / "versions"
MIGRATION = VERSIONS / "0002_kb_schema_v0_1.py"
USERS_MIGRATION = VERSIONS / "0005_users_and_sessions.py"
REVIEW_FK_MIGRATION = VERSIONS / "0006_review_reviewer_fk.py"
LOGIN_ATTEMPT_MIGRATION = VERSIONS / "0007_login_attempt.py"
EVIDENCE_MIGRATION = VERSIONS / "0008_statute_version_evidence.py"
REOPEN_MIGRATION = VERSIONS / "0009_review_decision_reopen.py"
FILE_STORE_MIGRATION = VERSIONS / "0010_ingest_file_store.py"
GORUS_MIGRATION = VERSIONS / "0011_document_type_gorus.py"
REVIEW_MIGRATION = VERSIONS / "0012_file_review.py"
# Tables created by later migrations (0004: decision_verification; 0005: users and sessions;
# 0007: login_attempt).
LATER_TABLES = {
    "decision_verification",
    "app_user",
    "user_session",
    "login_attempt",
    "file_deletion",
}


def _load_migration(path: Path = MIGRATION) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_enum_labels_match_migration() -> None:
    migration = _load_migration()
    orm = {name: tuple(m.value for m in cls) for name, cls in ENUM_TYPES.items()}
    # 0009 added the label 'reopen' to review_decision; 0010 created document_type and scan_status.
    # 0011 added the label 'gorus' to document_type (before 'diger' in the ORM, for reading).
    file_enums = _load_migration(FILE_STORE_MIGRATION).ENUMS
    document_type = tuple(_load_migration(GORUS_MIGRATION).OLD_LABELS)
    assert document_type == file_enums["document_type"]
    expected = {
        **migration.ENUMS,
        "review_decision": (*migration.ENUMS["review_decision"], "reopen"),
        **file_enums,
        "document_type": (*document_type[:-1], "gorus", "diger"),
        "review_status": _load_migration(REVIEW_MIGRATION).REVIEW_STATUS,
    }
    assert orm == expected
    assert _load_migration(REOPEN_MIGRATION).OLD_LABELS == migration.ENUMS["review_decision"]


def test_user_role_labels_match_migration() -> None:
    migration = _load_migration(USERS_MIGRATION)
    assert USER_ROLE_TYPE == "user_role"
    assert tuple(m.value for m in UserRole) == migration.USER_ROLES


def test_tables_match_migration() -> None:
    migration = _load_migration()
    assert set(Base.metadata.tables) == set(migration.TABLES) | LATER_TABLES
    assert len(migration.TABLES) == 19


def test_user_tables_are_in_the_users_migration() -> None:
    migration = USERS_MIGRATION.read_text()
    for name in ("app_user", "user_session", "uq_app_user_email", "uq_user_session_token_hash"):
        assert f'"{name}"' in migration, name
    orm = {i.name for t in Base.metadata.tables.values() for i in t.indexes}
    assert "ix_user_session_user_id" in orm
    assert '"ix_user_session_user_id"' in migration


def test_login_attempt_table_and_indexes_are_in_orm_and_migration() -> None:
    migration = LOGIN_ATTEMPT_MIGRATION.read_text()
    table = Base.metadata.tables["login_attempt"]
    assert {c.name for c in table.columns} == {"id", "email", "ip", "succeeded", "attempted_at"}
    assert '"login_attempt"' in migration
    indexes = {i.name: [c.name for c in i.columns] for i in table.indexes}
    assert indexes == {
        "ix_login_attempt_email_attempted_at": ["email", "attempted_at"],
        "ix_login_attempt_ip_attempted_at": ["ip", "attempted_at"],
        "ix_login_attempt_attempted_at": ["attempted_at"],
    }
    for name in indexes:
        assert f'"{name}"' in migration, name


def test_review_reviewer_fk_is_in_orm_and_migration() -> None:
    name = "fk_review_reviewer_id_app_user"
    review = Base.metadata.tables["review"]
    assert name in {c.name for c in review.foreign_key_constraints}
    migration = REVIEW_FK_MIGRATION.read_text()
    assert name in migration
    assert "NOT VALID" in migration


def test_case_document_is_not_a_kb_table() -> None:
    assert "case_document" not in Base.metadata.tables


def test_every_version_table_has_valid_range_check() -> None:
    for name, table in Base.metadata.tables.items():
        if name.endswith("_version"):
            checks = {c.name for c in table.constraints if c.name}
            assert f"ck_{name}_valid_range" in checks, name


def test_valid_range_is_strict_and_matches_migration() -> None:
    assert _load_migration().VALID_RANGE == VALID_RANGE
    assert "<=" not in VALID_RANGE


def test_every_version_table_has_the_same_check_text() -> None:
    for name, table in Base.metadata.tables.items():
        if name.endswith("_version"):
            checks = {
                c.name: str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
            }
            assert checks[f"ck_{name}_valid_range"] == VALID_RANGE, name


def test_no_overlap_on_the_three_exclusive_tables() -> None:
    expected = {"statute_article_version", "admin_act_version", "calc_parameter_version"}
    actual = {
        name
        for name, table in Base.metadata.tables.items()
        if f"ex_{name}_no_overlap" in {c.name for c in table.constraints}
    }
    assert actual == expected


def test_faz1_indexes_exist_in_orm_and_migration() -> None:
    migration = MIGRATION.read_text()
    literal = {
        "ix_decision_court_level_decision_date",
        "ix_chunk_version_id",
        "ix_statute_article_version_article_id",
        "ix_admin_act_version_act_id",
        "ix_ingest_file_job_id",
        "ix_extraction_file_id",
        "ix_extraction_source_id",
        "ix_review_extraction_id",
        "uq_statute_kind_number",
    }
    # created by the migration's _provenance_indexes() loop
    provenance = {
        f"ix_{table}_{column}"
        for table in ("decision", "statute_article_version", "calc_parameter_version")
        for column in ("source_id", "extraction_id", "review_id")
    }
    orm = {i.name for t in Base.metadata.tables.values() for i in t.indexes}
    assert (literal | provenance) <= orm
    assert all(f'"{name}"' in migration for name in literal)
    assert "uq_decision_court_bam_region_chamber_esas_no_karar_no_live" in orm
    assert "uq_decision_court_chamber_esas_no_karar_no_live" not in orm


def test_statute_version_evidence_columns_are_in_orm_and_migration() -> None:
    migration = _load_migration(EVIDENCE_MIGRATION)
    source = EVIDENCE_MIGRATION.read_text()
    table = Base.metadata.tables["statute_article_version"]
    new = {"evidence", "confidence", "warnings", "footnotes"}
    assert new <= {c.name for c in table.columns}
    assert all(f'"{name}"' in source for name in new)
    assert (migration.TABLE, migration.down_revision) == ("statute_article_version", "0007")
    checks = {c.name: str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}
    assert migration.CHECK in checks
    assert (
        checks[migration.CHECK]
        == "confidence IN (" + ", ".join(f"'{b}'" for b in migration.BANDS) + ")"
    )
    for name in ("evidence", "warnings", "footnotes"):
        assert not table.columns[name].nullable, name
    assert table.columns["confidence"].nullable


def test_ingest_file_store_columns_and_indexes_are_in_orm_and_migration() -> None:
    migration = _load_migration(FILE_STORE_MIGRATION)
    source = FILE_STORE_MIGRATION.read_text()
    table = Base.metadata.tables["ingest_file"]
    new = {
        "storage_key",
        "original_name",
        "doc_type",
        "doc_date",
        "official_ref",
        "origin_url",
        "note",
        "uploaded_by",
        "uploaded_at",
        "supersedes_id",
        "scan_status",
        "scan_result",
        "archived_at",
    }
    assert new <= {c.name for c in table.columns}
    assert all(f'"{name}"' in source for name in new)
    assert (migration.TABLE, migration.down_revision) == ("ingest_file", "0009")
    indexes = {i.name for i in table.indexes}
    for name in (
        "uq_ingest_file_sha256_stored",
        "uq_ingest_file_supersedes_id",
        "ix_ingest_file_scan_pending",
    ):
        assert name in indexes
        assert f'"{name}"' in source
    # Old rows count as scanned; the ORM and the migration agree on it.
    assert str(table.columns["scan_status"].server_default.arg) == "'done'"  # type: ignore[union-attr]
    assert not table.columns["scan_status"].nullable


def test_file_review_columns_indexes_and_deletion_table_are_in_orm_and_migration() -> None:
    migration = _load_migration(REVIEW_MIGRATION)
    source = REVIEW_MIGRATION.read_text()
    table = Base.metadata.tables["ingest_file"]
    new = {"review_status", "approved_by", "approved_at", "title", "suggestions", "matches"}
    assert new <= {c.name for c in table.columns}
    assert all(f'"{name}"' in source for name in new)
    assert (migration.TABLE, migration.down_revision) == ("ingest_file", "0011")
    assert "ix_ingest_file_review_pending" in {i.name for i in table.indexes}
    assert '"ix_ingest_file_review_pending"' in source
    # Old rows were set to approved by the migration; no default is left, so a forgotten status
    # fails instead of passing as approved.
    assert table.columns["review_status"].server_default is None
    assert not table.columns["review_status"].nullable
    deletion = Base.metadata.tables["file_deletion"]
    assert {c.name for c in deletion.columns} == {
        "id",
        "file_id",
        "sha256",
        "original_name",
        "doc_type",
        "review_status",
        "deleted_by",
        "deleted_at",
        "snapshot",
    }
    assert not deletion.c.file_id.foreign_keys
    assert 'create_table(\n        "file_deletion"' in source


def test_the_detector_knows_the_document_types_of_the_enum() -> None:
    from app.models.common import DocumentType
    from hukuk_ingest.classify.evidence import DOC_TYPES

    assert DOC_TYPES == tuple(m.value for m in DocumentType)
