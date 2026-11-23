"""The honest "kaynak yetersiz" content (md. 25; task 19, B4). When no answer passes the gate, the
user still learns which topic the question was taken as, which of its must-read sources could
not be read and why, what they told, and what would make the question answerable. Everything
comes from the trace and the case facts; the model writes none of it."""

from collections.abc import Mapping, Sequence

from agent.topics import Topic
from hukuk_models.chat import CaseFacts, MissingSource, SourceGap


def source_gap(topic: Topic, facts: CaseFacts, missing: Sequence[Mapping[str, str]]) -> SourceGap:
    """`missing`: the `missing_source` entries of the retrieve step (`ref`, `reason`). A künye
    listed twice keeps the first reason."""
    sources: dict[str, MissingSource] = {}
    for m in missing:
        sources.setdefault(m["ref"], MissingSource.model_validate(m))
    if sources:
        next_step = (
            "Bu soru, şu kaynaklar bilgi tabanına eklendiğinde cevaplanabilir: "
            + ", ".join(sources)
            + "."
        )
    else:
        next_step = "Okunan kaynakların elle incelenmesi gerekmektedir."
    return SourceGap(
        topic=topic.title,
        missing_sources=list(sources.values()),
        given_facts=[f for f in facts.facts if f.status != "unknown"],
        next_step=next_step,
    )
