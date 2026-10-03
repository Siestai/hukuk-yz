# Görev 08: Kullanıcı ve oturum (basit auth)

Durum: onaylandı (iki rol ve 12 saat: Orhan, 2026-10-03). Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/architecture.md` §2 (`app` auth'un sahibi), `docs/data-model.md` §3 (`review.reviewer_id`), §11 (org tablosu sonra), `docs/roadmap.md` Faz 1 hafta 3-4 ("auth (basit, org/kullanıcı)").

## Neden şimdi

Dashboard'un ilk ekranı inceleme/onay kuyruğu olacak (Görev 09 API, Görev 10 UI). Onayın provenance'ı bir kişi ister (`review.reviewer_id`, data-model §1 kural 3-4); bugün bu alan CLI'dan elle verilen bir UUID. Kimlik olmadan ne onay API'si ne dashboard yazılabilir. Mevzuat sürümleme (eski plandaki "Görev 08") bu üçünün arkasına kayar.

## Hedef

Az sayıda iç kullanıcının (Faz 1: Orhan, Baran, İbrahim) e-posta + parola ile giriş yaptığı, sunucu tarafında oturum tutan, rol kontrollü en küçük auth katmanı. Kayıt formu, e-posta, SSO yok; kullanıcıyı CLI açar.

## Kapsam

1. **Şema (Alembic 0005):**
   - `app_user`: id uuid, email (benzersiz, küçük harfe normalize edilerek saklanır), display_name, role enum `user_role` = `admin` / `reviewer`, password_hash, is_active (default true), created_at, last_login_at?.
   - `user_session`: id uuid, user_id FK, token_hash (benzersiz; ham token DB'de tutulmaz), created_at, expires_at, revoked_at?, last_seen_at?.
   - `review.reviewer_id` için `app_user.id`'ye FK **eklenmez** bu görevde (CLI ile yazılmış eski review'lar ve testler kırılmasın); Görev 09'da değerlendirilir, PR'da not.
   - ORM modelleri `services/app/app/models/` altında, `test_orm_consistency.py` kalıbına uyar; `data-model.md`'ye kısa bir §3 alt başlığı eklenir.
2. **Parola:** argon2id (`argon2-cffi`, tek yeni bağımlılık). En az 12 karakter. Hash parametreleri kütüphane varsayılanı. Doğrulama sonrası `check_needs_rehash` ise hash güncellenir.
3. **Oturum:** `secrets.token_urlsafe(32)` ile opak token; DB'de SHA-256'sı. Süre `SESSION_TTL_HOURS` (varsayılan 12), her istekte süre uzatılmaz (sabit süre, basit). Token iki yoldan kabul edilir:
   - Cookie `hukuk_session`: HttpOnly, SameSite=Lax, Path=/, `Secure` `COOKIE_SECURE` ayarıyla (varsayılan true; dev'de false verilebilir).
   - `Authorization: Bearer <token>` (CLI, test, ileride agent).
4. **Endpoint'ler** (`app.auth` modülü, FastAPI router):
   - `POST /auth/login` `{email, password}` → 200 + cookie + `{user}`; yanlış e-posta, yanlış parola ve pasif kullanıcı aynı 401 ve aynı mesaj (kullanıcı varlığı sızmaz). Kullanıcı yoksa da sahte bir hash doğrulaması yapılır (zamanlama farkı olmasın). `last_login_at` güncellenir. Yanıt gövdesinde token da döner (Bearer kullanımı için).
   - `POST /auth/logout` → oturum `revoked_at`, cookie silinir; 204.
   - `GET /auth/me` → `{id, email, display_name, role}`.
   - Paylaşılan şemalar (`LoginRequest`, `UserOut`) `packages/models`'e.
5. **Bağımlılıklar (dependency):** `current_user` (geçerli, süresi dolmamış, iptal edilmemiş oturum + aktif kullanıcı; yoksa 401) ve `require_role("admin")` (yoksa 403). Bu görevde korunan tek iş endpoint'i yok; Görev 09 bunları kullanır. `/healthz`, `/readyz`, `/auth/login` açık kalır.
6. **CSRF:** cookie ile gelen ve durum değiştiren isteklerde (`POST/PUT/PATCH/DELETE`) `Content-Type: application/json` zorunlu, değilse 415. SameSite=Lax ile birlikte Faz 1 için yeterli; gerekçe docstring'de. Bearer ile gelen istekler muaf.
7. **CLI** (`python -m app.users`):
   - `create --email --name --role {admin,reviewer}`: parolayı `getpass` ile iki kez sorar (argüman veya env ile parola alınmaz).
   - `set-password --email`, `deactivate --email` (kullanıcının açık oturumlarını da iptal eder), `list`.
8. **Ayarlar:** `Settings`'e `session_ttl_hours: int = 12`, `cookie_secure: bool = True`. `.env.example` güncellenir.
9. **Testler** (modüle göre dosyalanır: `test_auth.py`, `test_users_cli.py`, şema için mevcut `test_schema.py` / `test_orm_consistency.py`): DB gerektirenler `DATABASE_URL` yoksa skip. En az:
   - Doğru giriş → cookie set, `/auth/me` cookie ile ve Bearer ile 200.
   - Yanlış parola, olmayan e-posta, pasif kullanıcı → hepsi aynı 401 gövdesi.
   - Süresi dolmuş ve iptal edilmiş oturum → 401. Logout sonrası aynı token → 401.
   - `require_role("admin")` reviewer'a 403.
   - Cookie + `text/plain` POST → 415; Bearer + aynı istek → 415 değil.
   - DB'de ham token ve ham parola yok (token_hash ≠ token).
   - E-posta büyük/küçük harf: `Orhan@X` ile açılan kullanıcı `orhan@x` ile giriş yapar; aynı e-posta iki kez açılamaz.

## Kapsam dışı

- Org / çok kiracılı yapı, davet, kayıt formu, parola sıfırlama e-postası, SSO/OAuth, 2FA.
- Giriş denemesi sınırlama (rate limit / kilitleme): dashboard internete açılmadan önce ayrı görev olarak eklenir; PR'da açık risk olarak yazılır.
- Traefik ForwardAuth, `proxy` servisi.
- İnceleme/onay API'si (Görev 09), `dashboard-web` (Görev 10).
- `--approve-band` CLI bayrağının değiştirilmesi.

## Kabul kriterleri (Themis koşar)

- [ ] `make lint`, `make typecheck`, `make test` temiz; CI yeşil (DB testleri CI'da Postgres ile).
- [ ] `alembic upgrade head` boş DB'de ve 0004'teki DB'de çalışır; `downgrade -1` iki tabloyu ve enum'u kaldırır.
- [ ] Yukarıdaki test listesinin her maddesi bir testle karşılanır; PR açıklamasında madde → test eşlemesi.
- [ ] Kodda ham parola veya token loglanmaz (log çağrıları elle okunur).
- [ ] Yeni bağımlılık yalnızca `argon2-cffi`.

## Açık sorular (Orhan)

- Faz 1 rolleri iki tane yeter mi (`admin`: kullanıcı yönetimi + her şey; `reviewer`: inceleme/onay)? Öneri: evet; ortaklar `reviewer`, Orhan `admin`.
- Oturum süresi 12 saat uygun mu?

## Notlar Claude Code için

- Önce `services/app/app/main.py`, `settings.py`, `models/common.py`, `tests/conftest.py`, `alembic/versions/0004_*.py` oku; adlandırma ve enum kalıbını (`PgEnum`, `pg_type`) aynen izle.
- Router'ı `main.py`'ye `include_router` ile ekle; `main.py`'deki mevcut davranışı değiştirme.
- Spec dışı ekleme yapma (rate limit, org tablosu, ekstra endpoint yok). Testler modül adına göre dosyalanır.
- Commit et; push'u Themis yapar.
