"""Search index over typed records (data-model.md §8). Rebuildable, never a source of truth."""

import uuid
from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import Base, ChunkKind, CourtLevel, License, SourceCategory, UuidPkMixin

# Fixed here, not in settings: changing it needs a migration (task 02, scope item 8).
EMBEDDING_DIM = 1024


class Chunk(UuidPkMixin, Base):
    __tablename__ = "chunk"
    __table_args__ = (
        Index("ix_chunk_parent_kind_parent_id", "parent_kind", "parent_id"),
        Index("ix_chunk_category_kind_license", "category", "kind", "license"),
        # as_of filtering happens per chunk via version_id (data-model.md §8)
        Index("ix_chunk_version_id", "version_id"),
        Index("ix_chunk_tsv", "tsv", postgresql_using="gin"),
        Index("ix_chunk_source_id", "source_id"),
        # Added in task 14 (migration 0014): the search orders by cosine distance (`<=>`).
        Index(
            "ix_chunk_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )

    # The source every chunk belongs to; the review status of a result follows from parent_kind.
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source.id", ondelete="CASCADE"))
    category: Mapped[SourceCategory] = mapped_column(SourceCategory.pg_type("source_category"))
    # Polymorphic parent ("decision", "statute_article", "extraction" for a record not approved
    # yet, "admin_act", ...), hence no FK.
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
    # sha256 of header + text (the embedding input): an unchanged one is not embedded again.
    text_hash: Mapped[str]
    # Result line and filters, copied from the record when the chunk is built (task 14).
    title: Mapped[str]
    ref: Mapped[str | None]
    court_level: Mapped[CourtLevel | None] = mapped_column(CourtLevel.pg_type("court_level"))
    doc_date: Mapped[date | None]
    valid_from: Mapped[date | None]
    valid_to: Mapped[date | None]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None]
    # Maintained by trigger chunk_tsv_refresh (see migration 0002).
    tsv: Mapped[str | None] = mapped_column(TSVECTOR)
