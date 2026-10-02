"""Category D, idari düzenleme (data-model.md §5.3)."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.common import (
    AdminIssuer,
    AdminKind,
    Base,
    BitemporalMixin,
    ProvenanceMixin,
    UuidPkMixin,
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
        CheckConstraint("valid_to IS NULL OR valid_from <= valid_to", name="valid_range"),
        ExcludeConstraint(
            ("act_id", "="),
            (sql_text("daterange(valid_from, valid_to)"), "&&"),
            using="gist",
            where=sql_text("superseded_at IS NULL"),
            name="ex_admin_act_version_no_overlap",
        ),
    )

    act_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_act.id"))
    text: Mapped[str]
    # Chain of "this genelge repeals that one" references
    superseded_by_ref: Mapped[str | None]
