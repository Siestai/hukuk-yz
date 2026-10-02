"""ORM / migration consistency checks that need no database."""

import importlib.util
from pathlib import Path
from types import ModuleType

from app.models.common import ENUM_TYPES, Base

MIGRATION = Path(__file__).parents[1] / "alembic" / "versions" / "0002_kb_schema_v0_1.py"


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_0002", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_enum_labels_match_migration() -> None:
    migration = _load_migration()
    orm = {name: tuple(m.value for m in cls) for name, cls in ENUM_TYPES.items()}
    assert orm == migration.ENUMS


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
