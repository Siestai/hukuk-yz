"""The citation gate (docs/architecture.md §5.1) and the rules an answer must keep, in pure code.

The draft model names sources and words; this module turns the draft into an `Answer` or says
why it cannot: a citation to a source that was not read, or not in force on the date of the law
applied, is dropped (md. 25); a point left with no citation is dropped; a "-iyor" form, a
`definite` answer with an unknown critical fact, or a `conditional` one that does not say what it
depends on is refused.
"""

from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, ValidationError

from agent.facts import critical_unknown
from agent.llm_schemas import CitationPick, DraftOutput
from agent.sources import ReadSource, citation, locate, summarize, valid_on
from agent.topics import Topic
from hukuk_models.chat import (
    Answer,
    AnswerPoint,
    Calculation,
    CaseFacts,
    CitationRef,
    FactChip,
    HoldingMap,
    HoldingRow,
    MissingInfo,
)
from hukuk_models.formal_turkish import progressive_forms

NOT_ANSWERED = "Doğrulanmış kaynakla cevap verilemedi."


class GateDrops(BaseModel):
    """What the gate removed, for the trace and the eval table."""

    citations: int = 0
    points: int = 0
    rows: int = 0


@dataclass
class GateResult:
    answer: Answer | None
    issues: list[str]
    drops: GateDrops = field(default_factory=GateDrops)


def draft_texts(draft: DraftOutput) -> list[str]:
    """Every sentence the model wrote in the draft (the quotes are the sources' own words)."""
    texts = [draft.headline, draft.reasoning_summary]
    texts += [p.text for p in draft.points]
    texts += [t for m in draft.missing_info for t in (m.condition, m.result)]
    texts += [c.used_for for p in draft.points for c in p.citations if c.used_for]
    return texts


def progressive_in(draft: DraftOutput) -> list[str]:
    return progressive_forms(draft_texts(draft))


def _cite(
    picks: list[CitationPick], sources: dict[str, ReadSource], applied_on: date, drops: GateDrops
) -> list[CitationRef]:
    cited = []
    for pick in picks:
        source = sources.get(pick.source_id)
        quote = pick.quote.strip() if pick.quote else None
        if source is None or not valid_on(source, applied_on):
            drops.citations += 1
        elif quote and locate(source, quote) is None:
            drops.citations += 1
        else:
            cited.append(
                citation(source, sub=pick.sub, quote=quote or None, used_for=pick.used_for)
            )
    return cited


def _chips(topic: Topic, facts: CaseFacts) -> list[FactChip]:
    """The facts the answer rests on: those given, and the critical ones still missing."""
    critical = set(critical_unknown(topic, facts))
    return [
        FactChip(fact_key=f.key, label=f.label, status=f.status)
        for f in facts.facts
        if f.status != "unknown" or f.key in critical
    ]


def _status_note(status: str, date_assumed: bool) -> str:
    if status == "definite":
        return "Verdiğiniz bilgilere göre."
    note = "Eksik bilgiler nedeniyle koşullu cevaptır."
    if date_assumed:
        note += " Olay tarihi bilinmediğinden bugünün tarihindeki metin esas alınmıştır."
    return note


def _law_text(applied_on: date) -> str:
    return f"{applied_on.strftime('%d.%m.%Y')} tarihinde yürürlükte olan metin"


def check_draft(
    draft: DraftOutput,
    *,
    topic: Topic,
    facts: CaseFacts,
    rows: list[HoldingRow],
    read: list[ReadSource],
    applied_on: date,
    date_assumed: bool,
) -> GateResult:
    sources = {s.source_id: s for s in read}
    drops = GateDrops()
    issues = []

    if forms := progressive_in(draft):
        issues.append(f"-iyor kipi kullanılmıştır: {', '.join(forms)}")
    if draft.status == "definite":
        if missing := critical_unknown(topic, facts):
            issues.append(f"kritik olgu bilinmezken kesin cevap verilemez: {', '.join(missing)}")
        if any(r.result == "unknown" for r in rows):
            issues.append("hüküm haritasında sonucu bilinmeyen satır varken kesin cevap verilemez")
    elif not draft.missing_info:
        issues.append("koşullu cevap neye bağlı olduğunu (missing_info) söylemelidir")

    points = []
    for p in draft.points:
        cited = _cite(p.citations, sources, applied_on, drops)
        if cited:
            points.append(AnswerPoint(text=p.text, citations=cited))
        else:
            drops.points += 1
    if not points:
        issues.append("atıfı doğrulanan nokta kalmamıştır")
    missing_info = [
        MissingInfo(
            fact_key=m.fact_key,
            condition=m.condition,
            result=m.result,
            citations=_cite(m.citations, sources, applied_on, drops),
        )
        for m in draft.missing_info
    ]
    if not rows:
        issues.append("doğrulanan hüküm haritası satırı yoktur")
    if issues:
        return GateResult(None, issues, drops)

    try:
        answer = Answer(
            status=draft.status,
            status_note=_status_note(draft.status, date_assumed),
            headline=draft.headline,
            fact_chips=_chips(topic, facts),
            points=points,
            short_point_count=min(3, len(points)),
            missing_info=missing_info,
            holding_map=HoldingMap(rows=rows, reasoning_summary=draft.reasoning_summary),
            calculations=[Calculation(title=c.title, needs=c.needs) for c in topic.calculations],
            read_sources=summarize(read),
            applied_law_date=applied_on,
            applied_law_text=_law_text(applied_on),
        )
    except ValidationError as exc:
        return GateResult(None, [f"şema: {e['msg']}" for e in exc.errors()], drops)
    return GateResult(answer, [], drops)


def not_answered(
    *,
    topic: Topic,
    facts: CaseFacts,
    rows: list[HoldingRow],
    read: list[ReadSource],
    applied_on: date,
    date_assumed: bool,
) -> Answer | None:
    """The answer given when the draft could not pass the gate twice: it says so and shows the
    holding map rows that were verified. None when there is no verified row to show."""
    if not rows:
        return None
    return Answer(
        status="conditional",
        status_note=_status_note("conditional", date_assumed),
        headline=NOT_ANSWERED,
        fact_chips=_chips(topic, facts),
        points=[
            AnswerPoint(
                text=(
                    "Bu soru için okunan kaynaklara dayanan ve doğrulanabilen bir cevap "
                    "oluşturulamamıştır. Hüküm haritası yalnız doğrulanan hükümleri "
                    "göstermektedir."
                ),
                citations=[],
            )
        ],
        short_point_count=1,
        missing_info=[
            MissingInfo(
                condition="Cevabın doğrulanması",
                result="Kaynakların elle incelenmesi gerekmektedir.",
            )
        ],
        holding_map=HoldingMap(
            rows=rows,
            reasoning_summary="Cevap, kaynak doğrulama kapısından geçemediği için üretilmemiştir.",
        ),
        read_sources=summarize(read),
        applied_law_date=applied_on,
        applied_law_text=_law_text(applied_on),
    )
