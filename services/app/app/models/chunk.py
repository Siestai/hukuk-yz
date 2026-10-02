"""Search index over typed records (data-model.md §8). Rebuildable, never a source of truth."""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, ChunkKind, License, SourceCategory, UuidPkMixin

# Fixed here, not in settings: changing it needs a migration (task 02, scope item 8).
EMBEDDING_DIM = 1024


class Chunk(UuidPkMixin, Base):
    __tablename__ = "chunk"
    __table_args__ = (
        Index("ix_chunk_parent_kind_parent_id", "parent_kind", "parent_id"),
        Index("ix_chunk_category_kind_license", "category", "kind", "license"),
        Index("ix_chunk_tsv", "tsv", postgresql_using="gin"),
        # No HNSW index yet: pointless without data (decided in task 02).
    )

    category: Mapped[SourceCategory] = mapped_column(SourceCategory.pg_type("source_category"))
    # Polymorphic parent ("decision", "statute_article", "admin_act", ...), hence no FK.
    parent_kind: Mapped[str]
    parent_id: Mapped[uuid.UUID]
    # The *_version row for versioned parents, so as_of filters work per chunk.
    version_id: Mapped[uuid.UUID | None]
    kind: Mapped[ChunkKind] = mapped_column(ChunkKind.pg_type("chunk_kind"))
    # Copied from the parent; internal_only text never reaches users or the LLM.
    license: Mapped[License] = mapped_column(License.pg_type("license"))
    ordinal: Mapped[int]
    char_start: Mapped[int]
    char_end: Mapped[int]
    # Citation header fed to the embedding, never displayed
    header: Mapped[str | None]
    text: Mapped[str]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None]
    # Maintained by trigger chunk_tsv_refresh (see migration 0002).
    tsv: Mapped[str | None] = mapped_column(TSVECTOR)
