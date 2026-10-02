"""ORM / migration consistency checks that need no database."""

import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy import CheckConstraint

from app.models.common import ENUM_TYPES, VALID_RANGE, Base

VERSIONS = Path(__file__).parents[1] / "alembic" / "versions"
MIGRATION = VERSIONS / "0002_kb_schema_v0_1.py"
MIGRATION_V0_2 = VERSIONS / "0003_decision_fields_v0_2.py"


def _load_migration(path: Path = MIGRATION) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_enum_labels_match_migration() -> None:
    migration = _load_migration()
    added = _load_migration(MIGRATION_V0_2).NEW_ENUM_LABELS
    expected = {name: (*labels, *added.get(name, ())) for name, labels in migration.ENUMS.items()}
    orm = {name: tuple(m.value for m in cls) for name, cls in ENUM_TYPES.items()}
    assert orm == expected


def test_tables_match_migration() -> None:
    migration = _load_migration()
    assert set(Base.metadata.tables) == set(migration.TABLES)
    assert len(migration.TABLES) == 19


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
