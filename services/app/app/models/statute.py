"""Category A, mevzuat (data-model.md §5.1)."""

import uuid
from datetime import date

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import (
    Base,
    BitemporalMixin,
    ChangeKind,
    ProvenanceMixin,
    StatuteKind,
    UuidPkMixin,
    no_overlap,
    valid_range_check,
)


class Statute(UuidPkMixin, Base):
    __tablename__ = "statute"
    __table_args__ = (
        # A second row for the same law (e.g. from Eskiler/) would make every
        # /citation/resolve "ambiguous"; fail at load time instead.
        Index(
            "uq_statute_kind_number",
            "kind",
            "number",
            unique=True,
            postgresql_where=sql_text("number IS NOT NULL"),
        ),
    )

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
        valid_range_check(),
        no_overlap("statute_article_version", "article_id"),
    )

    # index: the partial gist EXCLUDE index cannot serve history / audit lookups
    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("statute_article.id"), index=True)
    text: Mapped[str]
    heading: Mapped[str | None]
    amending_ref: Mapped[str | None]
    change_kind: Mapped[ChangeKind] = mapped_column(ChangeKind.pg_type("change_kind"))
