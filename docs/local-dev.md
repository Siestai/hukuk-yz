# Yerel çalıştırma (Mac)

Tüm yığını (postgres, migration, `app`, `worker`, `dashboard-web`) kendi bilgisayarında çalıştırıp
tarayıcıdan denemek için. Yayın (deploy) ayrı: [deploy.md](deploy.md).

## Gerekenler

- **Docker Desktop** ya da **OrbStack** (ikisi de `docker compose` sağlar). Yığın için başka
  bir şey gerekmez.
- **uv** (`brew install uv`): yalnız `make load-archive` (özel arşivi ayrıştırma) ve `make lint test`
  için.
- **Node 24 ve pnpm** (yalnız arayüz geliştirmek ve e2e koşmak için; `make web-dev`, `pnpm e2e`):
  `corepack enable` pnpm'i `package.json`'daki sürümle getirir. Node sürümü `.nvmrc`'de.

## İlk çalıştırma

```bash
git clone https://github.com/siestai/hukuk-yz.git && cd hukuk-yz
make dev
```

`make dev` `.env`'i `.env.example`'dan oluşturur (yoksa), düz http için `COOKIE_SECURE=false`
yapar, imajları derler ve yığını başlatır; sonunda adresi yazar. İlk derleme birkaç dakika
sürer. Hazır olunca:

```bash
make user email=ben@example.com name='Ad Soyad' role=reviewer   # parolayı terminalde sorar
make demo-data                                                   # sentetik demo kayıtları
```

Sonra <http://localhost:3000> adresini aç, az önceki kullanıcıyla giriş yap. Kuyrukta 12 kurgusal
karar görürsün (6 yüksek, 4 orta, 2 düşük güven; ayrıntı: [infra/demo/README.md](../infra/demo/README.md)).

`role` için `reviewer` (inceleme ve onay) ya da `admin`. Parola en az uzunluk kuralına uymalıdır;
reddedilirse komut nedenini yazar.

### Özel arşivle (gerçek kararlar)

Telif ve KVKK nedeniyle arşiv repoda değildir. İbrahim'in Drive klasörünün kopyasını
`data/drive/` altına koy (içinde `Yargi_Kararlari_Arsivi/` olmalı; `rclone copy projem: data/drive`,
bkz. AGENTS.md). Sonra:

```bash
make load-archive
```

Bu hedef sırayla şunları yapar (komutlar Makefile'da, elle de çalıştırılabilir):

1. `.env` içinde `ARCHIVE_HOST_DIR=../../data/drive` yapar ve `app`'i bu klasörle (salt okunur,
   `/archive`) yeniden oluşturur: karar ekranındaki PDF sekmesi gerçek dosyaları gösterir.
