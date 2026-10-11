# Yayın (Dokploy)

Durum: taslak, **henüz yayına alınmadı**. Yayını Orhan onaylar. Adres:
`dash-hukuk.siestai.com`. Yerel çalıştırma için: [local-dev.md](local-dev.md).
Sunucu ayrıntıları (adres, erişim) repoda tutulmaz.

## Düzen

Dokploy'da tek compose uygulaması: `infra/compose/docker-compose.yml`
(postgres, migrate, app, worker, dashboard-web).

- **Yalnız `dashboard-web` dışarı açılır**: Dokploy'un Domains sekmesinde
  `dash-hukuk.siestai.com` → servis `dashboard-web`, port `3000`, HTTPS açık (TLS'i
  Traefik/Dokploy sonlandırır; sertifika Let's Encrypt). Domain ve Traefik etiketi Dokploy'da
  `dashboard-web` servisinin 3000 portuna ayarlanır; compose dosyası dışarıya port yayınlamaz.
- `app` (8000) ve `postgres` (5432) yalnız compose iç ağında kalır: alan adı eklenmez. Ana makine
  port eşlemeleri (`127.0.0.1:...`) yalnız `docker-compose.local.yml`'dedir; Makefile yerelde onu
  ekler, Dokploy yalnız `docker-compose.yml`'yi kullanır. (Dokploy'un kendi paneli ana makinenin
  3000 portunu kullanır; bu yüzden tabandaki dosyada eşleme yoktur.)
- Tarayıcı yalnız `dashboard-web` ile konuşur; `/api/*` isteklerini o `app`'e iletir.

### DNS ve TLS (Cloudflare)

- `dash-hukuk` A kaydı sunucu adresine gider, **Proxied** (turuncu bulut). Sunucu adresi repoda
  tutulmaz. Ayrı API alan adı yoktur: `app` iç ağda kalır (bkz. decisions.md).
- Cloudflare SSL/TLS modu **Full (strict)**. "Flexible" Traefik'in HTTPS yönlendirmesiyle döngüye girer.
- Let's Encrypt sertifikası ilk alınırken HTTP doğrulaması Cloudflare'den geçemezse kaydı geçici
  olarak "DNS only" yap, sertifika alınınca Proxied'a döndür (ya da Traefik'e Cloudflare Origin
  Certificate ver).
- **İstemci adresi:** Cloudflare istemci adresini `X-Forwarded-For`'a yazar. Traefik varsayılan
  olarak güvenmediği kaynaktan gelen `X-Forwarded-For`'u atar, kendi gördüğü adresi (Cloudflare'in)
  yazar; bu hâlde IP başına giriş sınırı tüm kullanıcılar için Cloudflare adresleriyle sayılır.
  Düzeltmek için Dokploy Traefik ayarında `websecure` entrypoint'ine
  `forwardedHeaders.trustedIPs` olarak Cloudflare'in IP aralıkları
  (https://www.cloudflare.com/ips/) verilir; o zaman başlık `istemci, cloudflare` olur ve
  `TRUSTED_PROXY_HOPS=2` doğrudur. Bu ayar sunucudaki tüm Dokploy uygulamalarını etkiler.
  Kontrol: aşağıdaki "Kontrol" bölümündeki IP doğrulaması.

## Ortam değişkenleri

Dokploy'un **Environment sekmesinde** tanımlanır (`.env.example` her birini açıklar); Dokploy bunu
compose dosyasının yanına, `infra/compose/.env` olarak yazar (kök `.env` değil; compose ikisini de okur). Compose değerleri hem `${...}` yerine koymasıyla hem
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
| `TRUSTED_PROXY_HOPS` | `2`: önde Cloudflare proxy ve Traefik var (aşağıdaki DNS bölümüne bak). DNS kaydı "DNS only" yapılırsa `1` |
| `FILE_STORE_ROOT` | Dosya deposunun konteyner içindeki yolu. Compose `app` ve `worker` için `/filestore` koyar (`filestore` adlı Docker volume, ikisine okuma-yazma bağlı); elle ayarlanmaz. Boşsa `/files` yükleme uç noktaları 503 verir, worker taramaz, karar PDF'i yalnız `ARCHIVE_ROOT`'tan gelir |
| `ARCHIVE_HOST_DIR` | **İsteğe bağlı, eski.** Karar PDF'lerinin sunucudaki **mutlak** klasörü (aşağıda); compose bunu `app`'e salt okunur `/archive` olarak bağlar. Arşiv "Arşivin içeri alınması" adımıyla dosya deposuna alındıktan sonra gerekmez; `storage_key`'i boş kayıtlar için geçiş süresince kalır |
| `DASHBOARD_HOST_PORT`, `POSTGRES_HOST_PORT` | tanımlanmaz (yalnız yerel override dosyasında kullanılır; Traefik konteyner portuna ağdan ulaşır) |

`APP_API_URL` ayarlanmaz: compose `dashboard-web` için `http://app:8000` koyar. `ARCHIVE_ROOT`
da compose'dadır (`/archive`; **isteğe bağlı, eski**: yalnız dosya deposunda karşılığı olmayan karar
kayıtları için okunur, kaldırılması ayrı küçük iş).

