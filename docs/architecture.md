# Mimari v0.1

Durum: taslak, 2026-10-02. Karar sahibi: Orhan. Yazan: Themis.
Spec referansları (`md. N`) `docs/requirements-raw.txt`'deki 37 maddeye işaret eder.

## 1. Hedef

Türk iş ve sosyal güvenlik hukuku için, mali müşavir / İK / avukat kullanan, **doğrulanmış kaynağa dayanmayan hiçbir hukuki cevap üretmeyen** bir asistan. LLM muhakeme eder, ama kaynak üretmez (md. 25), hesap yapmaz (md. 29), tarihsiz konuşmaz (md. 4).

## 2. Servisler

Altı parça. Üçü uygulama servisi, biri yardımcı servis, biri konfigürasyon, biri frontend çifti.

| Servis | Teknoloji | Sorumluluk | Durum |
|---|---|---|---|
| `web` | Next.js (TS) | Kullanıcı chat arayüzü: atıf chip'leri, kesinlik rozeti, gerekçe zinciri, eksik bilgi bloğu | Faz 3 |
| `dashboard-web` | Next.js (TS) | Admin: veri yükleme ve inceleme/onay akışı, KB arama, org/kullanıcı, AI tüketim ve maliyet | Faz 1 |
| `proxy` | Traefik | TLS, routing, ForwardAuth. Kod değil konfig; k8s'te Ingress + Middleware olur | Faz 3 |
| `app` | FastAPI (Py) | **Veri sahibi.** Auth, org/kullanıcı, dosya (case), KB CRUD + arama, atıf çözümleme, hesap motoru, kanallar (web, Telegram), maliyet, ödeme. Aynı kod `worker` olarak ikinci süreç | Faz 1 |
| `agent` | LangGraph (Py) | md. 33 muhakeme zinciri. **Durumsuz**; KB, atıf, hesap için `app`'i, bağlam için `memory`'yi çağırır. LLM gateway burada | Faz 2 |
| `memory` | FastAPI (Py) | Generic bellek servisi: `store / recall / forget / summarize`, scope (`tenant / user / case`), bitemporal. Domain bilmez. İleride siestai altında ayrışabilir | Faz 2 |

### Sınır kuralları

1. **`app` Postgres'in tek yazarıdır.** `agent` kendi tablosu tutmaz (LangGraph checkpoint hariç). `memory` kendi şemasına yazar, `app` tablolarına dokunmaz.
2. **`agent` kanal bilmez.** Web, Telegram, ileride WhatsApp hepsi `app`'in kanal adaptörlerinden geçer; `agent` tek bir `POST /run` görür.
3. **Hukuk mantığı framework'ten bağımsız.** Muhakeme adımları, atıf çözümleme, hesap motoru saf Python paketleri (`packages/`); LangGraph sadece orkestrasyon. Framework değişirse paketler kalır.
4. **Servisler arası iletişim HTTP + JSON**, şemalar Pydantic ile paylaşılır (`packages/models`). NATS gelince event'ler eklenir, senkron çağrılar kalır.

## 3. Monorepo düzeni

```
hukuk-yz/
  services/
    app/          FastAPI; app/ (api, auth, kb, channels, billing), worker/ (jobs)
    agent/        LangGraph graph, LLM gateway, prompt'lar
    memory/       generic memory API
    web/          Next.js
    dashboard-web/ Next.js
  packages/
    models/       Pydantic şemaları, paylaşılan enum'lar
    ingest/       tip tespiti, metin çıkarma, temizleme, parser'lar
    citation/     atıf ayrıştırma + çözümleme
    calc/         deterministik hesap motoru (kıdem, ihbar, İPC, PEK...)
    memory-client/ memory servisinin Python istemcisi
    ui/           ortak React bileşenleri + design token'lar
  infra/
    compose/      lokal docker-compose
    traefik/      proxy konfig
    helm/         Faz 3
  docs/
  data/           gitignored (ham veri symlink'i)
```

