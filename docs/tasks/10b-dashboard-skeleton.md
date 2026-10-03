# Görev 10b: dashboard-web iskeleti, giriş ve inceleme kuyruğu

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/architecture.md` (servisler, `app` tek veri yazarı), `docs/tasks/08-auth.md`, `docs/tasks/09-review-api.md`, `docs/tasks/10a-dashboard-api-prep.md`, `docs/decisions.md` 2026-10-03 (i18n, arayüzde DB yok, shadcn, PDF, alan adı).
Skill'ler: `frontend-ui` (bağlayıcı), `task-pr-hygiene`.
Tasarım: `docs/design/dashboard-v0.md` (bağlayıcı: token değerleri, fontlar, ekran kuralları, giriş alıntısı).
Önce: Görev 10a merge edilmiş olmalı (hata kodları ve OpenAPI şeması bu görevin tip üretimine girer).

## Hedef

`services/dashboard-web`: Baran ve İbrahim'in giriş yapıp onay bekleyen kararları görebildiği, `hukuk-dashboard.siestai.com` adresinde yayına alınabilir ilk sürüm. Bu görevde kuyruk listesi ve özet; karar detayı ve onay aksiyonları Görev 10c'de.

## Kapsam

1. **Workspace ve iskelet.**
   - Kökte pnpm workspace (`pnpm-workspace.yaml`): `services/dashboard-web`, `packages/ui`. Node sürümü `.nvmrc` / `engines` ile sabit (güncel LTS).
   - Next.js (App Router), TypeScript strict, ESLint, Prettier. `output: "standalone"`.
   - `packages/ui`: Tailwind tema token'ları (CSS değişkenleri; değerler `docs/design/dashboard-v0.md`'den; IBM Plex fontları `next/font` ile yerel), shadcn/ui bileşenleri bu token'lardan beslenir. Bileşenlerde sabit renk / keyfi Tailwind değeri yok (lint kuralı veya CI'da grep kontrolü).
2. **i18n.** `next-intl`, varsayılan ve tek dil `tr`, Türkçe adreslerde dil öneki yok. `messages/tr.json` ekran bazlı anahtarlarla. Bileşenlerde kullanıcıya görünen sabit metin yok (eslint kuralı: `i18next/no-literal-string` veya eşdeğeri, JSX metni için). Enum etiketleri (`court`, `band`, güven sebebi kodları) `enums.*` anahtarlarından; API hata kodları `errors.*` anahtarlarından. Tarih ve sayı `Intl` + `tr-TR`.
3. **API erişimi.**
   - Tarayıcı yalnız dashboard'la konuşur; dashboard `/api/*` isteklerini `APP_API_URL`'e iletir (Next rewrite veya route handler). `app` internete açılmaz. İletimde istemci IP'si `X-Forwarded-For` ile geçer (10a'daki rate limit için).
   - BFF, `X-Forwarded-For` değerini güvenilen uç proxy'den aldığı istemci IP'sine ayarlar (gelen başlığı olduğu gibi aktarmaz); `app` tarafında `FORWARDED_ALLOW_IPS` yalnız dashboard-web ağını güvenir.
   - Tipler `app`'in OpenAPI şemasından üretilir (`openapi-typescript` + `openapi-fetch` veya eşdeğeri). Şema dosyası `app` içinden bir komutla çıkarılır (`python -m app.openapi > services/dashboard-web/openapi.json`); CI şemanın güncel olduğunu kontrol eder (yeniden üret, `git diff --exit-code`).
   - Veritabanı istemcisi, ORM, `DATABASE_URL` yok.
4. **Ekranlar.**
   - `/giris`: sol panelde logo + rastgele ünlü söz (`content/login-quotes.tr.json`, liste `docs/design/login-quotes.tr.json`'dan; seçim sunucuda, her yüklemede), sağda e-posta + parola. Hatalar koddan çevrilir (`unauthorized`, `too_many_attempts` + kalan süre). Başarıda `/`'a.
   - Oturumsuz her istek `/giris`'e yönlenir (middleware `/auth/me` ile değil cookie varlığıyla ön kontrol; asıl kontrol API'de, 401 gelirse girişe dön).
   - Yan menü: logo + ad (`brand.name` = "Libria", çalışma adı), "İnceleme kuyruğu" (bekleyen sayısıyla), ileride gelecek bölümler pasif; altta kullanıcı adı, rolü, çıkış.
   - `/` (inceleme kuyruğu):
     - Özet kartları (`/review/decisions/summary`): banda göre bekleyen, mahkemeye göre bekleyen, toplam onaylanan / reddedilen, en sık sebepler.
     - Tablo (`/review/decisions`): başlık, mahkeme, daire, E/K, tarih, dergi sayısı, bant (renkli rozet, token'dan), skor, sebepler, mükerrer işareti. Varsayılan sıralama en şüpheli önce.
     - Filtreler: bant, mahkeme, sebep, dergi sayısı, E/K arama. Filtre, sıralama ve sayfa URL'de (paylaşılabilir, geri tuşu çalışır). Sayfalama `limit`/`offset`, toplam sayı görünür.
     - Boş durum, yükleniyor ve hata durumları.
     - Satırlar bu görevde detaya bağlanmaz (10c).
5. **Güvenlik başlıkları.** CSP (`default-src 'self'`; `frame-ancestors 'none'`; 10c'deki PDF için `frame-src 'self'` / `object-src 'self'` şimdiden), `X-Content-Type-Options`, `Referrer-Policy: same-origin`, `Permissions-Policy` sıkı. `X-Robots-Tag: noindex` (iç araç).
6. **Çalıştırma ve yayın.**
   - `services/dashboard-web/Dockerfile`: çok aşamalı, standalone çıktı, root olmayan kullanıcı, healthcheck.
   - Compose'a `dashboard-web` servisi: `APP_API_URL=http://app:8000`, `127.0.0.1:3000`. `app`'e `ARCHIVE_ROOT` salt okunur bağlama örneği (yol `.env`'den).
   - `docs/deploy.md` (yeni, kısa): Dokploy'da `hukuk-dashboard.siestai.com` (TLS Dokploy/Traefik'te), yalnız `dashboard-web` dışarı açılır; `app` ve `postgres` iç ağda; gerekli env listesi; ilk kurulum adımları (migrate, karar arşivini yükleme `python -m app.loaders.decisions`, arşiv dosyalarını sunucuya bağlama, kullanıcıları CLI ile açma, `prune-login-attempts` cron'u). Sunucu IP'si, alan adı dışındaki altyapı ayrıntısı ve kişi bilgisi yazılmaz (repo public).
7. **CI.** Yeni iş: `pnpm install --frozen-lockfile`, lint, typecheck, test, build, OpenAPI güncellik kontrolü, dashboard Docker build.
8. **Testler.** Vitest + Testing Library: kuyruk tablosu (veri, boş, hata), filtrelerin URL'ye yazılması, giriş formunun hata kodlarını çevirmesi, `tr` mesaj dosyasında kullanılan her anahtarın bulunması.

## Kapsam dışı

- Karar detayı, PDF görüntüleme, onay/ret, toplu onay (Görev 10c).
- Dosya yükleme, iş listesi, KB araması, kullanıcı yönetimi ekranı, marka ve logo, karanlık tema, mobil düzen (masaüstü öncelikli; dar ekranda bozulmaması yeter).
- Gerçek yayına alma (deploy). PR yayına hazır imaj ve `docs/deploy.md` ile biter; yayını Orhan onaylar, Themis Orhan'ın onayıyla yapar.

## Kabul kriterleri (Themis koşar)

1. Python tarafı `make lint typecheck test` ve yeni pnpm işleri yeşil; CI yeşil.
2. `grep` kontrolleri: frontend paketlerinde `prisma|drizzle|"pg"|postgres|DATABASE_URL` yok; bileşenlerde hex/rgb renk ve keyfi Tailwind değeri yok.
3. Yerel çalıştırma: `app` + `dashboard-web` ayağa kalkar (sunucuda Docker yok: `uv run uvicorn` + `pnpm dev`, test DB'si olmadan çalışmayan kısımlar CI'daki compose ile doğrulanır); giriş, kuyruk, filtre, sayfa değiştirme elle denendi, ekran görüntüleri PR'da.
4. OpenAPI'den üretilen tipler commit'li ve CI'da güncel.
5. Oturumsuz `/` → `/giris`; yanlış parola Türkçe mesaj; 6. yanlış deneme "çok fazla deneme, N dakika sonra" mesajı.
6. Güvenlik başlıkları yanıtta var (test ya da `curl -I` çıktısı PR'da).

## PR bölümü

Görev üç PR'a bölünür (Orhan, 2026-10-03):

- **10b-1, temel:** workspace, Next.js, `packages/ui` token'ları ve shadcn bileşenleri, i18n, OpenAPI tipleri, lint kuralları, CI işi `web`. Gerçek ekran yok.
- **10b-2, oturum:** giriş ekranı ve rastgele söz, `/api` BFF vekili (`X-Forwarded-For`), middleware yönlendirmesi, uygulama kabuğu ve yan menü, çıkış, güvenlik başlıkları.
- **10b-3, inceleme kuyruğu:** özet kartları, tablo, URL filtreleri, sayfalama.

Kapsam maddelerinin dağılımı: 1, 2 ve 7'nin `web` işi 10b-1; 3'ün tip üretimi 10b-1, vekil 10b-2; 4'ün giriş ve yan menüsü 10b-2, kuyruk ekranı 10b-3; 5 10b-2. Madde 6 (Dockerfile, compose, `docs/deploy.md`) ve 7'nin Docker build adımı bu üç PR'ın dışında, Görev 10d'dedir.

Kabul kriterlerinin dağılımı:

| Kriter | PR |
|---|---|
| 1. Python `make lint typecheck test` ve pnpm işleri yeşil, CI yeşil | her PR |
| 2. `grep` kontrolleri (DB istemcisi yok, sabit renk ve keyfi değer yok) | 10b-1 (lint kuralları ve testleri), sonraki PR'larda korunur |
| 3. Yerel çalıştırma, elle deneme, ekran görüntüleri | giriş 10b-2, kuyruk ve filtre 10b-3 |
| 4. OpenAPI tipleri commit'li ve CI'da güncel | 10b-1 |
| 5. Oturumsuz `/` → `/giris`, hata mesajları | 10b-2 |
| 6. Güvenlik başlıkları | 10b-2 |

## Notlar Claude Code için

- `frontend-ui` skill'i bu görevde bağlayıcı; ondan sapma gerekirse kod yazmadan önce PR açıklamasına gerekçeyle yaz.
- shadcn bileşenlerini `packages/ui`'ye ekle, yalnız kullanılanları.
- Test dosyaları modül adıyla (`queue-table.test.tsx`).
- Commit et, push etme.
