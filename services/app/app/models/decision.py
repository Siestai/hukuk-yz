"""Category C, yargı kararları (data-model.md §5.2)."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import Index
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Text

from app.models.common import (
    Base,
    Court,
    CourtLevel,
    Jurisdiction,
    ProvenanceMixin,
    TextCompleteness,
    UuidPkMixin,
    Verification,
)


class Decision(UuidPkMixin, ProvenanceMixin, Base):
    __tablename__ = "decision"
    __table_args__ = (
        # One live record per (court, chamber, esas, karar). chamber is NOT NULL DEFAULT '' (not
        # nullable) because Postgres unique indexes treat NULLs as distinct: HGK / İBK / AYM /
        # İDDK decisions have no chamber and would otherwise never collide. A plain column keeps
        # the index a simple column index that `alembic check` compares reliably (an expression
        # index over coalesce(chamber, '') would not be). esas_no / karar_no stay nullable and
        # NULL-distinct on purpose: ~4% of archive decisions lack them and must not collide.
        Index(
            "uq_decision_court_chamber_esas_no_karar_no_live",
            "court",
            "chamber",
            "esas_no",
            "karar_no",
            unique=True,
            postgresql_where=sql_text("superseded_at IS NULL"),
        ),
        Index("ix_decision_court_level_decision_date", "court_level", "decision_date"),
        Index("ix_decision_tsv", "tsv", postgresql_using="gin"),
    )

    court: Mapped[Court] = mapped_column(Court.pg_type("court"))
    court_level: Mapped[CourtLevel] = mapped_column(CourtLevel.pg_type("court_level"))
    # '' = no chamber (HGK, İBK, AYM, ...); see the unique index above
    chamber: Mapped[str] = mapped_column(server_default=sql_text("''"))
    # AYM: norm_denetimi / iptal / bireysel_basvuru / red; others: karar / ibk (md. 17)
    decision_kind: Mapped[str | None]
    esas_no: Mapped[str | None]
    karar_no: Mapped[str | None]
    decision_date: Mapped[date | None]
    event_date_hint: Mapped[date | None]
    # null for courts outside the adli/idari split (AYM, AİHM, ABAD)
    jurisdiction: Mapped[Jurisdiction | None] = mapped_column(Jurisdiction.pg_type("jurisdiction"))
    related_articles: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=sql_text("'[]'")
    )
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql_text("'{}'"))
    outcome: Mapped[str | None]
    full_text: Mapped[str | None]
    # Çalışma ve Toplum ÖZETİ: editorial, never a citation source (md. 20, 26)
    editorial_summary: Mapped[str | None]
    text_completeness: Mapped[TextCompleteness] = mapped_column(
        TextCompleteness.pg_type("text_completeness")
    )
    verification: Mapped[Verification] = mapped_column(
        Verification.pg_type("verification"), server_default=sql_text("'unverified'")
    )
    verification_source: Mapped[str | None]
    verification_ref: Mapped[str | None]
    verified_at: Mapped[datetime | None]
    journal_issue: Mapped[int | None]
    journal_page: Mapped[int | None]
    # Maintained by trigger decision_tsv_refresh (see migration 0002), not by the app.
    tsv: Mapped[str | None] = mapped_column(TSVECTOR)
