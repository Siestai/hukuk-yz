"""Fakes for the agent tests: a knowledge base with a few statute passages, and a scripted model
(Pydantic AI `FunctionModel`) that answers by the kind of output the node asks for."""

import json
import os
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agent.api import Graph, RunRequest, turn_events
from agent.kb import KbHit, KbMatch
from agent.sources import covers
from agent.trace import Tracing
from hukuk_models.chat import ClarificationAnswer

QUESTION = "5 ay kıdeme sahip bir işçi. İşe iade davası açabilir mi gerekçesi ile birlikte açıkla"
ANSWERS = {
    "q1": "gte_30",
    "q2": "belirsiz",
    "q3": "2026-10-03",
    "q4": "hayir",
    "q5": "hayir",
    "q6": "hayir",
}

M18_1 = (
    "Otuz veya daha fazla işçi çalıştıran işyerlerinde en az altı aylık kıdemi olan işçinin "
    "belirsiz süreli iş sözleşmesini fesheden işveren"
)
M18_4 = "aynı işverenin bir veya değişik işyerlerinde geçen süreler birleştirilerek hesap edilir"
M18_UNDERGROUND = "Yer altı işlerinde çalışan işçilerde kıdem şartı aranmaz"
M17_4 = "Bildirim şartına uymayan taraf, bildirim süresine ilişkin ücret tutarında tazminat"
M102_5 = (
    "İdarî para cezalarının, Kuruma itiraz edilmeden veya yargı yoluna başvurulmadan önce "
    "tebliğ tarihinden itibaren onbeş gün içinde peşin ödenmesi halinde, bunun dörtte üçü "
    "tahsil edilir."
)


def hit(
    source_id: str,
    ref: str,
    title: str,
    *passages: str,
    category: str = "statute",
    valid_from: date | None = None,
    valid_to: date | None = None,
) -> KbHit:
    offset = 0
    matches = []
    for i, text in enumerate(passages):
        matches.append(
            KbMatch(
                chunk_id=f"{source_id}#{i}",
                text=text,
                char_start=offset,
                char_end=offset + len(text),
            )
        )
        offset += len(text) + 1
    return KbHit.model_validate(
        {
            "source_id": source_id,
            "category": category,
            "title": title,
            "ref": ref,
            "review_status": "approved",
            "verification": None,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "matches": [m.model_dump() for m in matches],
        }
    )


def labour_law_hits() -> list[KbHit]:
    """4857 m.18 and m.17, 5510 m.102: enough for the SB-001 and SB-016 flows."""
    return [
        hit(
            "statute:4857:m18",
            "4857 m.18",
            "4857 sayılı İş Kanunu m.18",
            f"(1) {M18_1}",
            f"(4) {M18_4}",
            f"(1) {M18_UNDERGROUND}",
        ),
        hit("statute:4857:m17", "4857 m.17", "4857 sayılı İş Kanunu m.17", M17_4),
        hit(
            "statute:5510:m102",
            "5510 m.102",
            "5510 sayılı Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu m.102",
            f"(5) {M102_5}",
        ),
    ]


class FakeKb:
    """`/kb/search` over a list of hits: a query that is a künye finds the source it covers, any
    other query the sources that share a word of it."""

    def __init__(self, hits: Sequence[KbHit] | None = None) -> None:
        self.hits = list(labour_law_hits() if hits is None else hits)
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        q: str,
        *,
        categories: Sequence[str] = (),
        as_of: date | None = None,
        limit: int = 10,
    ) -> list[KbHit]:
        self.calls.append({"q": q, "categories": list(categories), "as_of": as_of})
        words = {w for w in q.casefold().split() if len(w) > 4}

        def found(h: KbHit) -> bool:
            text = " ".join(m.text or "" for m in h.matches).casefold()
            return covers(h.ref, q) or any(w in text for w in words)

        return [
            h
            for h in self.hits
            if found(h)
            and (not categories or h.category in categories)
            and (
                as_of is None
                or (
                    (h.valid_from is None or h.valid_from <= as_of)
                    and (h.valid_to is None or as_of < h.valid_to)
                )
            )
        ][:limit]


