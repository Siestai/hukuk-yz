import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


class HealthResponse(BaseModel):
    status: str


class ErrorCode(StrEnum):
    """Every error the API returns, by a stable code; the UI translates it (docs/decisions.md,
    2026-10-03). The values are the wire format: add, never rename."""

    unauthorized = "unauthorized"
    forbidden = "forbidden"
    unsupported_media_type = "unsupported_media_type"
    validation_error = "validation_error"  # params: fields
    not_found = "not_found"
    method_not_allowed = "method_not_allowed"
    extraction_not_found = "extraction_not_found"
    # the source is no longer pending, or the extraction is not the newest of its source
    review_conflict = "review_conflict"
    decision_conflict = "decision_conflict"  # params: decision_id
    bulk_count_changed = "bulk_count_changed"  # params: total, expected
    bulk_band_not_allowed = "bulk_band_not_allowed"
    too_many_attempts = "too_many_attempts"  # params: retry_after (seconds)
    file_not_found = "file_not_found"
    file_not_previewable = "file_not_previewable"
    statute_not_found = "statute_not_found"  # params: number
    invalid_date = "invalid_date"  # params: field
    http_error = "http_error"  # a framework error with no code of its own (e.g. 400, 413)
    internal_error = "internal_error"


class ErrorBody(BaseModel):
    """`params` carries the values the translated message interpolates; no prose."""

    code: ErrorCode
    params: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    error: ErrorBody


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: Literal["admin", "reviewer"]


Band = Literal["high", "medium", "low"]
SourceStatus = Literal[
    "draft",
    "analyzed",
    "approved",
    "published",
    "superseded",
    "withdrawn",
    "failed",
    "rejected",
]


class ReviewFilters(BaseModel):
    """Queue filters shared by the list query string and the bulk-approve body (`band` apart)."""

    court: str | None = None
    reason: str | None = None
    journal_issue: int | None = None
    q: str | None = None


class RelatedArticle(BaseModel):
    """One entry of `related_articles`, as the parser writes it: `statute` is the law number
    (None when the label could not be mapped), `articles` the article numbers as printed
    ("18", "17/3"), `raw` the line it came from ("" for an entry added by hand)."""

    model_config = ConfigDict(extra="forbid")

    statute: int | None
    label: str
    articles: list[str]
    raw: str


NonEmptyText = Annotated[str, StringConstraints(min_length=1)]
IsoDate = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]


class DecisionEdits(BaseModel):
    """The `fields` a reviewer may correct, each optional but never null; `full_text` and
    `editorial_summary` are not among them. Enum values mirror the schema enums of the app
    (checked by its tests)."""

    model_config = ConfigDict(extra="forbid")

    court: (
        Literal[
            "aym", "yargitay", "danistay", "bam", "bim", "ilk_derece", "aihm", "abad", "foreign"
        ]
        | None
    ) = None
    court_level: (
        Literal["aym", "ibk", "hgk_iddk", "daire", "bam_bim", "ilk_derece", "international"] | None
    ) = None
    chamber: str | None = None
    source_chamber: str | None = None
    bam_region: str | None = None
    decision_kind: str | None = None
    esas_no: NonEmptyText | None = None
    karar_no: NonEmptyText | None = None
    decision_date: IsoDate | None = None
    jurisdiction: Literal["adli", "idari"] | None = None
    related_articles: list[RelatedArticle] | None = None
    keywords: list[str] | None = None
    outcome: (
        Literal["bozma", "onama", "duzelterek_onama", "kabul", "red", "ihlal", "ihlal_yok"] | None
    ) = None
    text_completeness: Literal["full", "excerpt", "summary_only"] | None = None

    @field_validator("decision_date")
    @classmethod
    def _real_date(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value)  # 2019-02-30 is not a date
        return value

    @model_validator(mode="after")
    def _no_nulls(self) -> Self:
        if nulls := [name for name in self.model_fields_set if getattr(self, name) is None]:
            raise ValueError(f"edits must not be null: {', '.join(sorted(nulls))}")
        return self


