"""The citation gate (docs/architecture.md §5.1) and the rules an answer must keep, in pure code.

The draft model names sources and words; this module turns the draft into an `Answer` or says
why it cannot: a citation to a source that was not read, or not in force on the date of the law
applied, is dropped (md. 25); a point left with no citation is dropped; a "-iyor" form, a headline
that rests on no verified holding row, a `definite` answer with an unknown critical fact, or a
`conditional` one that does not say what it depends on is refused. The last draft, made after the
correction, loses only its sentences in the "-iyor" form, unless the answer loses its meaning.
"""

import re
from collections.abc import Callable, Iterable, Sequence
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
# Decision K1: an answer whose every citation is to a source no reviewer has approved says so.
ONLY_UNREVIEWED = (
    "Cevabın dayandığı kaynakların tamamı onaysızdır (test); uzman incelemesinden geçmemiştir."
)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


class GateDrops(BaseModel):
    """What the gate removed, for the trace and the eval table."""

    citations: int = 0
    points: int = 0
    rows: int = 0
    # Of the last draft: its sentences in the "-iyor" form, and the branches left with no words.
    sentences: int = 0
    branches: int = 0


class GateCited(BaseModel):
    """The citations of an answer by the review status of their source: an unreviewed one is a
    test source (decision K1)."""

    approved: int = 0
    unreviewed: int = 0


def cited_by_status(answer: Answer) -> GateCited:
    """Every citation the answer shows: of its points, its branches and its holding map."""
    cited = [c for p in answer.points for c in p.citations]
    cited += [c for m in answer.missing_info for c in m.citations]
    cited += [r.citation for r in answer.holding_map.rows] + answer.holding_map.citations
    unreviewed = sum(c.review_status == "analyzed" for c in cited)
    return GateCited(approved=len(cited) - unreviewed, unreviewed=unreviewed)


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


def _context_texts(rows: Sequence[HoldingRow], facts: CaseFacts | None) -> list[str]:
    """The words the models wrote outside the draft: into the rows and the title of the facts
    (a row's quote is the source's own words and is not scanned)."""
    texts = [t for r in rows for t in (r.condition, r.fact_value) if t]
    if facts is not None:
        texts.append(facts.title)
    return texts


def progressive_in(
    draft: DraftOutput, rows: Sequence[HoldingRow] = (), facts: CaseFacts | None = None
) -> list[str]:
    """The "-iyor" forms in the draft and in the words the models wrote into the rows and the
    title of the facts."""
    return progressive_forms(draft_texts(draft) + _context_texts(rows, facts))


def _sentences(text: str) -> list[str]:
    return [" ".join(s.split()) for s in _SENTENCE_END.split(text) if s.strip()]


def progressive_sentences(texts: Iterable[str]) -> list[str]:
    """The sentences of `texts` with an "-iyor" form, each once: what a correction rewrites."""
    found = [s for t in texts for s in _sentences(t) if progressive_forms([s])]
    return list(dict.fromkeys(found))


def _formal(text: str, drops: GateDrops) -> str:
    """`text` without its sentences in the "-iyor" form; the others are kept as written."""
    sentences = _sentences(text)
    kept = [s for s in sentences if not progressive_forms([s])]
    drops.sentences += len(sentences) - len(kept)
    return text if len(kept) == len(sentences) else " ".join(kept)


def _register_feedback(forms: Sequence[str], sentences: Sequence[str]) -> str:
    return (
        f"-iyor kipi kullanılmıştır: {', '.join(forms)}. Şu cümleleri anlamlarını koruyarak "
        "-mektedir / -maktadır kipi veya geniş zamanla yeniden yaz: "
        + "; ".join(f"«{s}»" for s in sentences)
    )


def _headline_supported(
    numbers: Sequence[int],
    rows: Sequence[HoldingRow],
    sources: dict[str, ReadSource],
    applied_on: date,
) -> bool:
    """The headline names at least one row; every row it names is one of the holding map and
    stands on a source that was read and is in force on the date of the law applied."""
    if not numbers or any(not 1 <= n <= len(rows) for n in numbers):
        return False
    named = {rows[n - 1].citation.source_id for n in numbers}
    return all(i in sources and valid_on(sources[i], applied_on) for i in named)