class FailingKb:
    """A knowledge base whose every search raises `error`."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def search(
        self,
        q: str,
        *,
        categories: Sequence[str] = (),
        as_of: date | None = None,
        limit: int = 10,
    ) -> list[KbHit]:
        raise self.error


INTAKE_SB001 = {
    "topic": "ise_iade",
    "title": "İşe iade, 5 ay kıdem",
    "event_date": None,
    "facts": [{"key": "kidem", "value": "5 ay", "status": "known"}],
}
INTAKE_SB016 = {
    "topic": "idari_para_cezasi",
    "title": "İdari para cezası, indirim",
    "facts": [
        {"key": "belge_30_gun", "value": "30 gün içinde verildi", "status": "known"},
        {"key": "odeme_15_gun", "value": "15 gün içinde ödenmedi", "status": "known"},
    ],
}


def row(source_id: str, quote: str, result: str = "met", sub: str | None = None) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "sub": sub,
        "condition": "Kıdem ve işçi sayısı şartı",
        "condition_quote": quote,
        "fact_value": "5 ay",
        "result": result,
    }


def draft(
    status: str = "conditional",
    *,
    points: list[dict[str, Any]] | None = None,
    missing: bool = True,
    headline: str = "İşe iade davası açılamamaktadır.",
) -> dict[str, Any]:
    cited = [{"source_id": "statute:4857:m18", "sub": "1", "quote": M18_1}]
    return {
        "status": status,
        "headline": headline,
        "points": points
        if points is not None
        else [{"text": "Altı aylık kıdem şartı aranmaktadır.", "citations": cited}],
        "missing_info": [
            {
                "fact_key": "isci_sayisi",
                "condition": "İşyerinde otuz veya daha fazla işçi çalışmaktaysa",
                "result": "İş güvencesi hükümleri uygulanmaktadır.",
            }
        ]
        if missing
        else [],
        "reasoning_summary": "Hüküm haritasına göre kıdem şartı sağlanmamaktadır.",
    }


@dataclass
class Script:
    """What the scripted model answers. `drafts` are used in turn (the last one repeats)."""

    intake: dict[str, Any] = field(default_factory=lambda: INTAKE_SB001)
    holding: dict[str, Any] = field(
        default_factory=lambda: {"rows": [row("statute:4857:m18", M18_1, sub="1")]}
    )
    drafts: list[dict[str, Any]] = field(default_factory=lambda: [draft()])
    rewrite: dict[str, Any] | None = None
    calls: list[tuple[str, str]] = field(default_factory=list)

    def of(self, kind: str) -> list[str]:
        return [prompt for k, prompt in self.calls if k == kind]


def _prompt(messages: list[ModelMessage]) -> str:
    return "\n".join(
        str(part.content)
        for message in messages
        for part in message.parts
        if isinstance(part, UserPromptPart)
    )


def scripted(script: Script) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = _prompt(messages)
        properties = info.output_tools[0].parameters_json_schema["properties"]
        drafts_made = len(script.of("draft"))
        if "topic" in properties:
            kind, out = "intake", script.intake
        elif "rows" in properties:
            kind, out = "holding", script.holding
        elif "Yasak biçimler" in prompt:
            kind, out = "rewrite", script.rewrite or script.drafts[-1]
        else:
            kind, out = "draft", script.drafts[min(drafts_made, len(script.drafts) - 1)]
        script.calls.append((kind, prompt))
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, json.dumps(out, ensure_ascii=False))]
        )

    return FunctionModel(respond)


def require_database_url() -> str:
    """The database of the tests that need Postgres; they skip when DATABASE_URL is unset (CI
    sets it)."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url


async def turn(graph: Graph, request: RunRequest) -> list[Any]:
    with Tracing().run(request.thread_id) as trace:
        return [e async for e in turn_events(graph, request, trace)]


def ask(thread: str) -> RunRequest:
    return RunRequest(thread_id=thread, text=QUESTION)


def answer_all(thread: str, **override: str | None) -> RunRequest:
    """Answers q1..q6; an override of None answers "Bilmiyorum"."""
    given = {**ANSWERS, **override}
    return RunRequest(
        thread_id=thread,
        clarification_answers=[
            ClarificationAnswer(question_id=k, value=v)
            if v is not None
            else ClarificationAnswer(question_id=k, unknown=True)
            for k, v in given.items()
        ],
    )


def only[T](events: list[Any], kind: type[T]) -> T:
    found = [e for e in events if isinstance(e, kind)]
    assert len(found) == 1, [type(e).__name__ for e in events]
    return found[0]


def unique_thread() -> str:
    return f"t-{uuid.uuid4().hex[:8]}"
