"""Topic templates (`agent/topics/*.yaml`): what the agent may ask, and what it must read.

The questions of the clarification are chosen from the template of the topic, never made up;
the texts, the sources and the reading lists come from the topic cards (docs/tasks/17-agent-v1.md).
"""

from datetime import date
from functools import cache
from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.kunye import admin_act_section
from hukuk_models.chat import CitationCategory, InputKind

TOPICS_DIR = Path(__file__).parent / "topics"
GENERAL = "genel"
# In a condition, the state of a fact nothing is known of (or whose value is no option).
UNKNOWN = "unknown"


class TopicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRef(TopicModel):
    """A künye to read: "4857 m.18/1", "9. HD E.2016/28920 K.2017/17860"."""

    ref: str
    category: CitationCategory


class MustRead(SourceRef):
    """A source the topic requires to be read. With `when`, only in a branch: when every fact
    named is in one of the listed states, as in `TopicFact.asked_when`; out of it the source is
    not read and does not count as unread."""

    when: dict[str, list[str]] = {}


class Option(TopicModel):
    value: str
    label: str
    # Choosing it means the user said the fact does not apply ("Yer altı işi değil").
    assumed_never: bool = False


class Question(TopicModel):
    text: str
    why: str
    kind: InputKind
    options: list[Option] = []
    basis: list[SourceRef] = []

    @model_validator(mode="after")
    def _options_match_kind(self) -> Self:
        # A date may carry options: the answers that name no date ("Tutanak tutulmadı").
        if (self.kind == "choice" and not self.options) or (
            self.kind not in ("choice", "date") and self.options
        ):
            raise ValueError("a choice has options, a date may, other inputs have none")
        return self

    @model_validator(mode="after")
    def _basis_names_a_section(self) -> Self:
        # "Neden soruyorum" shows the text it rests on: a whole genelge is not such a text.
        for basis in self.basis:
            if basis.category != "admin_act":
                continue
            found = admin_act_section(basis.ref)
            if found is not None and found.section is None:
                raise ValueError(f"a question basis names a section of the genelge: {basis.ref}")
        return self


class TopicFact(TopicModel):
    key: str
    label: str
    # An unknown critical fact is asked, and while it is unknown the answer is conditional.
    critical: bool = False
    question: Question | None = None
    # The values the intake picks from for a fact that is never asked: the branch of the topic
    # the question is about ("Ücretin düşürülmesi").
    options: list[Option] = []
    # The fact is critical only in a branch: when every fact named here is in one of the listed
    # states, an option value or UNKNOWN. Pure code decides it; the model asks nothing else.
    asked_when: dict[str, list[str]] = {}
    # A date fact that by nature is often still ahead (an askerlik sevk date): a date after today
    # is a known date, not an unknown one. Off, the question carries today as its upper bound.
    allow_future: bool = False

    @model_validator(mode="after")
    def _critical_is_asked(self) -> Self:
        if self.critical and self.question is None:
            raise ValueError(f"critical fact {self.key} needs a question")
        if self.options and self.question is not None:
            raise ValueError(
                f"{self.key}: the options of an asked fact are the options of its question"
            )
        if self.asked_when and not self.critical:
            raise ValueError(f"{self.key}: asked_when is for a critical fact only")
        if self.allow_future and (self.question is None or self.question.kind != "date"):
            raise ValueError(f"{self.key}: allow_future is for a date fact only")
        return self

    @property
    def choices(self) -> list[Option]:
        return self.question.options if self.question is not None else self.options


class CalculationNeed(TopicModel):
    title: str
    needs: Annotated[list[str], Field(min_length=1)]


class Topic(TopicModel):
    id: str
    title: str
    # Tells the intake model what the topic covers.
    description: str
    facts: list[TopicFact]
    # The fact whose date is the event date (md. 4), if the topic has one.
    event_date_fact: str | None = None
    must_read: list[MustRead] = []
    queries: list[str] = []
    # The distinctions the cards warn about; they go into the prompts as rules.
    traps: list[str] = []
    calculations: list[CalculationNeed] = []

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        keys = [f.key for f in self.facts]
        if len(keys) != len(set(keys)):
            raise ValueError("fact keys must be unique")
        if self.event_date_fact is not None:
            fact = next((f for f in self.facts if f.key == self.event_date_fact), None)
            if fact is None or fact.question is None or fact.question.kind != "date":
                raise ValueError("event_date_fact must be a fact asked as a date")
        for fact in self.facts:
            if fact.key in fact.asked_when:
                raise ValueError(f"{fact.key}: a condition does not name the fact itself")
            self._check_condition(fact.key, "asked_when", fact.asked_when)
        for source in self.must_read:
            self._check_condition(source.ref, "when", source.when)
        return self

    def _check_condition(self, owner: str, name: str, condition: dict[str, list[str]]) -> None:
        for key, states in condition.items():
            branch = self.fact(key)
            if branch is None:
                raise ValueError(f"{owner}: {name} names no fact {key}")
            values = {o.value for o in branch.choices}
            if not values:
                raise ValueError(f"{owner}: {name} fact {key} has no options")
            if UNKNOWN in values:
                raise ValueError(f"{key}: {UNKNOWN} is no option value, it is the unknown state")
            if not states:
                raise ValueError(f"{owner}: {name} {key} lists no value")
            if wrong := sorted(set(states) - values - {UNKNOWN}):
                raise ValueError(f"{owner}: {wrong} not an option of {key}")
            # Without "unknown", the condition holds only once the branch is known: so the branch
            # fact must be asked whenever it is unknown, or the fact (the source) drops silently.
            always_asked = branch.critical and all(
                UNKNOWN in other for other in branch.asked_when.values()
            )
            if UNKNOWN not in states and not always_asked:
                raise ValueError(
                    f"{owner}: {key} is not always asked while unknown (never asked or "
                    f"conditional), so the condition lists {UNKNOWN}"
                )

    def fact(self, key: str) -> TopicFact | None:
        return next((f for f in self.facts if f.key == key), None)


@cache
def load_topics(directory: Path = TOPICS_DIR) -> dict[str, Topic]:
    topics = {}
    for path in sorted(directory.glob("*.yaml")):
        topic = Topic.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if topic.id != path.stem:
            raise ValueError(f"{path.name}: id must be {path.stem}")
        topics[topic.id] = topic
    if GENERAL not in topics:
        raise ValueError("the general template is missing")
    return topics


def get_topic(topic_id: str | None) -> Topic:
    """The template of `topic_id`; the general one for a topic without a template."""
    topics = load_topics()
    return topics.get(topic_id or GENERAL, topics[GENERAL])


def parse_date(value: str) -> date | None:
    """An ISO date, or dd.mm.yyyy as the user writes it."""
    try:
        if "." in value:
            day, month, year = value.strip().split(".")
            return date(int(year), int(month), int(day))
        return date.fromisoformat(value.strip())
    except ValueError:
        return None
