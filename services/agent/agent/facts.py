"""The case facts and the clarification, in pure code (no model, no KB).

The model only fills in what the question says; which questions are asked, in which order, with
which options and "neden soruyorum" text, comes from the topic template. An answer fills the fact
its question completes.
"""

from datetime import date

from agent.llm_schemas import IntakeOutput
from agent.topics import Option, Topic, TopicFact, parse_date
from hukuk_models.chat import (
    CaseFacts,
    CitationRef,
    Clarification,
    ClarificationAnswer,
    ClarificationQuestion,
    Fact,
    QuestionInput,
    QuestionOption,
)


def _norm(text: str) -> str:
    return " ".join(text.replace("İ", "i").replace("I", "ı").lower().split())


def _matching_option(fact: TopicFact, value: str) -> Option | None:
    if fact.question is None:
        return None
    return next(
        (o for o in fact.question.options if _norm(value) in (_norm(o.value), _norm(o.label))),
        None,
    )


def _extracted(fact: TopicFact, extracted: IntakeOutput) -> Fact | None:
    """The fact as the intake model read it from the question; None: the question says nothing."""
    found = next((f for f in extracted.facts if f.key == fact.key), None)
    value = (found.value or "").strip() if found else ""
    if found is None or found.status == "unknown" or not value:
        return None
    option = _matching_option(fact, value)
    if option is not None:
        value = option.label
    status = "assumed_never" if found.status == "assumed_never" else "known"
    return Fact(key=fact.key, label=fact.label, value=value, status=status)


def build_facts(topic: Topic, extracted: IntakeOutput, previous: CaseFacts | None) -> CaseFacts:
    """The facts of the template, from this question first, then from the earlier turns of the
    same topic; what neither says is unknown."""
    earlier = {f.key: f for f in previous.facts} if previous else {}
    facts = []
    for tf in topic.facts:
        fact = _extracted(tf, extracted) or earlier.get(tf.key)
        facts.append(fact or Fact(key=tf.key, label=tf.label, status="unknown"))
    event_date = extracted.event_date or (previous.event_date if previous else None)
    return CaseFacts(
        title=extracted.title.strip() or topic.title,
        facts=facts,
        event_date=event_date_of(topic, facts) or event_date,
    )


def event_date_of(topic: Topic, facts: list[Fact]) -> date | None:
    """The date of the template's event-date fact, if it is known."""
    if topic.event_date_fact is None:
        return None
    fact = next((f for f in facts if f.key == topic.event_date_fact), None)
    return parse_date(fact.value) if fact and fact.value else None


def critical_unknown(topic: Topic, facts: CaseFacts) -> list[str]:
    """The keys of the critical facts that are still unknown."""
    unknown = {f.key for f in facts.facts if f.status == "unknown"}
    return [tf.key for tf in topic.facts if tf.critical and tf.key in unknown]


def clarification_for(
    topic: Topic, facts: CaseFacts, sources: dict[str, CitationRef]
) -> Clarification | None:
    """One question per unknown critical fact, from the template; None when nothing is missing.
    `sources` maps the künye of a basis to the citation the knowledge base resolved; a basis it
    could not resolve is left out, never made up."""
    questions: list[ClarificationQuestion] = []
    for key in critical_unknown(topic, facts):
        tf = topic.fact(key)
        assert tf is not None and tf.question is not None
        q = tf.question
        questions.append(
            ClarificationQuestion(
                id=f"q{len(questions) + 1}",
                fact_key=key,
                text=q.text,
                why=q.why,
                source_refs=[sources[b.ref] for b in q.basis if b.ref in sources],
                input=QuestionInput(
                    kind=q.kind,
                    options=[QuestionOption(value=o.value, label=o.label) for o in q.options],
                ),
            )
        )
    if not questions:
        return None
    return Clarification(questions=questions, index=1, total=len(questions))


def _answered_fact(
    tf: TopicFact, question: ClarificationQuestion, answer: ClarificationAnswer
) -> Fact:
    """The fact after the answer; an unusable answer ("Bilmiyorum", a value that is no option or
    no date) leaves it unknown."""
    unknown = Fact(key=tf.key, label=tf.label, status="unknown")
    if answer.value is None:
        return unknown
    kind, value = question.input.kind, answer.value.strip()
    if kind == "choice":
        option = _matching_option(tf, value)
        if option is None:
            return unknown
        status = "assumed_never" if option.assumed_never else "known"
        return Fact(key=tf.key, label=tf.label, value=option.label, status=status)
    if kind == "date":
        day = parse_date(value)
        if day is None:
            return unknown
        return Fact(key=tf.key, label=tf.label, value=day.strftime("%d.%m.%Y"), status="known")
    return Fact(key=tf.key, label=tf.label, value=value, status="known") if value else unknown


def apply_answers(
    topic: Topic,
    clarification: Clarification,
    answers: list[ClarificationAnswer],
    facts: CaseFacts,
) -> CaseFacts:
    """`facts` with the answers filled in; a question that got no answer stays as it is."""
    by_id = {q.id: q for q in clarification.questions}
    updated = {f.key: f for f in facts.facts}
    for answer in answers:
        question = by_id.get(answer.question_id)
        tf = topic.fact(question.fact_key) if question else None
        if question is not None and tf is not None:
            updated[tf.key] = _answered_fact(tf, question, answer)
    merged = [updated[f.key] for f in facts.facts]
    return facts.model_copy(
        update={"facts": merged, "event_date": event_date_of(topic, merged) or facts.event_date}
    )