## İlk kurulum

**İlk yayın demo veriyle yapılır** (Orhan, 2026-10-05), gerçek arşiv sonra yüklenir:

- Demo: `ARCHIVE_HOST_DIR`, Dokploy'un repoyu klonladığı klasördeki `infra/demo/archive`'ın
  mutlak yoludur. 3. ve 4. adımlar yerine yükleme `app` konteynerinde, `infra/demo` `/demo` olarak
  bağlanarak çalışır: `python -m app.loaders.decisions /demo/decisions.jsonl --files /demo/files.jsonl`
  (12 sentetik karar, [infra/demo/README.md](../infra/demo/README.md)).
- Gerçek veriye geçiş: demo kayıtları gerçek kayıtlarla karışmasın diye önce veritabanı sıfırlanır
  (yereldeki `make db-reset` gibi: postgres volume silinir, `migrate` yeniden çalışır; kullanıcılar da silinir, 2. adım tekrarlanır), sonra
  3. ve 4. adımlar. Demo süresince yapılan onay/retler atılır; bunlar sentetik kayıtlar üzerinedir.

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
4. **Arşiv dosyalarını salt okunur bağla** (eski yol; 5. adımdan sonra gerekmez). Yalnız `Yargi_Kararlari_Arsivi/` klasörünü sunucuda bir
   dizine kopyala (örn. `rsync -a`; dizin yalnız okuyabilen bir hesaba ait olsun), `ARCHIVE_HOST_DIR`'i
   o dizinin **üst** klasörüne (içinde `Yargi_Kararlari_Arsivi/` bulunan) mutlak yol olarak ver.
   Dosyalar Çalışma ve Toplum'un sayfalarıdır (telif): yalnız giriş yapmış reviewer'lara, iç
   inceleme için sunulur; yayınlama ve çoğaltma yok. `app` her dosyayı sunmadan SHA-256'sını
   kontrol eder; eşleşmeyen dosya sunulmaz.
