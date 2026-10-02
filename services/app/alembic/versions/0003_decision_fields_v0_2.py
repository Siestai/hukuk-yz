"""Decision fields v0.2 (docs/data-model.md §5.2)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02

Hand-written. Brings `decision` in line with what the task 04 parser produces:
`source_chamber` (HGK `YYYY/D-N` keeps D here), `bam_region` (two BAM regions can each have a
"12. HD" with the same E/K, so the region joins the live-uniqueness index) and the
Uyuşmazlık Mahkemesi in the `court` / `court_level` enums.

Enums: `ALTER TYPE ... ADD VALUE` may run inside a transaction block on Postgres 12+ as long as
the new value is not used in the same transaction, so no autocommit block is needed. Postgres
cannot drop an enum value, so the downgrade recreates both types without `uyusmazlik`. It fails
loudly (cast error) when a row still uses the value, and the old unique index fails to rebuild
when two regions hold the same chamber and E/K: such data has to be resolved by hand first.
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Postgres enum name -> labels added by this revision. tests/test_orm_consistency.py checks
# these against the ORM enums.
NEW_ENUM_LABELS: dict[str, tuple[str, ...]] = {
    "court": ("uyusmazlik",),
    "court_level": ("uyusmazlik",),
}

OLD_INDEX = "uq_decision_court_chamber_esas_no_karar_no_live"
NEW_INDEX = "uq_decision_court_bam_region_chamber_esas_no_karar_no_live"
LIVE = "superseded_at IS NULL"


def upgrade() -> None:
    for name, labels in NEW_ENUM_LABELS.items():
        for label in labels:
            op.execute(f"ALTER TYPE {name} ADD VALUE '{label}'")

    # NOT NULL DEFAULT '' for the same reason as chamber (see 0002): NULLs never collide in a
    # unique index.
    op.add_column(
        "decision",
        sa.Column("source_chamber", sa.Text(), server_default=sa.text("''"), nullable=False),
    )
    op.add_column(
        "decision",
        sa.Column("bam_region", sa.Text(), server_default=sa.text("''"), nullable=False),
    )

    op.drop_index(OLD_INDEX, table_name="decision", postgresql_where=sa.text(LIVE))
    op.create_index(
        NEW_INDEX,
        "decision",
        ["court", "bam_region", "chamber", "esas_no", "karar_no"],
        unique=True,
        postgresql_where=sa.text(LIVE),
    )


def _recreate_enum(name: str, labels: tuple[str, ...]) -> None:
    """Replace enum `name` by a copy holding `labels` only; decision.`name` is the one column."""
    quoted = ", ".join(f"'{label}'" for label in labels)
    op.execute(f"ALTER TYPE {name} RENAME TO {name}_old")
    op.execute(f"CREATE TYPE {name} AS ENUM ({quoted})")
    op.execute(f"ALTER TABLE decision ALTER COLUMN {name} TYPE {name} USING {name}::text::{name}")
    op.execute(f"DROP TYPE {name}_old")


def downgrade() -> None:
    op.drop_index(NEW_INDEX, table_name="decision", postgresql_where=sa.text(LIVE))
    op.drop_column("decision", "bam_region")
    op.drop_column("decision", "source_chamber")
    op.create_index(
        OLD_INDEX,
        "decision",
        ["court", "chamber", "esas_no", "karar_no"],
        unique=True,
        postgresql_where=sa.text(LIVE),
    )

    _recreate_enum(
        "court",
        ("aym", "yargitay", "danistay", "bam", "bim", "ilk_derece", "aihm", "abad", "foreign"),
    )
    _recreate_enum(
        "court_level",
        ("aym", "ibk", "hgk_iddk", "daire", "bam_bim", "ilk_derece", "international"),
    )
