"""What the models are asked to return. Narrow and typed: a model picks facts, rows, sources and
words; everything else of an `Answer` (read sources, citations, chips, dates, disclaimer) is
written by code from these."""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from hukuk_models.chat import AnswerStatus, FactStatus, HoldingResult


class LlmModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntakeFact(LlmModel):
    key: str
    # What the user said, in their words; None when the question does not say.
    value: str | None = None
    # `assumed_never` only when the user says the fact does not apply; never from silence.
    status: FactStatus


class IntakeOutput(LlmModel):
    topic: str
    title: str
    event_date: date | None = None
    facts: list[IntakeFact]


class RowDraft(LlmModel):
    source_id: str
    # The paragraph the condition is in ("1" for m.18/1); None for the whole source.
    sub: Annotated[str, Field(pattern=r"^[\w\- ]{1,20}$")] | None = None
    condition: str
    # The words of the source the condition comes from, copied exactly.
    condition_quote: str
    fact_value: str | None = None
    result: HoldingResult
    # All facts that can reverse this row, including exceptions and aggregation inputs.
    depends_on_facts: list[str] = []


class HoldingDraft(LlmModel):
    rows: list[RowDraft]


class CitationPick(LlmModel):
    source_id: str
    sub: Annotated[str, Field(pattern=r"^[\w\- ]{1,20}$")] | None = None
    # Exact words of the source; the gate drops a citation whose quote is not in the source.
    quote: str | None = None
    used_for: str | None = None


class PointDraft(LlmModel):
    text: str
    citations: list[CitationPick]


class MissingDraft(LlmModel):
    fact_key: str | None = None
    condition: str
    result: str
    citations: list[CitationPick] = []


class DraftOutput(LlmModel):
    status: AnswerStatus
    headline: str
    points: Annotated[list[PointDraft], Field(min_length=1)]
    missing_info: list[MissingDraft] = []
    reasoning_summary: str
