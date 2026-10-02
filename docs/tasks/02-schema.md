# Görev 02: Alembic şeması v0.1

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/data-model.md` (tamamı; §3, §4, §5, §8, §10 bağlayıcı). Üstüne oturduğu iş: Görev 01 (iskelet, boş `0001_init`).

## Hedef

`alembic upgrade head` ile `data-model.md` §10'daki Faz 1 tablolarının Postgres'te oluşması; SQLAlchemy 2 ORM modelleri `packages/models`'ta değil `services/app/app/models/` altında (veri sahibi `app`); Pydantic şemaları sonraki görevlerde.

## Kapsam

1. **Postgres eklentileri:** migration başında `CREATE EXTENSION IF NOT EXISTS vector`, `unaccent`, `pgcrypto` (uuid için `gen_random_uuid()`).
2. **Enum'lar** (Postgres native enum, adları `snake_case`): `source_category` (A..H harfleri yerine anlamlı: `statute, treaty, decision, admin_act, collective_agreement, case_document, doctrine, calc`), `source_rank`, `license`, `record_status` (`draft, analyzed, approved, published, superseded, withdrawn, failed, rejected`), `ingest_kind`, `ingest_status`, `review_decision`, `court`, `court_level`, `jurisdiction`, `text_completeness`, `verification`, `change_kind`, `statute_kind`, `admin_issuer`, `admin_kind`, `chunk_kind`.
3. **Ortak tablolar (§3):** `source`, `ingest_job`, `ingest_file`, `extraction`, `review`. Provenance alanları bir SQLAlchemy mixin (`ProvenanceMixin`: `source_id, extraction_id, review_id, recorded_at, superseded_at, recorded_by`).
4. **Mevzuat (§5.1):** `statute`, `statute_article`, `statute_article_version` (bitemporal: `valid_from date not null`, `valid_to date null`).
5. **Karar (§5.2):** `decision` tüm alanlarıyla; `verification` enum + `verification_source, verification_ref, verified_at`; `tsv tsvector` generated column (`to_tsvector('turkish', unaccent(coalesce(full_text,'')))`) ve GIN indeksi. `unaccent` immutable olmadığı için generated column yerine trigger ya da `simple` + ayrı uygulama güncellemesi kabul edilir; seçimi migration yorumunda gerekçelendir.
6. **İdari düzenleme (§5.3):** `admin_act`, `admin_act_version`.
7. **Diğer kategoriler (§5.4):** `treaty`, `treaty_article_version`, `collective_agreement`, `ca_article_version`, `doctrine`, `calc_method`, `calc_parameter_version`. Minimal alan seti: id, source_id, başlık/kimlik, `*_version`'larda text + valid_from/valid_to + provenance. `case_document` **oluşturulmaz** (F, KB dışı, ayrı görev).
8. **Chunk (§8):** `chunk` tablosu; `embedding vector(1024)` (boyut sabiti `settings`'te değil migration'da; model seçimi sonra, gerekirse yeni migration), `embedding_model text`, `tsv tsvector` + GIN, `(parent_kind, parent_id)` indeksi, `(category, kind, license)` indeksi. HNSW indeksi **bu görevde yok** (veri yokken anlamsız).
9. **İndeks ve kısıtlar:** `source.status` indeks; `decision (court, chamber, esas_no, karar_no)` unique partial (`WHERE superseded_at IS NULL`); `statute_article (statute_id, article_no)` unique; `statute_article_version` için `EXCLUDE USING gist (article_id WITH =, daterange(valid_from, valid_to) WITH &&) WHERE (superseded_at IS NULL)` (çakışan sürüm yasak; `btree_gist` eklentisi gerekir); aynı exclude `admin_act_version` ve `calc_parameter_version`'da. `ingest_file.sha256` indeks (tekrar yükleme tespiti).
10. **Çok kiracılık hazırlığı:** `source.org_id uuid null` (null = ortak KB; §11 önerisi). `org` tablosu **bu görevde yok**, FK sonra.
11. **ORM:** `app/models/__init__.py` + modül başına bir dosya (`common.py`, `statute.py`, `decision.py`, `admin_act.py`, `misc.py`, `chunk.py`). `DeclarativeBase` + `Mapped[]` tipli. Alembic `env.py` `target_metadata` buna bağlanır; `alembic check` temiz olmalı (model ile migration farkı yok).
12. **Migration:** tek dosya `0002_kb_schema_v0_1.py`, elle yazılmış ve okunabilir (autogenerate çıktısı temizlenmiş); `downgrade` tam çalışır.
13. **Testler** (`services/app/tests/test_schema.py`, DB gerektirir, CI'da koşar):
    - upgrade head → tüm tablolar var; downgrade base → yok; tekrar upgrade.
    - `alembic check` fark yok.
    - Bitemporal exclude: aynı maddeye çakışan iki sürüm insert → `IntegrityError`.
    - `decision` unique partial çalışıyor; superseded kayıt varken yeni insert serbest.
    - `chunk.embedding` 1024 boyutlu vektör insert/select.
14. **Makefile:** `make migrate` (upgrade head), `make migration name=...` (autogenerate taslak), `make db-reset` (compose'da volume sil + up + migrate).

## Kapsam dışı

- Veri yükleme, parser, API endpoint'leri, Pydantic şemaları, HNSW indeksi, `org`/`user` tabloları, `case_document`, memory şeması, RLS.
- `docs/` değişikliği (model ile doküman çelişirse **dokümanı değiştirme**, PR açıklamasına "doküman güncellemesi gerekir" notu düş).

## Kabul kriterleri (Themis koşar)

- [ ] `make lint`, `make typecheck`, `make test` temiz (DB testleri CI'da; lokal Postgres yoksa skip).
- [ ] CI yeşil, `test_schema.py` CI'da gerçekten koştu (skip değil).
- [ ] `alembic upgrade head && alembic downgrade base && alembic upgrade head` CI'da hatasız.
- [ ] `alembic check` temiz.
- [ ] Migration dosyası okunabilir; her tablo için `data-model.md` bölüm referansı yorumda.
- [ ] Toplam tablo sayısı: 20 ± 2 (sayı PR'da).

## Notlar Claude Code için

- Alan adları `data-model.md`'deki gibi; Türkçe alan adı yok (`esas_no`, `karar_no` kalır, bunlar terim).
- Her `*_version` tablosunda `valid_from <= valid_to` CHECK.
- `recorded_at` default `now()`, `superseded_at` null.
- `uuid` PK, `gen_random_uuid()` server default.
- Timestamp'ler `timestamptz`.
- İngilizce kod/yorum/commit; mesaj: `feat(db): KB schema v0.1 (alembic 0002, ORM models)`.