# This gate checks quote presence and provenance, not whether the claim follows from it.
# In particular, a genuine but irrelevant quote can still pass. Support and threshold
# fidelity are model instructions, with real-model/legal review still required.
def _cite(
    picks: list[CitationPick],
    sources: dict[str, ReadSource],
    applied_on: date,
    drops: GateDrops,
    formal: Callable[[str], str],
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
                    used_for=formal(pick.used_for) or None if pick.used_for else None,
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
    final: bool = False,
) -> GateResult:
    """The answer of `draft`, or why there is none. `final`: the draft is the last one, made after
    the gate asked for a correction; its sentences in the "-iyor" form drop instead of the whole
    draft, and the answer is refused if that leaves no headline, no gerekçe, no point or not a
    branch for every unknown critical fact."""
    sources = {s.source_id: s for s in read}
    drops = GateDrops()
    issues = []
    issue_counts: dict[str, int] = {}

    def reject(code: str, feedback: str, count: int = 1) -> None:
        issues.append(feedback)
        issue_counts[code] = count

    def formal(text: str) -> str:
        return _formal(text, drops) if final else text

    if issue := holding_issue(rows):
        reject(*issue)

    context = _context_texts(rows, facts)
    scanned = context if final else draft_texts(draft) + context
    if forms := progressive_forms(scanned):
        reject(
            "progressive_form",
            _register_feedback(forms, progressive_sentences(scanned)),
            len(forms),
        )
    headline, reasoning = formal(draft.headline), formal(draft.reasoning_summary)
    if final and not (headline and reasoning):
        written = {draft.headline: headline, draft.reasoning_summary: reasoning}
        lost = [t for t, kept in written.items() if not kept]
        reject(
            "progressive_form",
            "başlık veya gerekçe yalnız -iyor kipindeki cümlelerden oluşmaktadır; "
            "bu cümleler düşünce cevap anlamını yitirmektedir",
            len(progressive_forms(lost)),
        )
    if rows and not _headline_supported(draft.headline_rows, rows, sources, applied_on):
        reject(
            "unsupported_headline",
            "headline_rows, başlığın sonucunu dayandırdığı hüküm haritası satırlarının row "
            "numaralarını içermelidir; her numara verilen bir satıra karşılık gelmelidir. "
            "Hiçbir doğrulanan satıra dayanmayan başlık yazma.",
        )

    points = []
    for p in draft.points:
        text = formal(p.text)
        cited = _cite(p.citations, sources, applied_on, drops, formal) if text else []
        if cited:
            points.append(AnswerPoint(text=text, citations=cited))
        else:
            drops.points += 1
    if not points:
        reject("no_verified_points", "atıfı doğrulanan nokta kalmamıştır")
    missing_info = []
    for m in draft.missing_info:
        condition, outcome = formal(m.condition), formal(m.result)
        if final and not (condition and outcome):
            drops.branches += 1
            continue
        cited = _cite(m.citations, sources, applied_on, drops, formal)
        if m.citations and len(cited) != len(m.citations):
            reject(
                "unsupported_branch",
                "koşullu dalın dayanak alıntısı doğrulanamamıştır; hukuki sonuç uydurma, "
                "okunan destek yoksa kaynak yetersizliğini belirt",
            )
        missing_info.append(
            MissingInfo(
                fact_key=m.fact_key,
                condition=condition,
                result=outcome,
                citations=cited,
            )
        )

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
        if not missing_info:
            reject(
                "missing_conditions",
                "koşullu cevap neye bağlı olduğunu (missing_info) söylemelidir",
            )
        represented = {m.fact_key for m in missing_info}
        uncovered = [key for key in critical_unknown(topic, facts) if key not in represented]
        if uncovered:
            reject(
                "uncovered_critical_facts",
                "missing_info içinde her bilinmeyen kritik olgunun fact_key değeri bulunmalıdır; "
                f"eksik anahtarlar: {', '.join(uncovered)}. Okunan destek yoksa hukuki sonuç "
                "veya atıf uydurma; netleştirme iste veya kaynak yetersizliğini belirt.",
                len(uncovered),
            )
    if issues:
        return GateResult(None, issues, drops, issue_counts)

    try:
        answer = Answer(
            status=draft.status,
            status_note=_status_note(draft.status, date_assumed, unread),
            headline=headline,
            fact_chips=_chips(topic, facts),
            points=points,
            short_point_count=min(3, len(points)),
            missing_info=missing_info,
            holding_map=HoldingMap(rows=rows, reasoning_summary=reasoning),
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
    counts = cited_by_status(answer)
    if counts.unreviewed and not counts.approved:
        answer.status_note += f" {ONLY_UNREVIEWED}"
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
