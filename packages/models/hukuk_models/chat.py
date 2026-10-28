"""The chat contract (task 15): what the web UI, the agent and the eval set exchange.

Drawn from the screens in `docs/design/chat-ui/` (alternative B): the understood case
("Anladığım olay"), the questions that complete it, the answer in three presentation modes, the
basis viewer, the feedback form. One `Answer` carries the data of all three modes; the mode only
changes what the UI shows, so switching it needs no new model call.

The texts in these models are Turkish and user-facing; the field names are English. Error codes
use `ErrorCode`, like the rest of the API.
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from hukuk_models import ErrorCode

DISCLAIMER = "Hukuki görüş değildir."

ChatMode = Literal["short", "detailed", "reasoned"]
# Source categories of the knowledge base (md. 28); the labels are those of `source_category`.
CitationCategory = Literal[
    "statute",
    "treaty",
    "decision",
    "admin_act",
    "collective_agreement",
    "case_document",
    "doctrine",
    "calc",
]
ReviewStatus = Literal["approved", "analyzed"]
Verification = Literal["verified", "unverified", "not_applicable"]
FactStatus = Literal["known", "unknown", "assumed_never"]
InputKind = Literal["choice", "date", "number", "text"]
AnswerStatus = Literal["definite", "conditional"]
HoldingResult = Literal["met", "not_met", "not_applicable", "unknown"]
FeedbackKind = Literal["wrong_source", "wrong_conclusion", "missing", "unclear", "other"]


class ChatModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CitationRef(ChatModel):
    """A source the answer rests on. Tapping it opens the full text of `source_id` with the part
    given by `quote` (and `char_start`..`char_end` in that text) highlighted."""

    # The record in the knowledge base (a UUID there; the fixtures use readable ids).
    source_id: str
    category: CitationCategory
    label: str  # as shown, e.g. "4857 sayılı İş Kanunu m.18/1"
    ref: str  # the künye the eval set matches, e.g. "4857 m.18/1"
    review_status: ReviewStatus
    # Official-source check; for decisions it is the check against karararama.yargitay.gov.tr.
    verification: Verification
    # Validity of the text in force (md. 4). `valid_to` None: still in force. `valid_from` None:
    # not recorded.
    valid_from: date | None = None
    valid_to: date | None = None
    # The part of the source the answer relies on; the offsets are into the source's full text.
    quote: str | None = None
    char_start: Annotated[int, Field(ge=0)] | None = None
    char_end: Annotated[int, Field(ge=0)] | None = None
    # "Cevaptaki kullanım": what the answer uses this source for.
    used_for: str | None = None

    @model_validator(mode="after")
    def _span(self) -> Self:
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start and char_end go together")
        if self.char_start is not None and self.char_end is not None:
            if self.char_end <= self.char_start:
                raise ValueError("char_end must be after char_start")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be before valid_from")
        return self


class Fact(ChatModel):
    key: str
    label: str
    # Known: what the user said. Unknown: None. Assumed never: the user said it does not apply
    # ("Yer altı işi değil", "Önceki çalışma yok"); never inferred from silence.
    value: str | None = None
    status: FactStatus

    @model_validator(mode="after")
    def _value_matches_status(self) -> Self:
        if (self.status == "unknown") != (self.value is None):
            raise ValueError("an unknown fact has no value, a known one has")
        return self


class CaseFacts(ChatModel):
    """ "Anladığım olay": the case as the agent understood it. The user can correct it."""

    title: str
    facts: list[Fact]
    # The date whose law applies (md. 4); None while unknown.
    event_date: date | None = None

    @model_validator(mode="after")
    def _unique_keys(self) -> Self:
        keys = [f.key for f in self.facts]
        if len(keys) != len(set(keys)):
            raise ValueError("fact keys must be unique")
        return self


class QuestionOption(ChatModel):
    value: str
    label: str


class QuestionInput(ChatModel):
    kind: InputKind
    options: list[QuestionOption] = []
    # "Bilmiyorum" exists on every question (md. 22).
    allow_unknown: Literal[True] = True

    @model_validator(mode="after")
    def _options_match_kind(self) -> Self:
        if (self.kind == "choice") != bool(self.options):
            raise ValueError("a choice has options, other inputs have none")
        return self


class ClarificationQuestion(ChatModel):
    id: str
    # The fact this question completes; the answer fills it in.
    fact_key: str
    text: str
    # "Neden soruyorum", with its sources.
    why: str
    source_refs: list[CitationRef] = []
    input: QuestionInput


class Clarification(ChatModel):
    """ "Tamamlanması gereken bilgiler" (md. 22). The user answers, marks "Bilmiyorum" or skips;
    skipping gives a conditional answer."""

    questions: list[ClarificationQuestion]
    # Position of the question on screen, 1-based; `total` is the number of questions.
    index: Annotated[int, Field(ge=1)]
    total: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def _counts(self) -> Self:
        if self.total != len(self.questions):
            raise ValueError("total must be the number of questions")
        if self.index > self.total:
            raise ValueError("index must not exceed total")
        ids = [q.id for q in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question ids must be unique")
        return self


class FactChip(ChatModel):
    """A fact the answer rests on, shown above it; tapping it edits the fact."""

    fact_key: str
    label: str
    status: FactStatus


class AnswerPoint(ChatModel):
    text: str
    citations: list[CitationRef]


class MissingInfo(ChatModel):
    """What a conditional answer depends on: if `condition`, then `result`."""

    fact_key: str | None = None
    condition: str
    result: str
    citations: list[CitationRef] = []


class HoldingRow(ChatModel):
    """One row of the hüküm haritası: a condition of the norm, the case's value for it, the
    outcome."""

    condition: str
    # The words of the norm the condition comes from; the agent checks them against the source.
    condition_quote: str
    citation: CitationRef
    fact_value: str | None = None
    result: HoldingResult


class HoldingMap(ChatModel):
    rows: Annotated[list[HoldingRow], Field(min_length=1)]
    reasoning_summary: str
    citations: list[CitationRef] = []


class Calculation(ChatModel):
    """v1 only says what a calculation needs ("brüt ücret gerekli"); the engine comes in v2."""

    title: str
    needs: Annotated[list[str], Field(min_length=1)]


class ReadSources(ChatModel):
    """ "Okunanlar", written by the harness from its trace, never by the model. The counts are
    those of the distinct sources in `items`."""

    statute_articles: Annotated[int, Field(ge=0)]
    decisions: Annotated[int, Field(ge=0)]
    admin_acts: Annotated[int, Field(ge=0)]
    items: list[CitationRef]

    @model_validator(mode="after")
    def _counts_match_items(self) -> Self:
        def distinct(category: str) -> int:
            return len({c.source_id for c in self.items if c.category == category})

        counts = (
            (self.statute_articles, distinct("statute")),
            (self.decisions, distinct("decision")),
            (self.admin_acts, distinct("admin_act")),
        )
        if any(stated != actual for stated, actual in counts):
            raise ValueError("counts must match the distinct sources in items")
        return self


class Answer(ChatModel):
    status: AnswerStatus
    # "Verdiğiniz bilgilere göre."
    status_note: str
    headline: str
    fact_chips: list[FactChip]
    points: Annotated[list[AnswerPoint], Field(min_length=1)]
    # Short mode shows the first `short_point_count` points, detailed mode all of them.
    short_point_count: Annotated[int, Field(ge=1)] = 3
    missing_info: list[MissingInfo] = []
    holding_map: HoldingMap
    calculations: list[Calculation] = []
    read_sources: ReadSources
    applied_law_date: date
    applied_law_text: str  # "03.10.2026 tarihinde yürürlükte olan metin"
    disclaimer: Literal["Hukuki görüş değildir."] = "Hukuki görüş değildir."

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.short_point_count > len(self.points):
            raise ValueError("short_point_count must not exceed the number of points")
        if self.status == "conditional" and not self.missing_info:
            raise ValueError("a conditional answer says what it depends on (missing_info)")
        if self.status == "definite":
            if self.missing_info:
                raise ValueError("a definite answer has no missing_info")
            if any(chip.status == "unknown" for chip in self.fact_chips):
                raise ValueError("a definite answer cannot rest on an unknown fact")
            if any(row.result == "unknown" for row in self.holding_map.rows):
                raise ValueError("a definite answer has no unknown row in its holding map")
        # md. 25: nothing is cited that was not read.
        read = {item.source_id for item in self.read_sources.items}
        cited = [c for point in self.points for c in point.citations]
        cited += [row.citation for row in self.holding_map.rows] + self.holding_map.citations
        cited += [c for info in self.missing_info for c in info.citations]
        if unread := {c.source_id for c in cited} - read:
            raise ValueError(f"cited but not read: {sorted(unread)}")
        if self.applied_law_date.strftime("%d.%m.%Y") not in self.applied_law_text:
            raise ValueError("applied_law_text must name applied_law_date")
        return self


# Stream events (SSE). `type` is the discriminator.


class StepEvent(ChatModel):
    """A live status line ("Kaynaklar okunuyor"); `node` is the name of the step."""

    type: Literal["step"] = "step"
    node: str
    label: str


class FactsEvent(ChatModel):
    type: Literal["facts"] = "facts"
    facts: CaseFacts


class ClarificationEvent(ChatModel):
    type: Literal["clarification"] = "clarification"
    clarification: Clarification


class AnswerEvent(ChatModel):
    type: Literal["answer"] = "answer"
    answer: Answer


class ErrorEvent(ChatModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    params: dict[str, str | int] = {}


class DoneEvent(ChatModel):
    """The last event. `turn_id` is the assistant turn the feedback goes to (None when the
    stream ended in an error)."""

    type: Literal["done"] = "done"
    turn_id: uuid.UUID | None = None
    trace_id: str | None = None


AnyChatEvent = StepEvent | FactsEvent | ClarificationEvent | AnswerEvent | ErrorEvent | DoneEvent


class ChatEvent(RootModel[Annotated[AnyChatEvent, Field(discriminator="type")]]):
    """One event of the `text/event-stream` of `POST /chat/conversations/{id}/messages`: the SSE
    `event:` line is its `type`, the `data:` line is its JSON."""


# Requests and records.


class ClarificationAnswer(ChatModel):
    question_id: str
    # The text of the answer: an option value, an ISO date, a number or free text. None with
    # `unknown` set ("Bilmiyorum").
    value: Annotated[str, Field(max_length=500)] | None = None
    unknown: bool = False

    @model_validator(mode="after")
    def _one_or_the_other(self) -> Self:
        if self.unknown == (self.value is not None):
            raise ValueError("an answer has a value or says unknown, not both and not neither")
        return self


class MessageRequest(ChatModel):
    """A question (`text`), the answers to the open questions, or the choice to skip them. The
    mode is only the presentation the user has open."""

    text: Annotated[str, Field(min_length=1, max_length=4000)] | None = None
    clarification_answers: Annotated[list[ClarificationAnswer], Field(min_length=1)] | None = None
    skip: bool = False
    mode: ChatMode = "short"

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        given = [self.text is not None, self.clarification_answers is not None, self.skip]
        if sum(given) != 1:
            raise ValueError("send a text, clarification answers or skip")
        return self


class Turn(ChatModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    created_at: datetime
    # User turns carry one of these three (what the user sent).
    text: str | None = None
    clarification_answers: list[ClarificationAnswer] | None = None
    skipped: bool = False
    # How many personal names were masked in `text` ("1 kişi adı gizlendi", KVKK).
    redacted_names: Annotated[int, Field(ge=0)] = 0
    # Assistant turns carry facts and either a clarification or an answer.
    facts: CaseFacts | None = None
    clarification: Clarification | None = None
    answer: Answer | None = None
    trace_id: str | None = None

    @model_validator(mode="after")
    def _role_fields(self) -> Self:
        sent = [self.text is not None, self.clarification_answers is not None, self.skipped]
        replied = [self.facts, self.clarification, self.answer]
        if self.role == "user":
            if sum(sent) != 1 or any(r is not None for r in replied):
                raise ValueError("a user turn is a text, answers or a skip")
        else:
            if any(sent) or self.redacted_names:
                raise ValueError("an assistant turn has no user input")
            if self.clarification is not None and self.answer is not None:
                raise ValueError("a turn asks or answers, not both")
            if all(r is None for r in replied):
                raise ValueError("an assistant turn has facts, a clarification or an answer")
        return self


class Conversation(ChatModel):
    id: uuid.UUID
    # Empty until the first question is understood; then the title of the case facts.
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(Conversation):
    turns: list[Turn]


class ConversationList(ChatModel):
    items: list[Conversation]


class FeedbackIn(ChatModel):
    rating: Literal["up", "down"] | None = None
    # The point the feedback is about (index into `Answer.points`); None: the whole answer.
    point_index: Annotated[int, Field(ge=0)] | None = None
    kind: FeedbackKind | None = None
    comment: Annotated[str, Field(max_length=4000)] = ""
    # What the right answer is, in the user's words (optional).
    correction: Annotated[str, Field(max_length=4000)] = ""

    @model_validator(mode="after")
    def _says_something(self) -> Self:
        if self.rating is None and self.kind is None and not self.comment and not self.correction:
            raise ValueError("feedback has a rating, a kind or a comment")
        return self


class Feedback(FeedbackIn):
    id: uuid.UUID
    turn_id: uuid.UUID
    created_at: datetime
