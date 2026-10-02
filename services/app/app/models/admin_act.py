"""Category D, idari düzenleme (data-model.md §5.3)."""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import (
    AdminIssuer,
    AdminKind,
    Base,
    BitemporalMixin,
    ProvenanceMixin,
    UuidPkMixin,
    no_overlap,
    valid_range_check,
)


class AdminAct(UuidPkMixin, Base):
    __tablename__ = "admin_act"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source.id"))
    issuer: Mapped[AdminIssuer] = mapped_column(AdminIssuer.pg_type("admin_issuer"))
    kind: Mapped[AdminKind] = mapped_column(AdminKind.pg_type("admin_kind"))
    # "2018/38"
    number: Mapped[str | None]
    subject: Mapped[str | None]


class AdminActVersion(UuidPkMixin, ProvenanceMixin, BitemporalMixin, Base):
    __tablename__ = "admin_act_version"
    __table_args__ = (
        valid_range_check(),
        no_overlap("admin_act_version", "act_id"),
    )

    act_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_act.id"), index=True)
    text: Mapped[str]
    # Chain of "this genelge repeals that one" references
    superseded_by_ref: Mapped[str | None]