Python tarafı `uv` workspace; her servis ve paket kendi `pyproject.toml`. Frontend `pnpm` workspace.

## 4. Veri akışları

### 4.1 Soru → cevap

```
kullanıcı (web / Telegram)
  → proxy (ForwardAuth: app /auth/verify, X-User / X-Org header)
  → app  POST /chat        (case'i yükler, maliyet kaydı açar)
  → agent POST /run        (soru + case bağlamı)
      agent → memory  recall(scope=case)
      agent → app     GET /kb/search, GET /citation/resolve, POST /calc/*
      agent → LLM gateway → model (EU region)
      agent ↔ interrupt (eksik bilgi sorusu / eskalasyon) → app → kullanıcı
  ← cevap: {text, citations[], certainty, reasoning_chain[], missing_info[], cost}
  app → atıf kapısı (madde 5.1) → kaydet → kanal adaptörü → kullanıcı
```

### 4.2 Yükleme → KB

```
dashboard-web  upload (dosya/klasör/URL)
  → app  POST /ingest/jobs   (kuyruğa yazar)
  → worker  tip tespiti → metin çıkarma → temizleme → parse → normalize → QA raporu
  → app  kayıt durumu: taslak → analiz_edildi
dashboard-web  inceleme ekranı: çıkarılan alanlar, güven skoru, uyarılar
  → insan: onayla / düzelt / reddet
  → app  durum: onaylandı → yayında   (embedding + tsvector burada üretilir)
```

İnsan onayı atlanamaz. Parser ne kadar iyi olursa olsun, yayına giren her kayıt bir kişinin adını taşır (provenance). Ayrıntı: `docs/data-model.md`.

## 5. Spec eşlemesi

| Madde | Gereksinim | Nerede karşılanıyor |
|---|---|---|
| md. 4 | Olay tarihindeki hukuk | KB bitemporal; `citation/resolve?ref=…&date=…` o tarihteki sürümü döner |
| md. 9, 10 | Kaynak hiyerarşisi tek boyutlu değil; mevzuat kümesi dinamik | `agent` adım 8-14; `kb` kaynak türü + otorite alanları |
| md. 15-18 | Yargı otoritesi ağırlığı, sayısal çoğunluk değil | karar kaydında `court_level`, `decision_kind`; agent adım 17-23 |
| md. 20 | Karar metni ≠ özet | kayıtta `full_text` ve `editorial_summary` ayrı; özet "editoryal" etiketli, ÖZETİ kaynak gösterilmez |
| md. 22 | Eksik bilgide varsayım yok | agent adım 6 ve 27; `interrupt` ile soru; cevapta `missing_info[]` |
| md. 23 | Kesinlik düzeyi | cevapta `certainty` enum: açık_norm / bağlayıcı_karar / yerleşik_içtihat / tartışmalı / eksik_bilgi |
| md. 25 | Uydurma kaynak yasak | **Atıf kapısı** (5.1). Çözümlenemeyen atıf cevaptan düşer veya `unverified` etiketi alır; test edilebilir, agent'tan bağımsız |
| md. 26 | Birincil kaynak önceliği | kayıtta `source_rank`: resmi/birincil > ikincil; arama sıralamasında ağırlık |
| md. 28 | 8 kaynak kategorisi karışmaz | ayrı tablolar, ortak `source` üst tablosu; tek vektör havuzu yok, arama kategori filtreli |
| md. 29 | Hesap ayrı katman | `packages/calc`; LLM parametre çıkarır, motor hesaplar, adımlar cevapta gösterilir; Excel'ler test oracle |
| md. 31 | KVKK | DB EU'da; LLM çağrısı EU region; case belgeleri şifreli; silme hakkı için `memory.forget` + case silme |
| md. 32 | Telif | her kaynakta `license` alanı; Çalışma ve Toplum özetleri izin gelene kadar `internal_only` |
| md. 33 | 31 adımlı muhakeme | LangGraph düğümleri; her adım kendi atıflarıyla `reasoning_chain`'e yazar |
| md. 35 | Gerekçe zinciri | cevap şemasında `reasoning_chain[]`; UI'da açılır blok |