5. **Arşivin içeri alınması** (Görev 12c; tek seferlik, tekrar çalıştırılabilir). Karar kayıtları
   3. adımla yüklendikten **sonra** yapılır. Drive'ın tam kopyası (`Mevzuat/`, `Yargi_Kararlari_Arsivi/`
   ve kökteki hesap tabloları) sunucuda bir dizine kopyalanır (örn. `rsync -a data/drive/ SUNUCU:/srv/arsiv-aktarim/`;
   Mac'ten gelen klasör adlarının NFC ya da NFD olması fark etmez). CLI, `filestore` volume'ünü
   bağlayan tek seferlik bir `app` konteynerinde çalışır (Dokploy terminalinde compose
   klasöründe; `/import` salt okunur bağlanır):

   ```bash
   docker compose run --rm -v /srv/arsiv-aktarim:/import:ro app \
     python -m app.files.import_dir /import --uploaded-by-system
   ```

   Her dosya dosya deposuna konur. SHA-256'sı 3. adımda yüklenen bir karar kaydınınkiyle aynıysa
   o kayda yalnız `storage_key` ve `original_name` yazılır (yeni kayıt açılmaz); diğerleri yeni
   kayıt olur (`doc_type` Drive klasör adından, yükleyen boş = sistem, tarama kuyruğunda; `worker`
   tarar). `Eskiler/` altındaki dosya, aynı adlı güncel dosyanın önceki sürümü olarak bağlanır
   (ad kuralı: uzantısız, harf/aksan/büyük-küçük harf farkı yok sayılan ad aynı olmalı); eşleşmeyenler
   özette listelenir. Özet (eklenen, eşleşen, atlanan, bağlanan, hatalı, eşleşmeyen `Eskiler/`
   dosyaları) ekrana basılır; bir dosyanın hatası çalışmayı durdurmaz. Çıkış kodu 1 hata olduğunu
   söyler. Komutu ikinci kez çalıştırınca eklenen 0 olmalıdır. Aktarım `FILE_MAX_BYTES` sınırına
   tabi değildir (yönetici sunucuda çalıştırır). İsteğe bağlı `--report YOL` özeti JSON olarak yazar (yol
   konteynerin içindedir; saklamak için ek bir `-v` ile bağla).
6. **Aktarım sonrası Drive salt arşivdir.** İki yönlü senkron yoktur; yeni dosyalar dashboard'daki
   Dosyalar ekranından yüklenir. `ARCHIVE_HOST_DIR` bağı karar PDF'leri için artık gerekmez
   (PDF uç noktası önce dosya deposundan sunar); aynı SHA-256'lı bir dergi yeniden basımı gibi
   `storage_key`'i boş kalan kayıtlar için eski yol çalışmaya devam eder.
7. **Giriş denemesi temizliği** (cron): `login_attempt` tablosu büyür. Dokploy'da Schedules ile
   `app` konteynerinde günlük: `python -m app.users prune-login-attempts` (30 günden eskiyi siler).

## Dosya deposu: yedek ve risk

Yüklenen ve aktarılan tüm dosyalar `filestore` Docker volume'ündedir. **Tek kopya sunucu
diskindedir**: disk ya da volume giderse dosyalar (ve Drive'dan başka kaynağı olmayan yüklemeler)
kaybolur; veritabanı yedeği dosyaları kapsamaz. Zamanlanmış yedek bu görevde yoktur; **12d olarak
önerilir ve 12c'nin hemen ardından yapılmalıdır**. O zamana kadar elle yedek (volume adı
`docker volume ls`'ten bakılır, Dokploy proje adıyla öneklenir):

```bash
docker run --rm -v PROJE_filestore:/filestore:ro -v /srv/yedek:/yedek alpine \
  tar czf /yedek/filestore-$(date +%F).tar.gz -C /filestore .
```

Yedek dosyasını sunucu dışına kopyala. Geri yükleme: aynı komutun `tar xzf` karşılığı, boş
bir volume'e. Dosyalar içerikle adreslendiği için (`sha256/ab/cd/<sha256>`) geri yüklenen bir
dosya yanlışsa uygulama onu sunmaz (SHA-256 kontrolü).

## Kontrol

- `https://dash-hukuk.siestai.com/healthz` → `ok` (API'ye bağlı değil).
- Giriş sayfası açılır, yanlış parola Türkçe hata verir, doğru parola kuyruğa götürür.
- Çerez `Secure` ve `HttpOnly`; yanıtlarda `Content-Security-Policy`, `X-Robots-Tag: noindex`.
- `app` ve `postgres` dışarıdan erişilemez (`curl` ile bu alan adının başka bir yolu yok).
- Birkaç yanlış girişten sonra `app` günlüğünde istemci IP'sinin `dashboard-web` adresi değil
  gerçek adres olduğunu doğrula (`FORWARDED_ALLOW_IPS` + `TRUSTED_PROXY_HOPS` doğru mu).

## Doğrulanmadı

Bu belge sunucuda denenmedi; Docker imajı CI'da derlenir ve `/healthz` kontrol edilir ama Dokploy
alan adı ve ağ ayarı, `FORWARDED_ALLOW_IPS` değeri ve Traefik'in tek proxy olması ilk yayında
elle doğrulanmalıdır. Aktarım komutu ve yedek komutu da sunucuda denenmedi (aktarım yerelde tam Drive kopyasıyla denendi, sayılar PR'da).
