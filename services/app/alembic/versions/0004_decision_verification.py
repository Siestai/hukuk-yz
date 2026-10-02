"""decision_verification (docs/data-model.md §5.2, task 06)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02

Hand-written. Adds the table of official-source checks. `decision.verification*` already exist
(0002); they summarize the latest non-error row of this table.

`outcome` is text with a CHECK rather than a Postgres enum: it adds `error` to the labels of the
`verification` enum, and a CHECK is cheaper to extend. Additive; the downgrade drops the table.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

OUTCOMES = ("verified_official", "verified_uyap", "mismatch", "not_in_source", "error")


def upgrade() -> None:
    op.create_table(
        "decision_verification",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("official_ref", sa.Text(), nullable=True),
        sa.Column("official_url", sa.Text(), nullable=True),
        sa.Column("matched", pg.JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("official_text_sha256", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_decision_verification"),
        sa.ForeignKeyConstraint(
            ["decision_id"], ["decision.id"], name="fk_decision_verification_decision_id_decision"
        ),
        sa.CheckConstraint(
            "outcome IN (" + ", ".join(f"'{o}'" for o in OUTCOMES) + ")",
            name="ck_decision_verification_outcome",
        ),
    )
    op.create_index(
        "ix_decision_verification_decision_id_attempted_at",
        "decision_verification",
        ["decision_id", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_table("decision_verification")