2. Ana makinede: `uv run hukuk-ingest scan data/drive --out data/work/scan --text-cache data/extracted --no-ocr`
   (6.600 dosya, birkaç dakika; çıktı `data/` altında, gitignore'lu).
3. Ana makinede: `uv run hukuk-ingest decisions parse --scan-report data/work/scan/files.jsonl --text-cache data/extracted --out data/work/decisions`.
4. `app` konteynerinde yükler: `python -m app.loaders.decisions /work/decisions/decisions.jsonl --files /work/scan/files.jsonl`
   (`data/work` salt okunur bağlanır). Yükleyici tekrar çalıştırılabilir: olanı atlar.

Tarama ve ayrıştırma ana makinede çalışır, çünkü `app` imajında Tesseract yok ve çıktıların
`data/` altında kalması istenir; yükleme konteynerde çalışır, çünkü veritabanı oradadır.

### Demo ile gerçek arşiv arasında geçiş

`ARCHIVE_HOST_DIR` (`.env`) app konteynerine salt okunur `/archive` olarak bağlanır; karar
ekranı PDF'leri oradan okur. `make demo-data` bunu `../../infra/demo/archive`, `make load-archive`
`../../data/drive` yapar ve `app`'i yeniden oluşturur. Yol `infra/compose/`'a göredir. Veritabanı
tek: demo kayıtlarını silmek için `make db-reset` (tüm veriyi ve kullanıcıları siler, sonra
`make user` ve istediğin yükleme yeniden).

## Arayüz geliştirme (`make web-dev`)

Konteynerdeki `dashboard-web` yerine ana makinede sıcak yenilemeli `next dev`:

```bash
make dev        # app ve veritabanı için (dashboard-web konteyneri de çalışır, zararsız)
make web-dev    # http://localhost:3001, APP_API_URL=http://localhost:8000
```

Port çakışırsa `WEB_DEV_PORT=3002 make web-dev`. API tipleri değişince `pnpm openapi`
(`app`'in şemasını yeniden üretir). Çerez ana bilgisayar adına bağlıdır, porta değil: 3000'de
açılan oturum 3001'de de geçerlidir.

## Uçtan uca testler (Playwright)

Canlı yığına ve **demo veriye** karşı koşar (CI'da yok). Ayrıntı:
[services/dashboard-web/e2e/README.md](../services/dashboard-web/e2e/README.md).

```bash
make user email=e2e@example.test name='E2E' role=reviewer
make db-reset demo-data   # taze demo verisi (kullanıcıyı silerse make user'ı yeniden çalıştır)
cd services/dashboard-web && pnpm exec playwright install chromium   # bir kez
E2E_EMAIL=e2e@example.test E2E_PASSWORD='...' make e2e
```

Testler demo kayıtlarını **tüketir** (onaylar, reddeder): tekrar koşmadan önce `make db-reset demo-data`
ve `make user`. Parola ortam değişkeninden gelir, repoya yazılmaz.

**Video:** `E2E_VIDEO=1 make e2e` her test için video kaydeder; dosyalar
`services/dashboard-web/e2e/.output/results/<test-adı>/video.webm` altına düşer (HTML rapor:
`e2e/.output/report/index.html`, `pnpm exec playwright show-report e2e/.output/report`). Dizin
gitignore'ludur. PDF sekmesini gerçek Chromium'da görmek için `E2E_CHANNEL=chromium` (varsayılan
headless kabuğunda PDF görüntüleyici yoktur; bu testler PDF'in yanıtını ayrıca doğrular).

## Sorun giderme

- **Giriş "başarılı" ama sayfa girişe dönüyor.** Tarayıcı `Secure` çerezi düz http'de atar.
  `.env` içinde `COOKIE_SECURE=false` olmalı (`make dev` kontrol eder), sonra
  `docker compose --env-file .env -f infra/compose/docker-compose.yml up -d app`.
  Üretimde `true` kalır.
- **Port çakışması.** `Bind for 127.0.0.1:3000 failed`: `.env`'de `DASHBOARD_HOST_PORT=3010`
  (postgres için `POSTGRES_HOST_PORT`). `app` 8000'i sabit kullanır; başka bir şey 8000'deyse onu durdur.
- **"Çok fazla hatalı deneme."** Aynı e-posta için 15 dakikada 5 yanlış parola (aynı IP'den 20)
  giriş sınırına takılır; 15 dakika bekle ya da `make db-reset`.
- **PDF sekmesi "bulunamadı" diyor.** `ARCHIVE_HOST_DIR` yanlış klasöre bakıyor (demo kayıtları
  için demo arşiv, gerçek kayıtlar için `data/drive` gerekir; yukarıdaki geçiş bölümü), ya da
  dosya yüklemeden sonra değişmiş (SHA-256 uyuşmazlığı; `app` günlüğünde uyarı).
- **`dashboard-web` açılmıyor.** `docker compose ... logs dashboard-web`: `APP_API_URL` eksikse
  başlangıçta hata verir (compose bunu `http://app:8000` olarak kendisi koyar).
- **Sıfırdan başlamak.** `make db-reset` veritabanı birimini siler ve migration'ı yeniden
  uygular; `make down` yığını durdurur (veri kalır).
