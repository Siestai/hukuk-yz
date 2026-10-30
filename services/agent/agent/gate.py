"""The citation gate (docs/architecture.md §5.1) and the rules an answer must keep, in pure code.

The draft model names sources and words; this module turns the draft into an `Answer` or says
why it cannot: a citation to a source that was not read, or not in force on the date of the law
applied, is dropped (md. 25); a point left with no citation is dropped; a "-iyor" form, a
`definite` answer with an unknown critical fact, or a `conditional` one that does not say what it
depends on is refused.
"""

from collections.abc import Sequence
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
    # Fixed codes only: detailed issues belong in model feedback, never in logs.
    issue_counts: dict[str, int] = field(default_factory=dict)


def holding_issue(rows: Sequence[HoldingRow]) -> tuple[str, str] | None:
    """No row or explicit inapplicability cannot support an ordinary rights answer.

    not_met is different: the rule applies, but its condition is not satisfied.
    Mixed and unknown rows remain eligible for the normal draft gate.
    """
    if not rows:
        return "no_verified_rows", "doğrulanan hüküm haritası satırı yoktur"
    if all(r.result == "not_applicable" for r in rows):
        return (
            "all_holdings_not_applicable",
            "doğrulanan hükümlerin tamamı uygulanamaz olarak işaretlenmiştir; "
            "bu kaynaklarla soruya cevap verilemez",
        )
    return None


def draft_texts(draft: DraftOutput) -> list[str]:
    """Every sentence the model wrote in the draft (the quotes are the sources' own words)."""
    texts = [draft.headline, draft.reasoning_summary]
    texts += [p.text for p in draft.points]
    texts += [t for m in draft.missing_info for t in (m.condition, m.result)]
    texts += [
        c.used_for
        for picks in [
            *[p.citations for p in draft.points],
            *[m.citations for m in draft.missing_info],
        ]
        for c in picks
        if c.used_for
    ]
    return texts


def progressive_in(
    draft: DraftOutput, rows: Sequence[HoldingRow] = (), facts: CaseFacts | None = None
) -> list[str]:
    """The "-iyor" forms in the draft and in the words the models wrote into the rows and the
    title of the facts (a row's quote is the source's own words and is not scanned)."""
    texts = draft_texts(draft)
    texts += [t for r in rows for t in (r.condition, r.fact_value) if t]
    if facts is not None:
        texts.append(facts.title)
    return progressive_forms(texts)


# This gate checks quote presence and provenance, not whether the claim follows from it.
# In particular, a genuine but irrelevant quote can still pass. Support and threshold
# fidelity are model instructions, with real-model/legal review still required.
def _cite(
    picks: list[CitationPick], sources: dict[str, ReadSource], applied_on: date, drops: GateDrops
) -> list[CitationRef]:
    cited = []
    for pick in picks:
        source = sources.get(pick.source_id)
        quote = pick.quote.strip() if pick.quote else None
        if source is None or not valid_on(source, applied_on):
            drops.citations += 1
        elif not quote or locate(source, quote) is None:
            drops.citations += 1
        else:
            cited.append(
                citation(
                    source,
                    sub=pick.sub,
                    quote=quote or None,
                    used_for=pick.used_for,
                )
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


def _status_note(status: str, date_assumed: bool, unread: Sequence[str]) -> str:
    if status == "definite":
        return "Verdiğiniz bilgilere göre."
    note = "Eksik bilgiler nedeniyle koşullu cevaptır."
    if date_assumed:
        note += " Olay tarihi bilinmediğinden bugünün tarihindeki metin esas alınmıştır."
    if unread:
        note += f" Okunamayan kaynaklar bulunmaktadır: {', '.join(unread)}."
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
    unread: Sequence[str] = (),
) -> GateResult:
    sources = {s.source_id: s for s in read}
    drops = GateDrops()
    issues = []
    issue_counts: dict[str, int] = {}

    def reject(code: str, feedback: str, count: int = 1) -> None:
        issues.append(feedback)
        issue_counts[code] = count

    if issue := holding_issue(rows):
        reject(*issue)

    if forms := progressive_in(draft, rows, facts):
        reject("progressive_form", f"-iyor kipi kullanılmıştır: {', '.join(forms)}", len(forms))
    if draft.status == "definite":
        if missing := critical_unknown(topic, facts):
            reject(
                "critical_unknown",
                f"kritik olgu bilinmezken kesin cevap verilemez: {', '.join(missing)}",
                len(missing),
            )
        if unread:
            reject(
                "unread_source",
                f"okunamayan kaynak varken kesin cevap verilemez: {', '.join(unread)}",
                len(unread),
            )
        if any(r.result == "unknown" for r in rows):
            reject(
                "unknown_holding",
                "hüküm haritasında sonucu bilinmeyen satır varken kesin cevap verilemez",
            )
    else:
        if not draft.missing_info:
            reject(
                "missing_conditions",
                "koşullu cevap neye bağlı olduğunu (missing_info) söylemelidir",
            )
        represented = {m.fact_key for m in draft.missing_info}
        uncovered = [key for key in critical_unknown(topic, facts) if key not in represented]
        if uncovered:
            reject(
                "uncovered_critical_facts",
                "missing_info içinde her bilinmeyen kritik olgunun fact_key değeri bulunmalıdır; "
                f"eksik anahtarlar: {', '.join(uncovered)}. Okunan destek yoksa hukuki sonuç "
                "veya atıf uydurma; netleştirme iste veya kaynak yetersizliğini belirt.",
                len(uncovered),
            )

    points = []
    for p in draft.points:
        cited = _cite(p.citations, sources, applied_on, drops)
        if cited:
            points.append(AnswerPoint(text=p.text, citations=cited))
        else:
            drops.points += 1
    if not points:
        reject("no_verified_points", "atıfı doğrulanan nokta kalmamıştır")
    missing_info = []
    for m in draft.missing_info:
        cited = _cite(m.citations, sources, applied_on, drops)
        if m.citations and len(cited) != len(m.citations):
            reject(
                "unsupported_branch",
                "koşullu dalın dayanak alıntısı doğrulanamamıştır; hukuki sonuç uydurma, "
                "okunan destek yoksa kaynak yetersizliğini belirt",
            )
        missing_info.append(
            MissingInfo(
                fact_key=m.fact_key,
                condition=m.condition,
                result=m.result,
                citations=cited,
            )
        )
    if issues:
        return GateResult(None, issues, drops, issue_counts)

    try:
        answer = Answer(
            status=draft.status,
            status_note=_status_note(draft.status, date_assumed, unread),
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
        return GateResult(
            None,
            [f"şema: {e['msg']}" for e in exc.errors()],
            drops,
            {"answer_schema": exc.error_count()},
        )
    return GateResult(answer, [], drops)


def not_answered(
    *,
    topic: Topic,
    facts: CaseFacts,
    rows: list[HoldingRow],
    read: list[ReadSource],
    applied_on: date,
    date_assumed: bool,
    unread: Sequence[str] = (),
) -> Answer | None:
    """The answer given when the draft could not pass the gate twice: it says so and shows the
    holding map rows that were verified. None when there is no verified row to show."""
    rows = [r for r in rows if not progressive_forms([r.condition, r.fact_value or ""])]
    if not rows:
        return None
    note = _status_note("conditional", date_assumed, unread)
    if all(r.result == "not_applicable" for r in rows):
        note = note.replace(
            "Eksik bilgiler nedeniyle koşullu cevaptır.",
            "Doğrulanan hükümler bu soruya uygulanabilir bir cevap için yeterli değildir.",
        )
    return Answer(
        status="conditional",
        status_note=note,
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