class ReviewActionRequest(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edits: DecisionEdits | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _required_parts(self) -> Self:
        if self.action == "edit" and not (self.edits and self.edits.model_fields_set):
            raise ValueError("edits are required for action 'edit'")
        if self.action != "edit" and self.edits is not None:
            raise ValueError(f"edits are only for action 'edit', not '{self.action}'")
        if self.action == "reject" and not (self.note and self.note.strip()):
            raise ValueError("note is required for action 'reject'")
        return self


class ReviewActionResponse(BaseModel):
    review_id: uuid.UUID
    decision_id: uuid.UUID | None
    source_status: SourceStatus


class BulkApproveRequest(BaseModel):
    # Only "high" is accepted; the endpoint answers any other band with `bulk_band_not_allowed`.
    band: Band
    filters: ReviewFilters = ReviewFilters()
    expected_count: int = Field(ge=0)
    limit: int = Field(default=100, ge=1, le=100)
    # sha256 of the last record of the previous call (its `next_cursor`); the run goes in sha256
    # order, so a record that stays in the queue (a conflict) is passed, not met again.
    # `expected_count` counts the matching records after it.
    cursor: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class BulkFailure(BaseModel):
    extraction_id: uuid.UUID
    reason: str


class BulkApproveResponse(BaseModel):
    published: int
    conflicts: list[uuid.UUID]
    failed: list[BulkFailure]
    remaining: int  # matching records after `next_cursor`
    next_cursor: str | None  # None when nothing remains


ListStatus = Literal["pending", "approved", "rejected", "all"]
ReviewDecisionName = Literal["approve", "edit", "reject"]


class ReviewListItem(BaseModel):
    """A queue row. `source_status` is the status of the decision's source. The last-review
    fields are None for a decision still waiting; `note` is the reason of a rejection and None
    for any other review."""

    extraction_id: uuid.UUID
    source_id: uuid.UUID
    source_status: SourceStatus
    title: str
    court: str
    chamber: str
    esas_no: str
    karar_no: str
    decision_date: str
    journal_issue: int | None
    band: Band
    score: int
    reasons: list[str]
    duplicate_group: dict[str, Any] | None
    reviewed_at: datetime | None = None
    reviewer_name: str | None = None  # None too when the reviewer has no user row
    review_decision: ReviewDecisionName | None = None
    note: str | None = None


class ReviewListResponse(BaseModel):
    total: int
    items: list[ReviewListItem]


class ReasonCount(BaseModel):
    reason: str
    count: int


class ReviewSummary(BaseModel):
    by_band: dict[Band, int]
    by_court: dict[str, int]
    top_reasons: list[ReasonCount]
    approved: int
    rejected: int


class Confidence(BaseModel):
    score: int
    band: Band
    reasons: list[str]


class DuplicateOut(BaseModel):
    extraction_id: uuid.UUID
    band: Band
    score: int
    text_length: int


class ReviewOut(BaseModel):
    id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewer_name: str | None  # None: the reviewer has no user row (reviews of the task-05 CLI)
    decision: ReviewDecisionName
    edits: dict[str, Any] | None
    note: str | None
    reviewed_at: datetime


class ReviewDetail(BaseModel):
    extraction_id: uuid.UUID
    source_id: uuid.UUID
    source_status: SourceStatus
    title: str
    fields: dict[str, Any]
    warnings: list[str]
    confidence: Confidence
    raw_text_ref: str | None
    pdf: Literal["available", "missing", "not_previewable"]
    duplicates: list[DuplicateOut]
    reviews: list[ReviewOut]


ArticleStatus = Literal["found", "gap", "not_in_force", "unknown_article"]


class ArticleVersionOut(BaseModel):
    text: str
    heading: str | None
    valid_from: date
    valid_to: date | None  # None: still in force
    change_kind: Literal["original", "amended", "repealed", "added"]
    amending_ref: str | None
    evidence: dict[str, Any]
    confidence: Band | None
    footnotes: list[Any]
    warnings: list[str]


Day = date  # `KnownAmendment.date` shadows the type inside its class body


class KnownAmendment(BaseModel):
    law: str
    date: Day
    kind: str
    scope: str


class ArticleGapOut(BaseModel):
    """An interval with no text on file. It names the amendments that are known to fall in it
    and never carries article text (md. 25: a gap cannot be cited)."""

    model_config = ConfigDict(populate_by_name=True)

    from_: date | None = Field(alias="from")  # None: from the statute's own entry into force
    to: date
    reason: str
    known_amendments: list[KnownAmendment]


class ArticleAsOf(BaseModel):
    """What a published article said on a date (task 11b). Only fields that apply to the status
    are present: `version` for found / repealed, `gap` for gap, `reason` for unknown_article
    (`not_published`) and for a repealed article (`repealed`)."""

    status: ArticleStatus
    reason: Literal["repealed", "not_published"] | None = None
    version: ArticleVersionOut | None = None
    gap: ArticleGapOut | None = None
    # `stale`: the date is after the newest snapshot, so the text may have been amended since.
    latest_snapshot_date: date | None = None
    stale: bool | None = None
    confidence: Band | None = None


# --- statute article review (task 11c-1) -------------------------------------------------------

StatuteArticleStatus = Literal["pending", "approved", "rejected", "superseded"]


class StatuteReviewListItem(BaseModel):
    """A queue row: the newest extraction of one article. `status` is `pending`, `approved`
    (live) or `rejected` here."""

    extraction_id: uuid.UUID
    source_id: uuid.UUID
    statute_number: str
    article_no: str
    ordinal: int
    heading: str | None
    band: Band
    reasons: list[str]
    version_count: int
    gap_count: int
    latest_snapshot_date: date
    status: StatuteArticleStatus


class StatuteReviewListResponse(BaseModel):
    total: int
    items: list[StatuteReviewListItem]


class StatuteSummaryRow(BaseModel):
    statute_number: str
    band: Band
    status: Literal["pending", "approved", "rejected"]
    count: int


class StatuteReviewSummary(BaseModel):
    """Only the combinations that occur have a row."""

    items: list[StatuteSummaryRow]


class StatuteBulkApproveRequest(BaseModel):
    """Same contract as `BulkApproveRequest`; the cursor is the id of the last article of the
    previous call (`next_cursor`), the run goes in id order."""

    band: Band  # only "high" is accepted, as for decisions
    statute: str | None = None
    expected_count: int = Field(ge=0)
    limit: int = Field(default=100, ge=1, le=100)
    cursor: uuid.UUID | None = None


class StatuteReviewActionRequest(BaseModel):
    """No edits: a timeline is not edited on screen, a wrong one is rejected."""

    action: Literal["approve", "reject"]
    note: str | None = None

    @model_validator(mode="after")
    def _note_for_reject(self) -> Self:
        if self.action == "reject" and not (self.note and self.note.strip()):
            raise ValueError("note is required for action 'reject'")
        return self


class StatuteReviewActionResponse(BaseModel):
    review_id: uuid.UUID
    article_id: uuid.UUID | None  # the published article; None for a rejection
    source_status: SourceStatus


class StatuteSnapshotOut(BaseModel):
    file_name: str
    date: Day | None


class TimelineVersion(ArticleVersionOut):
    kind: Literal["version"]


class TimelineGap(ArticleGapOut):
    """A gap entry has no text field."""

    kind: Literal["gap"]


TimelineEntry = Annotated[TimelineVersion | TimelineGap, Field(discriminator="kind")]


class StatuteReviewDetail(BaseModel):
    extraction_id: uuid.UUID
    source_id: uuid.UUID
    source_status: SourceStatus
    statute_number: str
    statute_title: str
    article_no: str
    ordinal: int
    heading: str | None
    status: StatuteArticleStatus
    band: Band
    reasons: list[str]
    warnings: list[str]
    timeline: list[TimelineEntry]
    snapshots: list[StatuteSnapshotOut]
    latest_snapshot_date: date
    reviews: list[ReviewOut]
    # The extraction whose versions are live for this article, when it is another one.
    live_extraction_id: uuid.UUID | None