### 5.1 Atıf kapısı

`app` içinde, cevap kullanıcıya gitmeden önce:

1. Metinden atıfları ayrıştır (`packages/citation`): kanun/madde, karar (mahkeme + E/K + tarih), genelge/tebliğ no, uluslararası sözleşme.
2. Her atfı KB'de çözümle; mevzuat için olay tarihi parametresi ile.
3. Sonuç: `verified` (KB'de, yayında) / `unverified` (bulunamadı) / `external` (web kaynaktan, KB'de değil).
4. Politika (konfigüre edilebilir): `unverified` atıf içeren cümle düşer, ya da etiketle gösterilir. Varsayılan: etiketle + UI'da uyarı. Atıfsız kalan cevap "kaynaksız" bandı alır.
5. Her kapı kararı loglanır; eval setinin bir metriği budur.

## 6. Altyapı

- **Lokal:** `docker compose` (Postgres, app, worker, agent, memory, iki Next.js). Tek komutla ayağa kalkar.
- **Hedef:** Kubernetes. 12-factor baştan: config env'den, stateless süreçler, stdout log, graceful shutdown, `/healthz` + `/readyz` her serviste. Helm chart Faz 3.
- **Postgres** cluster dışında; pgvector + tsvector + pg_trgm. LangGraph checkpoint (`PostgresSaver`), kuyruk ve memory şeması aynı instance, ayrı şemalar.
- **Kuyruk:** Postgres tabanlı (`SELECT … FOR UPDATE SKIP LOCKED`) Faz 1; NATS Faz 2 (event'ler: `ingest.completed`, `escalation.requested`, `kb.published`).
- **LLM gateway:** `agent` içinde ince katman (LiteLLM değerlendirilecek); her çağrı `org, user, case, model, tokens, cost` ile loglanır; `app` bu log'u maliyet raporuna çevirir.
- **Secrets:** env; k8s'te Secret/external-secrets. Kod ikisini ayırt etmez.
- **Ödeme:** iyzico veya PayTR (Stripe TR'de merchant olarak çalışmıyor). Abonelik + eskalasyon kredisi. e-Fatura entegrasyonu Faz 3'te araştırılır.

## 7. Dil ve araçlar

- Backend: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, uv, ruff, mypy, pytest.
- Frontend: TypeScript, Next.js (son LTS), pnpm, Tailwind, shadcn/ui üstüne `packages/ui`.
- **UI kuralı:** renk, tipografi, spacing yalnızca design token (CSS değişkeni + Tailwind theme) üzerinden. Bileşende hardcode renk yok. Design system günü token dosyası değişir, bileşenler değişmez.
- CI: ruff + mypy + pytest + eslint + tsc her PR'da. Eval seti Faz 2'den itibaren CI'da.

## 8. Açık kararlar

| Konu | Seçenekler | Öneri | Karar |
|---|---|---|---|
| Hesap motoru ve atıf kapısı nerede | `app` / `agent` | `app` (veriyle beraber, bağımsız test, dashboard'dan da çağrılır); `agent` performans gerekirse paketi lokal import eder | bekliyor |
| Çalışma ve Toplum özetleri | izin iste / kullanma / sadece iç kullanım | izin iste; gelene kadar `internal_only` | toplantı |
| LLM sağlayıcı ve bölge | Anthropic/OpenAI direkt / Bedrock-Vertex EU | EU region zorunlu; sağlayıcı eval'e göre | toplantı |
| İsim/marka | aday listesi | ayrı doküman | toplantı |
| Kaynak site listesi | ortaklardan | her site için crawler + değişiklik takibi | toplantı |
| Üst mahkeme toplama kriterleri | Baran | konu, tarih aralığı, öncelik | toplantı |

## 9. Diyagram

`docs/architecture-v0.1.svg`
