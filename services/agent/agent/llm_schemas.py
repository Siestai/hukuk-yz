"""What the models are asked to return. Narrow and typed: a model picks facts, rows, sources and
words; everything else of an `Answer` (read sources, citations, chips, dates, disclaimer) is
written by code from these."""

from datetime import date
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, create_model, model_validator

from agent.topics import Topic
from hukuk_models.chat import AnswerStatus, CaseFacts, FactStatus, HoldingResult


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


def draft_output_type(
    topic: Topic, facts: CaseFacts, *, original: DraftOutput | None = None
) -> type[DraftOutput]:
    """Request-local key vocabulary and coverage; rewrite may change generated words only.

    Critical coverage is visible in the generation schema, not a claim of source support.
    The internal/public draft still serializes missing_info as an array.
    No shared model or schema is mutated.
    """
    from agent.facts import critical_unknown

    keys = tuple(f.key for f in topic.facts)
    key_type = (
        Annotated[Literal[keys], Field(json_schema_extra={"enum": list(keys)})] | None
        if keys
        else type(None)
    )
    missing_type = create_model(
        "RequestMissingDraft", __base__=MissingDraft, fact_key=(key_type, None)
    )
    required = frozenset(critical_unknown(topic, facts))
    frozen = _rewrite_structure(original) if original is not None else None

    class RequestDraftOutput(DraftOutput):
        @model_validator(mode="after")
        def request_contract(self) -> Self:
            represented = {m.fact_key for m in self.missing_info}
            if uncovered := required - represented:
                raise ValueError(f"Missing critical unknown facts: {sorted(uncovered)}")
            if frozen is not None and _rewrite_structure(self) != frozen:
                raise ValueError("Rewrite changed identifiers, citations or structure")
            return self

    missing_annotation: Any = list[missing_type]
    missing_default: Any = []
    if required:
        # Each required property carries the actual generated entry, never a coverage flag.
        # Keep the enum on additional entries; no null/invented key can replace a critical entry.
        critical_types = {
            key: create_model(
                f"CriticalMissing_{key}",
                __base__=MissingDraft,
                fact_key=(Annotated[Literal[key], Field(json_schema_extra={"enum": [key]})], ...),
            )
            for key in critical_unknown(topic, facts)
        }
        critical_fields: dict[str, Any] = {
            key: (entry, ...) for key, entry in critical_types.items()
        }
        critical_type = create_model(
            "CriticalMissingInfo",
            __base__=LlmModel,
            **critical_fields,
        )
        wire_type = create_model(
            "MissingInfoCoverage",
            __base__=LlmModel,
            critical=(critical_type, ...),
            additional=(list[missing_type], []),
        )

        def from_wire(value: Any) -> Any:
            # Arrays remain valid internal input, with the same coverage validator below.
            # The provider is offered only the keyed object schema.
            if not isinstance(value, dict):
                return value
            wire = wire_type.model_validate(value).model_dump()
            entries = wire["critical"]
            additional = wire["additional"]
            if original is None:
                return [*entries.values(), *additional]
            # A rewrite retains the original array order, including nulls and duplicates.
            ordered = []
            for entry in original.missing_info:
                if entry.fact_key in entries:
                    ordered.append(entries.pop(entry.fact_key))
                elif additional:
                    ordered.append(additional.pop(0))
            return [*ordered, *entries.values(), *additional]

        missing_annotation = Annotated[
            list[missing_type], BeforeValidator(from_wire, json_schema_input_type=wire_type)
        ]
        missing_default = ...

    return create_model(
        "RequestDraftOutput",
        __base__=RequestDraftOutput,
        missing_info=(missing_annotation, missing_default),
    )


def _rewrite_structure(draft: DraftOutput) -> dict[str, Any]:
    data = draft.model_dump(mode="json")
    for field in ("headline", "reasoning_summary"):
        data.pop(field)
    for point in data["points"]:
        point.pop("text")
    for missing in data["missing_info"]:
        missing.pop("condition")
        missing.pop("result")
    # used_for is generated language; all other citation fields are immutable.
    for item in [*data["points"], *data["missing_info"]]:
        for pick in item["citations"]:
            pick.pop("used_for")
    return data
