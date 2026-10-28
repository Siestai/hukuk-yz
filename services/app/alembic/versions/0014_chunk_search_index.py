"""chunk: source link, content hash, filter columns and the HNSW index (task 14)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-27

Hand-written (docs/tasks/14-kb-search.md). The search reads `chunk` alone, so a chunk now carries
what the filters and the result need: `source_id` (every chunk is bound to its source),
`text_hash` (a chunk whose embedding input is unchanged is not embedded again), `title` and `ref`
(the citation line of the result), `court_level` and `doc_date` (decisions), `valid_from` /
`valid_to` (statute article versions; the `as_of` filter). The review status of a result is not
stored: it follows from `parent_kind` (`decision` / `statute_article` approved, `extraction`
analyzed). The HNSW index (cosine, as the search orders by `<=>`) is the one task 02 left out
because there was no data.

`chunk` is a rebuildable index, empty on the live database, so the upgrade clears it before it
adds the NOT NULL columns. The downgrade drops the columns and the index.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

NEW_COLUMNS = (
    "source_id",
    "text_hash",
    "title",
    "ref",
    "court_level",
    "doc_date",
    "valid_from",
    "valid_to",
)


def upgrade() -> None:
    # An index, never a source of truth (data-model.md §8): the NOT NULL columns need it empty.
    op.execute("DELETE FROM chunk")
    op.add_column(
        "chunk",
        sa.Column(
            "source_id", sa.Uuid(), sa.ForeignKey("source.id", ondelete="CASCADE"), nullable=False
        ),
    )
    op.add_column("chunk", sa.Column("text_hash", sa.Text(), nullable=False))
    op.add_column("chunk", sa.Column("title", sa.Text(), nullable=False))
    op.add_column("chunk", sa.Column("ref", sa.Text(), nullable=True))
    op.add_column(
        "chunk",
        sa.Column(
            "court_level",
            pg.ENUM(name="court_level", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("chunk", sa.Column("doc_date", sa.Date(), nullable=True))
    op.add_column("chunk", sa.Column("valid_from", sa.Date(), nullable=True))
    op.add_column("chunk", sa.Column("valid_to", sa.Date(), nullable=True))
    op.create_index("ix_chunk_source_id", "chunk", ["source_id"])
    # Alembic cannot express the operator class of an index: raw SQL. m / ef_construction are
    # pgvector's defaults, named so a later change is a visible edit.
    op.execute(
        "CREATE INDEX ix_chunk_embedding ON chunk USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_index("ix_chunk_embedding", table_name="chunk")
    op.drop_index("ix_chunk_source_id", table_name="chunk")
    for name in reversed(NEW_COLUMNS):
        op.drop_column("chunk", name)
