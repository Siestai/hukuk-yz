"""The instructions and the prompts of the three model nodes. Turkish; the rules are the
project's (formal register, nothing cited that was not read, no calculation by the model)."""

import json

from agent.sources import ReadSource
from agent.topics import Topic
from hukuk_models.chat import CaseFacts, HoldingRow

# One source in a prompt shows at most this many characters of what was read of it.
MAX_SOURCE_CHARS = 6000

REGISTER = (
    'Dil: resmi Türkçe; geniş zaman ve -mektedir / -maktadır kipi kullan; "-iyor" kipini '
    '(örneğin "yapılıyor", "bulunuyor") hiçbir cümlede kullanma.'
)

INTAKE_INSTRUCTIONS = f"""\
Sen bir iş ve sosyal güvenlik hukuku asistanının olay kayıt adımısın. Kullanıcının sorusundan \
yalnızca şunları çıkarırsın: konu, kısa bir başlık, olay tarihi ve olgular. Hukuki değerlendirme \
yapmaz, soru sormaz, cevap vermezsin.
- topic: verilen konu kimliklerinden biri; hiçbiri uymuyorsa "genel".
- facts: yalnız seçtiğin konunun olgu anahtarlarını kullan. Soruda açıkça yazılan olguyu value \
ile (kullanıcının sözleriyle) ve status "known" ile yaz. Soruda yazılmayan olguyu listeye ekleme.
- Bir olgunun uygulanmadığını kullanıcı açıkça söylediyse status "assumed_never"; söylemediyse \
bunu asla varsayma.
- event_date: yalnız soruda açıkça yazılı bir olay tarihi varsa (YYYY-MM-DD); bugünün tarihini \
yazma.
- title: olayı özetleyen kısa Türkçe başlık (örnek: "İşe iade, 5 ay kıdem").
{REGISTER}"""

HOLDING_INSTRUCTIONS = f"""\
Sen bir hüküm haritası çıkarma adımısın. Verilen kaynak metinlerinden, olaya uygulanacak her \
hüküm için bir satır yazarsın: hükmün koşulu, olgunun bu koşul için değeri ve sonuç.
- source_id yalnız verilen kaynak listesinden olmalı; sub, hükmün fıkrasıdır (örneğin "1").
- condition_quote, kaynak metinde BİREBİR geçen en az üç kelimelik bir parça olmalı; kaynaktan \
kopyala, değiştirme, kısaltma, özetleme. Birebir geçmeyen satır silinir.
- result: met (koşul sağlanıyor), not_met, not_applicable veya unknown (olgu bilinmiyorsa).
- Kaynakta olmayan hüküm yazma; madde veya karar numarası uydurma.
{REGISTER}"""

DRAFT_INSTRUCTIONS = f"""\
Sen cevap taslağı yazan adımsın. Yalnız verilen hüküm haritası satırlarına ve kaynak listesine \
dayanırsın; kaynakta olmayan iddia kurmaz, madde veya karar numarası uydurmaz, tutar veya gün \
hesaplamazsın (hesap ayrı bir motorda yapılır).
- Her noktanın citations alanında okunan kaynağın source_id'si (ve varsa sub, quote) bulunmalı; \
quote kaynak metninden birebir olmalı. Atfı olmayan nokta silinir.
- Bilinmeyen kritik olgu varsa status "conditional" olmalı ve missing_info neye göre değiştiğini \
koşul -> sonuç olarak söylemeli. Bilinmeyen olgu varken "definite" yazma.
- status "definite" ise missing_info boş olur.
- Verilen tuzak ve ayrımları gözet; kesin söylenemeyen şeyi kesin söyleme.
- headline tek cümlelik sonuçtur; points kısa ve ayrı noktalardır (en önemli üçü başta); \
reasoning_summary hüküm haritasının kısa gerekçesidir.
{REGISTER}"""

REWRITE_INSTRUCTIONS = f"""\
Sana bir cevap taslağı ve içindeki yasak kip biçimleri verilecek. Taslağı, anlamını, atıflarını \
(source_id, sub, quote) ve yapısını aynen koruyarak yalnız kipi düzelt.
{REGISTER}"""


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1, default=str)


def facts_block(facts: CaseFacts) -> str:
    return _dump(
        {
            "olay_tarihi": facts.event_date,
            "olgular": [
                {"key": f.key, "label": f.label, "value": f.value, "status": f.status}
                for f in facts.facts
            ],
        }
    )


def intake_prompt(question: str, topics: dict[str, Topic], previous: CaseFacts | None) -> str:
    listing = [
        {
            "topic": t.id,
            "kapsam": t.description,
            "olgu_anahtarlari": {f.key: f.label for f in t.facts},
        }
        for t in topics.values()
    ]
    parts = [f"Konular:\n{_dump(listing)}", f"Soru:\n{question}"]
    if previous is not None:
        parts.append(f"Önceki mesajlardan bilinenler:\n{facts_block(previous)}")
    return "\n\n".join(parts)


def sources_block(read: list[ReadSource]) -> str:
    blocks = []
    for s in read:
        text = " […] ".join(p.text for p in s.passages)[:MAX_SOURCE_CHARS]
        label = "onaylanmadı" if s.review_status == "analyzed" else "onaylı"
        blocks.append(f"[source_id: {s.source_id}] {s.ref} ({s.category}, {label})\n{text}")
    return "\n\n".join(blocks)


def traps_block(topic: Topic) -> str:
    return "\n".join(f"- {t}" for t in topic.traps) or "-"


def holding_prompt(topic: Topic, facts: CaseFacts, read: list[ReadSource]) -> str:
    return (
        f"Olgular:\n{facts_block(facts)}\n\nTuzaklar ve ayrımlar:\n{traps_block(topic)}\n\n"
        f"Kaynaklar:\n{sources_block(read)}"
    )


def draft_prompt(
    topic: Topic,
    facts: CaseFacts,
    rows: list[HoldingRow],
    read: list[ReadSource],
    unread: list[str],
    feedback: list[str],
) -> str:
    holding = [
        {
            "source_id": r.citation.source_id,
            "ref": r.citation.ref,
            "condition": r.condition,
            "fact_value": r.fact_value,
            "result": r.result,
        }
        for r in rows
    ]
    parts = [
        f"Olgular:\n{facts_block(facts)}",
        f"Hüküm haritası:\n{_dump(holding)}",
        f"Tuzaklar ve ayrımlar:\n{traps_block(topic)}",
        f"Kaynaklar:\n{sources_block(read)}",
    ]
    if unread:
        parts.append("Okunamayan kaynaklar (bunlara dayanma): " + ", ".join(unread))
    if feedback:
        parts.append(
            "Önceki taslak kapıdan geçemedi; şunları düzelt:\n"
            + "\n".join(f"- {i}" for i in feedback)
        )
    return "\n\n".join(parts)
