# Görev 17: Ajan v1 (`services/agent`, LangGraph)

Durum: uygulandı; gerçek model eval tablosu, CI imaj doğrulaması ve PR onayı beklenmektedir. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/architecture.md` §2 (agent durumsuz, `POST /run`, sınır kuralları), §4.1, §5.1 (atıf kapısı), Themis araştırması "Ana app ajanı: tasarım" (15.10; özet aşağıda), `docs/tasks/14-kb-search.md` (`/kb/search`), `docs/tasks/15-chat-contract-eval.md` (çıktı şeması, eval), gereksinim md. 4, 22, 23, 25, 33.
Skill'ler: `task-pr-hygiene`.

## Karar (Orhan, 2026-10-27)

- Çerçeve: **LangGraph** iskelet (durum, Postgres checkpoint, netleştirme `interrupt`'ı) + düğüm içi tipli LLM çağrıları **Pydantic AI** ile (doğrulama hatasında otomatik tekrar). `deepagents` ana yolda yok.
- Otonom ajan değil: **sabit iş akışı + dar LLM düğümleri.** Adım sırasını, kaynak kapsamını, atıf doğrulamasını ve "okunanlar" kaydını kod tutar; model az ve tipli karar verir.
- Model: düğüm başına env ile seçilir (`AGENT_MODEL_FAST`, `AGENT_MODEL_STRONG`); varsayılan hızlı = Claude Haiku 4.5, güçlü (taslak) = Claude Sonnet 5.5. Sağlayıcı soyut (Pydantic AI model adı), OpenAI'ye geçiş yalnız env.

## Kapsam

`services/agent` (FastAPI + LangGraph). Hukuk mantığı saf modüllerde, graf yalnız orkestrasyon (architecture §2 kural 3).

### Graf (v1: 6 düğüm)

1. **intake (olay kaydı, LLM hızlı):** soru (+ önceki olgular) → `CaseFacts` (konu sınıfı, statü, olay tarihi, olgular `known|unknown`) + `Clarification` adayları. Soru adayları serbest değil: konu sınıfının **olgu şablonundan** (`agent/topics/*.yaml`: her konu için gerekli olgular, seçenekler, "neden soruyorum" metni + dayanak künyesi) seçilir; şablon dışı soru üretilmez. v1 şablonları: eval setindeki konular (işe iade, idari para cezası, hizmet tespiti / geriye dönük hizmet, kıdem-ihbar, yıllık izin; Themis konu kartlarından hazırlar). Şablonu olmayan konu → genel şablon (olay tarihi, statü).
2. **clarify (interrupt):** bilinmeyen kritik olgu varsa graf durur, `clarification` olayı döner; kullanıcı cevaplar veya atlar (`skip=true` → koşullu yola devam). Checkpoint Postgres'te (`agent` şeması), `thread_id = turn zinciri`.
3. **plan (deterministik, LLM yok):** konu sınıfı → zorunlu okuma listesi (şablondaki `must_read`: kanun maddeleri, genelge bölümü) + arama sorguları.
4. **retrieve (deterministik + arama):** `app` `/kb/search` (`as_of` = olay tarihi) ve madde okuma; madde getirilirken komşu fıkralar dahil. Her okunan kaynak iz kaydına (`read_sources`) kod tarafından yazılır.
5. **holding_map (LLM hızlı):** her ilgili hüküm için `{condition, condition_quote, citation, fact_value, result}`. Kod `condition_quote`'un atıf verilen metinde birebir geçtiğini doğrular; geçmeyen satır düşer.
6. **draft + gate (LLM güçlü + kod):** yalnız harita satırları ve okunan kaynak kimliklerinden `Answer` üretir (Görev 15 şeması; üç mod verisi birlikte). Kapı kodla: her `CitationRef` okunan kaynaklar içinde ve olay tarihinde geçerli (değilse düşer, md. 25); "-iyor" kipi taraması (varsa bir kez düzelttirme); bilinmeyen olgu varken `definite` yasak; `disclaimer` ve `applied_law_date` kod ekler. Kapıdan geçemezse bir tekrar, yine geçemezse "doğrulanmış kaynakla cevap verilemedi" cevabı.

### API

- `POST /run` (yalnız `app` çağırır, servis anahtarı ile): `{thread_id, message | clarification_answers | skip, mode}` → SSE `ChatEvent` (`step` olayları düğüm adlarıyla Türkçe etiket).
- `GET /healthz`, `/readyz`.

### İz kaydı

- Her düğüm: girdi özeti, çıktı, model, token, süre, maliyet. Langfuse (OTel) env ile açılır (`LANGFUSE_*`); env yoksa yalnız yapılandırılmış log. `trace_id` cevapla döner.

### Eval koşucusu

- `python -m agent.eval eval/cases` → her vaka için ajanı (netleştirme sorularına vakadaki olgularla otomatik cevap vererek) koşar, `eval/score.py` ile puanlar; tablo: vaka, must_cite kapsama, must_ask kapsama, kapı düşüşleri, token, maliyet, süre. CI'da sahte LLM ile duman testi; gerçek koşu elle.

## Kapsam dışı

- Hesap motoru (v2; v1 yalnız "hangi bilgi gerekli"), uzmana eskalasyon, çürütücü ikinci geçiş, memory servisi, konu kartı eşleme (kart → cevap kısayolu; v2).
- `app` tarafındaki chat endpoint'leri ve kalıcılık (Görev 18).

## Kabul kriterleri

- `ruff`, `mypy`, `pytest` yeşil; graf testleri sahte LLM (Pydantic AI `TestModel`/`FunctionModel`) ve sahte `/kb/search` ile: SB-001 akışı interrupt'ta durur, cevaplar sonrası devam eder; atlama koşullu cevap verir; okunmamış kaynağa atıf kapıda düşer; uydurma alıntılı harita satırı düşer; "-iyor" taraması çalışır.
- Docker image ve compose servisi (`agent`), CI'da build.
- Gerçek LLM ile (Themis, yerel yığın + yerel KB örneği) 3 vaka eval koşusu, tablo PR'da; doğrulanamayan açıkça yazılır.

## Uygulama notları (şemadan sapmalar)

- **Komşu fıkralar (graf 4. madde):** `app`'te `/statutes/{number}/articles/{article_no}?as_of=` okuma endpoint'i vardır, ancak oturum ister ve yalnız yayımlanmış maddeleri okur. Agent v1 bu endpoint'e henüz bağlı değildir; zorunlu maddeyi madde künyesiyle (`4857 m.18`) arar ve yalnız aramanın döndürdüğü parçaları okur. Tam madde/komşu fıkra okuması, servis anahtarı desteği ve arama kayıtlarının okuma endpoint'iyle eşlenmesi Görev 18'de tamamlanacaktır; v1 tam fıkra kapsamı garantisi vermez.
- **`/kb/search` kimliği:** Görev 14 sözleşmesi oturum ister; agent `X-Service-Key` gönderir. Servis anahtarı ile çağrıyı kabul etmeyi Görev 18 `app` tarafına ekler (`18-chat-wiring.md`); o zamana kadar agent yalnız fixture KB (`--kb fixtures`) ile çalışır.
- **Fıkra (`sub`):** model fıkra adı verebilir; kod yalnız okunan metinde satır başındaki sayısal fıkra işaretini (`(1)`) ve alıntının aynı fıkrada geçtiğini doğrularsa atıfa yazar. Bentler ve doğrulanamayan fıkralar için atıf madde düzeyinde kalır.
- **Okunanlar:** modele gösterilen metin kaynak başına en çok 6000 karakterdir; "okunanlar" yalnız modele gösterilen metni sayar. Zorunlu kaynak bu sınırda kesilirse okunamayanlar listesinde de görünür.
- **Okunamayan zorunlu kaynak:** cevap `definite` olamaz; `status_note` okunamayan kaynakları yazar.
- **Olay tarihi:** modelin verdiği tarih (olgu içindeki tarih dahil), soru metninde geçmiyorsa veya gelecekteyse bilinmiyor sayılır ve sorulur. Yeni olay tarihi şablondaki tarih olgusuyla birlikte güncellenir. Açık bilinmiyor/geçersiz/çelişkili düzeltme önceki tarihi geri getirmez; tarih verilmemiş tur önceki olguyu korur. Gelecekteki netleştirme tarihi de bilinmiyor kalır.
- **Hata kodu:** doğrulanmış cevap üretilemezse `answer_not_verified` hata olayı ve `done` gönderilir (Görev 15 sözleşmesi); kod ortak `ErrorCode` listesindedir.
- **Eval koşucusu:** `FixtureKb`, `--kb`, `--case`, `--json` şema dışıdır; PR açıklamasında listelenir.

- **Fixture KB sınırı:** `eval/fixtures/*.answer.json` içindeki alıntılar, alıntıdaki özgün metin ve konumla kullanılır; fıkra işareti uydurulmaz. Bu parçalar tam madde/karar metni değildir; eksik zorunlu kaynaklar cevabı koşullu kılar. Gerçek modelle bu fixture KB üzerinde üç vaka koşusu ayrıca yetkilendirilip yapılacaktır; bu koşu gerçek HTTP KB bütünleşmesini doğrulamaz.
- **İz kaydı mahremiyeti (md. 31):** kullanıcı sorusu yerine karakter sayısı kaydedilir. Sağlayıcı hata metni/traceback istemi içerebileceğinden hata logunda yalnız hata sınıfı bulunur. Kapının ayrıntılı geri bildirimi yalnız iç durumda ve modelin tekrar isteminde tutulur; düğüm loguna sabit hata kodları ve adetleri, düşen atıf/nokta/satır sayıları, deneme sayısı ve fallback bilgisi yazılır.

- **Geçerlilik sınırı (md. 4):** Görev 14 ile aynı aralık kullanılır: `valid_from <= as_of < valid_to`; bitiş günü eski sürüm atıfta kullanılamaz.
