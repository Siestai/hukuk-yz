"""The plan (no model): what the topic requires to be read in the branch of the facts, and the
date whose law applies."""

from datetime import date

from pydantic import BaseModel

from agent.facts import holds
from agent.topics import SourceRef, Topic
from hukuk_models.chat import CaseFacts


class Plan(BaseModel):
    # The date whose law applies (md. 4): the event date, or today when it is not known.
    as_of: date
    as_of_assumed: bool
    must_read: list[SourceRef]
    queries: list[str]


def make_plan(topic: Topic, question: str, facts: CaseFacts, today: date) -> Plan:
    return Plan(
        as_of=facts.event_date or today,
        as_of_assumed=facts.event_date is None,
        # A must-read out of the branch of the facts is not read, and so not unread either.
        must_read=[
            SourceRef(ref=r.ref, category=r.category)
            for r in topic.must_read
            if holds(topic, facts, r.when)
        ],
        queries=[question, *topic.queries],
    )
