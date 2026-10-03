# Yayın (Dokploy)

Durum: taslak, **henüz yayına alınmadı**. Yayını Orhan onaylar. Adres:
`hukuk-dashboard.siestai.com`. Yerel çalıştırma için: [local-dev.md](local-dev.md).
Sunucu ayrıntıları (adres, erişim) repoda tutulmaz.

## Düzen

Dokploy'da tek compose uygulaması: `infra/compose/docker-compose.yml`
(postgres, migrate, app, worker, dashboard-web).

- **Yalnız `dashboard-web` dışarı açılır**: Dokploy'un Domains sekmesinde
  `hukuk-dashboard.siestai.com` → servis `dashboard-web`, port `3000`, HTTPS açık (TLS'i
  Traefik/Dokploy sonlandırır; sertifika Let's Encrypt). Domain ve Traefik etiketi Dokploy'da
  `dashboard-web` servisinin 3000 portuna ayarlanır; compose dosyası dışarıya port yayınlamaz.
- `app` (8000) ve `postgres` (5432) yalnız compose iç ağında kalır: alan adı eklenmez. Ana makine
  port eşlemeleri (`127.0.0.1:...`) yalnız `docker-compose.local.yml`'dedir; Makefile yerelde onu
  ekler, Dokploy yalnız `docker-compose.yml`'yi kullanır. (Dokploy'un kendi paneli ana makinenin
  3000 portunu kullanır; bu yüzden tabandaki dosyada eşleme yoktur.)
- Tarayıcı yalnız `dashboard-web` ile konuşur; `/api/*` isteklerini o `app`'e iletir.

## Ortam değişkenleri

Dokploy'un **Environment sekmesinde** tanımlanır (`.env.example` her birini açıklar); Dokploy bunu
compose'un yanına bir `.env` olarak yazar. Compose değerleri hem `${...}` yerine koymasıyla hem
`env_file` ile okur; `env_file` isteğe bağlıdır (`required: false`, compose v2.24+), dosya yoksa
hata vermez. Sır değerleri repoya yazılmaz.

| Değişken | Üretim değeri |
|---|---|
| `ENV` | `production` (`dev` dışı: `FORWARDED_ALLOW_IPS` boşsa başlangıçta uyarı verir) |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | güçlü, benzersiz parola; `DATABASE_URL`'i compose bunlardan kurar |
| `COOKIE_SECURE` | `true` (varsayılan; **false yapma**) |
| `SESSION_TTL_HOURS` | `12` |
| `LOGIN_MAX_FAILS_PER_EMAIL`, `LOGIN_MAX_FAILS_PER_IP`, `LOGIN_WINDOW_MINUTES` | `5`, `20`, `15` (varsayılan) |
| `FORWARDED_ALLOW_IPS` | **`dashboard-web`'in compose ağındaki adresi ya da ağın CIDR'ı** (`docker network inspect <proje>_default`); `*` değil. Boş kalırsa `app` istemci IP'sini hep `dashboard-web` adresi görür ve IP başına giriş sınırı herkes için tek sayaç olur |
| `TRUSTED_PROXY_HOPS` | `1`: `dashboard-web`'in önünde yalnız Traefik var, istemci adresi `X-Forwarded-For`'un son girdisidir. Araya bir proxy daha (CDN) girerse artır |
| `ARCHIVE_HOST_DIR` | Karar PDF'lerinin sunucudaki **mutlak** klasörü (aşağıda); compose bunu `app`'e salt okunur `/archive` olarak bağlar |
| `DASHBOARD_HOST_PORT`, `POSTGRES_HOST_PORT` | tanımlanmaz (yalnız yerel override dosyasında kullanılır; Traefik konteyner portuna ağdan ulaşır) |

`APP_API_URL` ayarlanmaz: compose `dashboard-web` için `http://app:8000` koyar. `ARCHIVE_ROOT`
da compose'dadır (`/archive`).

## İlk kurulum

1. **Uygulamayı ayağa kaldır** (Dokploy'da Deploy). `migrate` servisi `alembic upgrade head`'i
   `app`'ten önce çalıştırır; sonradan elle: `docker compose ... run --rm app alembic upgrade head`.
2. **Kullanıcıları aç** (parola terminalde sorulur, argümanla verilmez): `app` konteynerinde
   (Dokploy terminali ya da `docker exec -it`):
   `python -m app.users create --email EPOSTA --name "Ad Soyad" --role reviewer`.
   Diğer komutlar: `set-password`, `deactivate`, `list` (`python -m app.users -h`).
3. **Karar arşivini yükle.** Ayrıştırma (`hukuk-ingest scan` ve `decisions parse`) veriye sahip
   makinede çalışır ([local-dev.md](local-dev.md), `make load-archive`); sunucuya yalnız şunlar gider:
   - `decisions.jsonl` ve `files.jsonl` (geçici bir klasöre), ve
   - karar dosyaları, aşağıdaki gibi.

   Yükleme `app` konteynerinde, o klasör `/work` olarak bağlanarak çalışır:
   `python -m app.loaders.decisions /work/decisions.jsonl --files /work/files.jsonl`
   (tekrar çalıştırılabilir; olan kaydı atlar). Dosya yolları (`ingest_file.path`) `ARCHIVE_ROOT`'a
   göredir: `Yargi_Kararlari_Arsivi/...`.
4. **Arşiv dosyalarını salt okunur bağla.** Yalnız `Yargi_Kararlari_Arsivi/` klasörünü sunucuda bir
   dizine kopyala (örn. `rsync -a`; dizin yalnız okuyabilen bir hesaba ait olsun), `ARCHIVE_HOST_DIR`'i
   o dizinin **üst** klasörüne (içinde `Yargi_Kararlari_Arsivi/` bulunan) mutlak yol olarak ver.
   Dosyalar Çalışma ve Toplum'un sayfalarıdır (telif): yalnız giriş yapmış reviewer'lara, iç
   inceleme için sunulur; yayınlama ve çoğaltma yok. `app` her dosyayı sunmadan SHA-256'sını
   kontrol eder; eşleşmeyen dosya sunulmaz.
5. **Giriş denemesi temizliği** (cron): `login_attempt` tablosu büyür. Dokploy'da Schedules ile
   `app` konteynerinde günlük: `python -m app.users prune-login-attempts` (30 günden eskiyi siler).

## Kontrol

- `https://hukuk-dashboard.siestai.com/healthz` → `ok` (API'ye bağlı değil).
- Giriş sayfası açılır, yanlış parola Türkçe hata verir, doğru parola kuyruğa götürür.
- Çerez `Secure` ve `HttpOnly`; yanıtlarda `Content-Security-Policy`, `X-Robots-Tag: noindex`.
- `app` ve `postgres` dışarıdan erişilemez (`curl` ile bu alan adının başka bir yolu yok).
- Birkaç yanlış girişten sonra `app` günlüğünde istemci IP'sinin `dashboard-web` adresi değil
  gerçek adres olduğunu doğrula (`FORWARDED_ALLOW_IPS` + `TRUSTED_PROXY_HOPS` doğru mu).

## Doğrulanmadı

Bu belge sunucuda denenmedi; Docker imajı CI'da derlenir ve `/healthz` kontrol edilir ama Dokploy
alan adı ve ağ ayarı, `FORWARDED_ALLOW_IPS` değeri ve Traefik'in tek proxy olması ilk yayında
elle doğrulanmalıdır.
