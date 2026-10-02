"""Categories B, E, G, H: schema only in Phase 1, no data yet (data-model.md §5.4)."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import (
    Base,
    BitemporalMixin,
    ProvenanceMixin,
    UuidPkMixin,
    no_overlap,
    valid_range_check,
)


class Treaty(UuidPkMixin, Base):
    """B: ILO conventions, AİHS, ..."""

    __tablename__ = "treaty"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source.id"))
    title: Mapped[str]
    short_name: Mapped[str | None]


class TreatyArticleVersion(UuidPkMixin, ProvenanceMixin, BitemporalMixin, Base):
    __tablename__ = "treaty_article_version"
    __table_args__ = (valid_range_check(),)

    treaty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("treaty.id"), index=True)
    article_no: Mapped[str]
    text: Mapped[str]


class CollectiveAgreement(UuidPkMixin, Base):
    """E: TİS and protocols."""

    __tablename__ = "collective_agreement"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source.id"))
    title: Mapped[str]
    sector: Mapped[str | None]
    parties: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class CaArticleVersion(UuidPkMixin, ProvenanceMixin, BitemporalMixin, Base):
    __tablename__ = "ca_article_version"
    __table_args__ = (valid_range_check(),)

    ca_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collective_agreement.id"), index=True)
    article_no: Mapped[str]
    text: Mapped[str]


class Doctrine(UuidPkMixin, ProvenanceMixin, Base):
    """G: articles, book chapters (license check required)."""

    __tablename__ = "doctrine"

    title: Mapped[str]
    author: Mapped[str | None]
    published_year: Mapped[int | None]
    full_text: Mapped[str | None]


class CalcMethod(UuidPkMixin, Base):
    """H: a calculation method / formula family."""

    __tablename__ = "calc_method"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source.id"))
    key: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    description: Mapped[str | None]


class CalcParameterVersion(UuidPkMixin, ProvenanceMixin, BitemporalMixin, Base):
    """H: dated parameter, e.g. asgari_ucret_brut; the engine fetches it by date."""

    __tablename__ = "calc_parameter_version"
    __table_args__ = (
        valid_range_check(),
        no_overlap("calc_parameter_version", "param"),
    )

    param: Mapped[str]
    value: Mapped[Decimal] = mapped_column(Numeric)
    unit: Mapped[str | None]
    source_ref: Mapped[str | None]
