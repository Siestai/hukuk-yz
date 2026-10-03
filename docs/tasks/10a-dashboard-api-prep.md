# Görev 10a: Dashboard için API hazırlığı (hata kodları, giriş sınırı, PDF)

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/tasks/08-auth.md` (oturum, `require_role`, rate limit kararı), `docs/tasks/09-review-api.md` (inceleme endpoint'leri), `docs/decisions.md` 2026-10-03 (arayüz kuralları: i18n, hata kodu), `.claude/skills/frontend-ui`, `.claude/skills/db-migration`.
Skill'ler: `task-pr-hygiene`, `db-migration`.

## Neden şimdi

Dashboard `hukuk-dashboard.siestai.com` adresinde internete açılacak (Orhan, 2026-10-03). Görev 08'de giriş denemesi sınırı "internete açılmadan önce" diye ertelenmişti; şimdi o an. Ayrıca i18n kararı API'nin kullanıcıya metin değil kod dönmesini, detay ekranında PDF gösterme kararı da dosya sunan bir endpoint'i gerektiriyor. Üçü de UI yazılmadan önce API'de olmalı.

## Hedef

`app` API'sinde üç değişiklik: (1) bütün hatalar sabit bir hata koduyla döner; (2) giriş denemeleri sınırlanır; (3) bir karar extraction'ının orijinal PDF'i yetkili kullanıcıya sunulur.

## Kapsam

1. **Hata kodları.**
   - Ortak hata gövdesi: `{"error": {"code": "<snake_case>", "params": {...}}}`. `params` çeviride kullanılacak değerleri taşır (örn. `{"total": 41, "expected": 40}`). Kullanıcıya yönelik Türkçe/İngilizce metin gövdede **yok**.
   - `ApiError(status, code, params)` istisnası + FastAPI exception handler. `HTTPException(detail="...")` kullanan bütün yerler (`auth.py`, `review.py`, varsa diğerleri) buna geçer.
   - Pydantic doğrulama hataları (422) `validation_error` koduna, `params.fields` alan listesine çevrilir.
   - Kod listesi `packages/models` içinde tek bir enum (`ErrorCode`); OpenAPI şemasında görünür, böylece UI tipleri bundan üretir. En az: `unauthorized`, `forbidden`, `unsupported_media_type`, `validation_error`, `not_found`, `extraction_not_found`, `review_conflict` (kaynak artık beklemede değil / extraction en yenisi değil), `decision_conflict` (+ `params.decision_id`), `bulk_count_changed` (+ `total`, `expected`), `bulk_band_not_allowed`, `too_many_attempts` (+ `retry_after`), `file_not_found`, `file_not_previewable`.
   - Mevcut testler gövde yerine koda bakacak şekilde güncellenir.
2. **Giriş denemesi sınırı.**
   - Alembic 0007: `login_attempt` (id, email (normalize), ip, succeeded bool, attempted_at). İndeksler `(email, attempted_at)` ve `(ip, attempted_at)`. Kalıcı tablo, çünkü `app` birden çok kopya çalışabilir (12-factor; bellek içi sayaç yetmez).
   - Kural: son 15 dakikada aynı e-posta için 5 başarısız deneme **veya** aynı IP'den 20 başarısız deneme varsa `POST /auth/login` 429 `too_many_attempts` döner, `Retry-After` başlığı ve `params.retry_after` (saniye) ile. Sınırdayken doğru parola da 429 alır. Başarılı giriş o e-postanın sayacını sıfırlamaz; pencere kayar. Eşikler ayarla değiştirilebilir (`LOGIN_MAX_FAILS_PER_EMAIL=5`, `LOGIN_MAX_FAILS_PER_IP=20`, `LOGIN_WINDOW_MINUTES=15`).
   - Var olmayan e-posta da sayılır (kullanıcı varlığı sızmasın; Görev 08'deki sabit süreli doğrulama korunur).
   - İstemci IP'si: `request.client.host`. `app` doğrudan internete açılmaz; dashboard üzerinden gelir. Uvicorn `--proxy-headers` ve `FORWARDED_ALLOW_IPS` ayarı ile yalnız güvenilen proxy'nin `X-Forwarded-For`'u kabul edilir; varsayılan güvenilen proxy yok. `.env.example`'a eklenir.
   - 30 günden eski satırlar `python -m app.users prune-login-attempts` ile silinir (cron'a bağlamak deploy işi).
3. **PDF sunma.**
   - `GET /review/decisions/{extraction_id}/file`, `require_role("reviewer")`.
   - Dosya yolu: `ARCHIVE_ROOT` (yeni ayar, mutlak yol, salt okunur bağlanması beklenir) + `ingest_file.path`. `ingest_file.path`'in arşiv köküne göre göreli tutulduğu doğrulanır; değilse görev bunu belgeleyip normalize eder.
   - Güvenlik: çözülen yol `ARCHIVE_ROOT` dışına çıkarsa (`..`, symlink) 404 `file_not_found`. Dosyanın sha256'sı `ingest_file.sha256` ile uyuşmazsa 404 `file_not_found` + uyarı logu (yanlış dosya göstermektense hiç gösterme).
   - Yalnız `detected_type = pdf` sunulur; diğerleri (2 eski `.doc`, html taslakları) 415 `file_not_previewable`.
   - Yanıt başlıkları: `Content-Type: application/pdf`, `Content-Disposition: inline; filename="<sha256>.pdf"` (dosya adında kişi/kurum adı olmasın), `Cache-Control: private, no-store`, `X-Content-Type-Options: nosniff`. Dosya akış olarak gönderilir (`FileResponse`).
   - `ARCHIVE_ROOT` ayarlı değilse endpoint 404 `file_not_found` döner, uygulama açılmaya devam eder.
   - Telif notu (docstring): arşiv PDF'leri Çalışma ve Toplum'un sayfalarıdır; yalnız giriş yapmış reviewer'lara, iç inceleme için sunulur.

## Kapsam dışı

- Arayüz (Görev 10b, 10c).
- CAPTCHA, hesap kilitleme, e-posta bildirimi.
- PDF'i S3/obje deposuna taşıma; dosya sistemi yeter.
- Mevzuat dosyalarının sunulması (yalnız karar extraction'ları).

## Kabul kriterleri (Themis koşar)

1. `make lint`, `make typecheck`, `make test` yeşil; CI yeşil (DB testleri CI'da).
2. `grep -rn "HTTPException(" services/app/app` yalnızca handler'ın kendisinde ya da hiç çıkmaz; kullanıcıya dönen hiçbir hata gövdesinde serbest metin yok (testler `error.code`'a bakar).
3. OpenAPI şemasında `ErrorCode` enum'u ve hata gövdesi şeması var (`/openapi.json` testte okunur).
4. Rate limit testleri: 5. başarısız denemeden sonra aynı e-posta 429 + `Retry-After`; farklı e-posta aynı IP'den 20'ye kadar geçer; pencere dışına çıkan denemeler sayılmaz (zaman enjekte edilerek); sınırdayken doğru parola da 429.
5. PDF testleri: doğru dosya 200 + başlıklar; `..` / symlink ile kök dışı 404; sha256 uyuşmazlığı 404; `.doc` 415; reviewer olmayan / oturumsuz 401/403; `ARCHIVE_ROOT` yok 404.
6. Migration 0007 için `test_orm_consistency.py` ve `test_schema.py` genişletildi; `downgrade` çalışıyor.

## Notlar Claude Code için

- Hata kodu dönüşümü mekanik ama geniş; davranışı (durum kodları, transaction sınırları) değiştirme, sadece gövdeyi.
- Rate limit sayımı ve kontrolü login ile aynı transaction'da; başarısız deneme kaydı, doğrulama hatası dönülmeden önce commit edilir.
- Testler modül adına göre: `test_auth.py`, `test_review.py`, yeni bir modül açılırsa onun adıyla (`test_errors.py`).
- Commit et, push etme.
