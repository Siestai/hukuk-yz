# Görev 15: Cevap sözleşmesi (chat API şeması) ve eval seti v0

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/architecture.md` §4.1 (soru → cevap), §5 (md. 22, 23, 25, 35), `docs/decisions.md` 2026-10-27 (chat UI yönü: Alternatif B; v1 kapalı beta), `docs/design/chat-ui/` (B ekranları), konu kartları (`eval/cases/` kaynağı).
Skill'ler: `task-pr-hygiene`, `frontend-ui` (tip üretimi).

## Hedef

UI, ajan ve eval'in aynı veri yapısını konuşması. Bu sözleşme sabitlenince web (Görev 16) sahte veriyle, ajan (Görev 17) gerçek veriyle **paralel** ilerler; eval aynı yapıyı puanlar.

## Kapsam

### 1. Şema (`packages/models/hukuk_models/chat.py`, Pydantic v2)

Alternatif B'nin üç ekranından çıkarılır:

- `ChatMode`: `short` | `detailed` | `reasoned` (kısa / ayrıntılı / gerekçeli). Mod yalnız sunumu değiştirir: bir cevap üç modun verisini birlikte taşır, mod değişimi yeni LLM çağrısı gerektirmez.
- `CaseFacts` ("Anladığım olay"): `title` (ör. "İşe iade, 5 ay kıdem"), `facts: [{key, label, value | null, status: known|unknown|assumed_never}]`, `event_date` (olay tarihi; uygulanan mevzuatın tarihi), kullanıcı düzeltebilir.
- `Clarification` ("Tamamlanması gereken bilgiler", m.22): `questions: [{id, text, why (neden soruyorum, kaynaklı), source_refs[], input: {kind: choice|date|number|text, options: [{value, label}], allow_unknown: true}}]`, `index/total`. "Bilmiyorum" her soruda var. Kullanıcı soruları atlayabilir → cevap `conditional` döner.
- `Answer`:
  - `status`: `definite` | `conditional` (Net / Koşullu) + `status_note` ("Verdiğiniz bilgilere göre").
  - `headline`: tek cümle sonuç.
  - `fact_chips`: cevabın dayandığı bilgiler (etiket; dokununca düzenlenir).
  - `points: [{text, citations: [CitationRef]}]` (kısa mod: ilk N nokta; ayrıntılı: hepsi).
  - `missing_info`: koşullu cevapta neye göre değişeceği (koşul → sonuç).
  - `holding_map` (gerekçeli mod): `[{condition, condition_quote, citation, fact_value, result: met|not_met|not_applicable|unknown}]` + `reasoning_summary`.
  - `calculations`: v1'de yalnız `{title, needs: [...]}` ("brüt ücret gerekli"); hesap motoru v2.
  - `read_sources`: okunanlar (harness iz kaydından, model yazmaz): `{statute_articles: n, decisions: n, admin_acts: n, items: [CitationRef]}`.
  - `applied_law_date` + metin ("03.10.2026 tarihinde yürürlükte olan metin").
  - `disclaimer`: sabit "Hukuki görüş değildir."
- `CitationRef`: `{source_id, category, label (ör. "4857 sayılı İş Kanunu m.18/1"), ref (künye), review_status: approved|analyzed, verification: verified|unverified|not_applicable, valid_from, valid_to, quote?, char_start?, char_end?}`. Tıklanınca tam metin açılır, ilgili kısım vurgulanır (tasarım kararı): bu yüzden konum alanları.
- Akış olayları (SSE, `ChatEvent`): `step` (ör. "Kaynaklar okunuyor", düğüm adı), `facts`, `clarification`, `answer`, `error` (hata kodu, `app/errors.py` kalıbı), `done`.
- Konuşma kayıtları: `Conversation {id, title, created_at, updated_at}`, `Turn {id, role: user|assistant, text?, facts?, clarification?, answer?, trace_id?}`.
- Geri bildirim: `Feedback {turn_id, rating: up|down|null, point_index?, kind: wrong_source|wrong_conclusion|missing|unclear|other, comment, correction}`.

### 2. API sözleşmesi (yalnız OpenAPI + stub, `app`)

- `POST /chat/conversations` → yeni konuşma. `GET /chat/conversations`, `GET /chat/conversations/{id}`.
- `POST /chat/conversations/{id}/messages` (soru ya da netleştirme cevapları, `mode`) → `text/event-stream` `ChatEvent`'ler.
- `POST /chat/turns/{id}/feedback`.
- Bu görevde endpoint'ler **fixture** döner: `CHAT_BACKEND=fixture` iken `eval/fixtures/` altındaki elle hazırlanmış üç vaka (SB-001 işe iade, SB-016 idari para cezası, SB-026 geriye dönük hizmet) senaryoya göre akar (soru → olay → netleştirme → cevap). Kalıcılık yok (bellek içi). Gerçek ajan Görev 17'de.
- Yeni rol: `user` (`UserRole`, migration). `/chat/*` tüm roller; mevcut dashboard endpoint'leri `user` rolüne kapalı (test). Kullanıcıyı admin oluşturur (davet, kayıt yok; mevcut kullanıcı oluşturma akışı).
- OpenAPI'den TS tipleri üretilir (`frontend-ui` skill'indeki komut).

### 3. Eval seti v0 (`eval/cases/`, repo'da, JSON/YAML)

- Soru bankası ve konu kartlarından **makine okur vaka formatı**: `{id: "SB-001", question (aynen), event_date?, expected: {status, headline_contains[], must_cite: [künye], must_ask: [netleştirme konusu], must_not: [ifade/kaynak], traps[]}, tags}`.
- Bu görevde ilk **10 vaka** (Themis hazırlar: SB-001, SB-016, SB-026 + 7 tane). Kalan ~33 vaka ayrı küçük PR'larla. Repo public: kişi adı yok; soru metni "aynen" ama ad/kurum geçerse maskelenir.
- Puanlayıcı iskeleti `eval/score.py`: bir `Answer` JSON'u + vaka → deterministik metrikler: `must_cite` kapsama, atıf geçerliliği (künye `CitationRef` listesinde), `must_ask` kapsama (netleştirme sorularında), "-iyor" kipi taraması, `disclaimer` var mı. LLM hakemi v1 sonu.
- Fixture cevapları puanlayıcıdan geçer (kendi testimiz: fixture'lar tam puan almalı).

## Kapsam dışı

- Ajan, LLM çağrısı, kalıcı konuşma tabloları (Görev 17/18).
- Web arayüzü (Görev 16).
- Hesap motoru, eskalasyon, dilekçe teklifi.

## Kabul kriterleri

- `make lint`, `make typecheck`, `make test` yeşil.
- Şema birim testleri: her fixture `Answer`/`ChatEvent` olarak doğrulanır; `conditional` cevapta `missing_info` boş olamaz; `definite` cevapta `unknown` olgu kalamaz (validator).
- `curl -N` ile `POST .../messages` SB-001 fixture akışını SSE olarak döker (çıktı PR'da).
- `user` rolüyle `/review/*` 403, `/chat/*` 200 (test).
- `python eval/score.py eval/fixtures/SB-001.answer.json eval/cases/SB-001.yaml` metrikleri basar; üç fixture tam puan.
- TS tipleri üretilmiş ve commit'li.

## Notlar Claude Code için

- Şema adları İngilizce, kullanıcıya görünen metinler Türkçe (fixture'larda).
- Fixture içerikleri konu kartlarından (`/opt/data/projects/hukuk-yz/konu-kartlari/SB-*.md`, repo dışı) Themis tarafından hazırlanıp `eval/fixtures/` altına verilir; hukuki metin uydurulmaz.
