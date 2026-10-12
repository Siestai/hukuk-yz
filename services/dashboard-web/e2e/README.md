# e2e (Playwright)

Canlı bir yığına karşı koşan uçtan uca testler. **CI'da koşmaz** (orada yığın yok); Vitest de
bu klasörü taramaz. Kurulum ve video: [docs/local-dev.md](../../../docs/local-dev.md).

```bash
make dev && make demo-data       # yığın + sentetik demo verisi
make user email=e2e@example.test name='E2E' role=reviewer
E2E_EMAIL=e2e@example.test E2E_PASSWORD='...' pnpm e2e   # services/dashboard-web içinde
```

Ortam değişkenleri: `E2E_EMAIL`, `E2E_PASSWORD` (gerekli, repoya yazılmaz), `BASE_URL`
(varsayılan `http://localhost:3000`), `E2E_VIDEO=1` (video), `E2E_CHANNEL=chromium` (tam
Chromium; PDF görüntüleyicisi için), `E2E_NAME` (giriş yapan kullanıcının görünen adı; varsayılan `E2E`, `statuses.spec.ts` inceleyen adını bununla arar), `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` (isteğe bağlı; demo veritabanındaki bir admin, `files-approve.spec.ts` onaylı dosyayı silme akışı için), `E2E_RETRIES` (varsayılan 0; trace ilk yeniden denemede
alınır). Çıktı: `.output/` (gitignore'lu). Tarayıcı `pnpm exec playwright install chromium` ile iner.

## Dosyalar

| Dosya                   | Ne dener                                                                                                                                                                                                                                                                                                                                                              | Veriyi                                                                                                          |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `login.spec.ts`         | oturumsuz yönlendirme, yanlış parola (Türkçe hata), giriş, boş alan, çıkış                                                                                                                                                                                                                                                                                            | değiştirmez                                                                                                     |
| `queue.spec.ts`         | özet, bant / mahkeme / sebep filtresi, arama, mükerrer işareti, sıralama, sayfalama                                                                                                                                                                                                                                                                                   | değiştirmez                                                                                                     |
| `detail.spec.ts`        | alanlar, PDF sekmesi (iframe ve PDF yanıtı), metin sekmesi, J/K                                                                                                                                                                                                                                                                                                       | değiştirmez                                                                                                     |
| `actions.spec.ts`       | R ile ret (not zorunlu), E ile anahtar kelime düzeltip onay, A ile onay, "kuyruk bitti"                                                                                                                                                                                                                                                                               | **tüketir**: Demo 12, 05, 04                                                                                    |
| `bulk.spec.ts`          | yüksek bant + dar arama, onay kutusu, çalıştırma, rapor                                                                                                                                                                                                                                                                                                               | **tüketir**: Demo 01-03                                                                                         |
| `info-tips.spec.ts`     | bilgi ipuçları: başlık ipucu fareyle / dokunarak açılır, Escape ve dışarı basma kapatır, klavye odağı, kutu ekranda kalır (360 / 768 / 1440), yatay kaydırma yok, 44 px hedef (telefon), karşılama kartı kapanır ve yeniden yüklemede gelmez                                                                                                                          | değiştirmez                                                                                                     |
| `statuses.spec.ts`      | durum sekmeleri: ret ve onaydan sonra Reddedilen (ret notu, inceleyen) / Onaylanan (düzeltilerek onaylandı rozeti) / Tümü (üç rozet), detaya git ve geri dön, J/K sekmenin listesinde, sekme sayıları liste toplamıyla aynı; "Onaydan çıkar" / "Reddi geri al" ile yeniden incelemeye alıp tekrar karara bağlama, geçmişte reopen satırı, "Yeniden incelemede" rozeti | **tüketir**: Demo 11, 06, 07, 08 (actions ve bulk'tan sonra)                                                    |
| `responsive.spec.ts`    | 1024 / 1280 / 1440: tablo kutusunda iç yatay kaydırma yok (Bekleyen, Reddedilen, Tümü; 1024 ve altında kart); 360x740 ve 768x1024: yatay kaydırma yok (giriş, kuyruk, detay), durum sekmeleri sığar ve gezinir, menü çekmecesi, kart listesi, filtre düğmesi, toplu onay diyaloğu, aksiyon çubuğu, PDF bağlantısı / çerçevesi, 44 px dokunma hedefi                   | değiştirmez                                                                                                     |
| `files-approve.spec.ts` | Yükleme listesi "Taranıyor → Onay bekliyor", onay paneli (öneri, kaynak etiketi, alıntı), alanı düzeltip onayla, aynı sayılı dosya "yeni sürüm olabilir" ve bağlama, onay bekleyen dosyayı sil, admin onayı kaldırıp siler, 360 px                                                                                                                                    | **ekler** (kendi metinlerini yükler; admin kısmı `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` ister, yoksa atlanır) |
| `files.spec.ts`         | Dosyalar: PDF yükle → listede görünür → tarama "Tamamlandı" → detayda gömülü PDF, metin ve sürüm geçmişi; aynı dosya "zaten yüklü"; yeni sürüm (liste tek satır, 2 sürüm); tür / durum filtresi; 360 px'te kart, yatay kaydırma yok, 44 px / 16 px (`chromium-mobile-files`)                                                                                          | **ekler** (her koşu kendi PDF'lerini yükler, sıfırlama gerekmez)                                                |

Üç Playwright projesi var (hepsi Chromium): `chromium` (salt okunur dosyalar) önce, sonra
`chromium-mobile` (`devices["Pixel 7"]`: dokunmatik, `pointer: coarse`; yalnız `responsive.spec.ts` ve `info-tips.spec.ts`,
salt okunur) ve `chromium-mutating` (veri değiştirenler) koşar; ikisi de `chromium`a bağlıdır ve tek worker'la
tanım sırasıyla koşar (mobil önce), böylece okuyan testler dokunulmamış demo verisini görür. Testler tek worker'la, sırayla koşar. Oturum bir kez `global-setup.ts` ile açılır
(`.output/state.json`); `login.spec.ts` kendi girişini yapar.

## Dosyalar (`files.spec.ts`)

Yükleme taraması `worker`'a bağlıdır: `app` ve `worker` aynı `FILE_STORE_ROOT`'u görmeli ve worker çalışıyor olmalı
(`make dev` ikisini de başlatır). Worker yoksa test "Tamamlandı"yı bekleyip düşer (90 sn). Metinli bir PDF'in taranması
Tesseract istemez. Her koşu kendi içeriğiyle PDF üretir (aynı içerik "zaten yüklü" olur), bu yüzden demo veriyi
sıfırlamak gerekmez. Rol `reviewer`dır; arşivle / yeniden tara (admin) bu testte yok, bileşen testlerinde.

## Tekrar koşmak

Mutating testler demo kayıtlarını onaylar veya reddeder; ikinci koşuda kayıt kalmaz ve testler
"Demo data is used up" ipucuyla düşer. Başa dönmek için:

```bash
make e2e-reset        # db-reset + demo-data; siler, kullanıcılar da gider
make user email=e2e@example.test name='E2E' role=reviewer   # sıra önemli: önce sıfırla, sonra kullanıcı
```

Demo kayıtlarının içeriği ve bantları: [infra/demo/README.md](../../../infra/demo/README.md). Testler
sayıları (12 kayıt: 6 yüksek, 4 orta, 2 düşük) bu fixture'dan bekler.

Not: `login.spec.ts` yanlış parola denemesini var olmayan bir e-postayla yapar; giriş sınırı
e-posta başına sayar, tekrarlı koşular gerçek hesabı kilitlemesin diye.
