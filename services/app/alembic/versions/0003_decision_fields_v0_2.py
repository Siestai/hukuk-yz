"""Decision fields v0.2 (docs/data-model.md §5.2)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02

Hand-written. Brings `decision` in line with what the task 04 parser produces:
`source_chamber` (HGK `YYYY/D-N` keeps D here) and `bam_region` (two BAM regions can each have a
"12. HD" with the same E/K, so the region joins the live-uniqueness index).

The downgrade drops both columns and restores the 0002 index. That index fails to build when two
regions hold the same chamber and E/K; such data has to be resolved by hand first.
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

OLD_INDEX = "uq_decision_court_chamber_esas_no_karar_no_live"
NEW_INDEX = "uq_decision_court_bam_region_chamber_esas_no_karar_no_live"
LIVE = "superseded_at IS NULL"


def upgrade() -> None:
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

    op.drop_index(OLD_INDEX, table_name="decision")
    op.create_index(
        NEW_INDEX,
        "decision",
        ["court", "bam_region", "chamber", "esas_no", "karar_no"],
        unique=True,
        postgresql_where=sa.text(LIVE),
    )


def downgrade() -> None:
    op.drop_index(NEW_INDEX, table_name="decision")
    op.drop_column("decision", "bam_region")
    op.drop_column("decision", "source_chamber")
    op.create_index(
        OLD_INDEX,
        "decision",
        ["court", "chamber", "esas_no", "karar_no"],
        unique=True,
        postgresql_where=sa.text(LIVE),
    )
