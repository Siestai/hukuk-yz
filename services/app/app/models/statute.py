"""Category A, mevzuat (data-model.md §5.1)."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import (
    Base,
    BitemporalMixin,
    ChangeKind,
    ProvenanceMixin,
    StatuteKind,
    UuidPkMixin,
)


class Statute(UuidPkMixin, Base):
    __tablename__ = "statute"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source.id"))
    # text: yönetmelik numbers are not always plain integers
    number: Mapped[str | None]
    kind: Mapped[StatuteKind] = mapped_column(StatuteKind.pg_type("statute_kind"))
    short_name: Mapped[str | None]
    full_title: Mapped[str]
    rg_date: Mapped[date | None]
    rg_number: Mapped[str | None]
    repealed_at: Mapped[date | None]


class StatuteArticle(UuidPkMixin, Base):
    __tablename__ = "statute_article"
    __table_args__ = (UniqueConstraint("statute_id", "article_no"),)

    statute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("statute.id"))
    # "18", "Ek 2", "Geçici 4"
    article_no: Mapped[str]
    ordinal: Mapped[int]


class StatuteArticleVersion(UuidPkMixin, ProvenanceMixin, BitemporalMixin, Base):
    """Bitemporal core: no two live versions of one article may overlap in valid time."""

    __tablename__ = "statute_article_version"
    __table_args__ = (
        CheckConstraint("valid_to IS NULL OR valid_from <= valid_to", name="valid_range"),
        ExcludeConstraint(
            ("article_id", "="),
            (sql_text("daterange(valid_from, valid_to)"), "&&"),
            using="gist",
            where=sql_text("superseded_at IS NULL"),
            name="ex_statute_article_version_no_overlap",
        ),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("statute_article.id"))
    text: Mapped[str]
    heading: Mapped[str | None]
    amending_ref: Mapped[str | None]
    change_kind: Mapped[ChangeKind] = mapped_column(ChangeKind.pg_type("change_kind"))
