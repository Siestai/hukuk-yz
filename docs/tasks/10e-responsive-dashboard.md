# Görev 10e: dashboard-web mobil ve duyarlı (responsive) düzen

Durum: onaylandı (Orhan, 2026-10-05: "bütün UI projelerimiz responsive olmalı, mobil de düşünülmeli"). Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/design/dashboard-v0.md`, `docs/tasks/10b-dashboard-skeleton.md` (10b'de mobil kapsam dışıydı), `docs/tasks/10c-review-detail.md`, `docs/decisions.md` 2026-10-05.
Skill'ler: `frontend-ui` (bağlayıcı; bu görevle duyarlı düzen kuralları eklenir), `task-pr-hygiene`.

## Hedef

Şu ana kadarki dashboard (giriş, uygulama kabuğu, inceleme kuyruğu, karar detayı, aksiyonlar, toplu onay) 360 px telefondan geniş masaüstüne kadar kullanılabilir olsun. Masaüstü düzeni korunur; dar ekranda içerik yeniden akar, yatay sayfa kaydırması olmaz, dokunma hedefleri parmakla basılabilir.

## Başlangıç durumu (Themis, 360x740, demo veri)

- Kuyruk: sayfa 1236 px genişliğe taşıyor; yan menü (256 px) ekranın üçte ikisini kaplıyor; "Toplu onayla" düğmesi başka öğenin altında kaldığı için tıklanamıyor.
- Detay: sayfa 513 px; alan etiketleri harf harf kırılıyor ("Mahke me"); yapışkan aksiyon çubuğu (`-mx-8`) içeriğin ortasında üst üste biniyor; klavye kısayolu açıklamaları telefonda anlamsız yer kaplıyor.
- Dokunma hedefleri 28-36 px (düğmeler, select'ler, özet kartı bağlantıları).

## Kapsam

1. **Kırılım noktaları** (Tailwind varsayılanları, yeni değer yok): telefon `< md` (768), tablet `md`-`lg`, masaüstü `>= lg` (1024). Mobil öncelikli yazılır: temel sınıf telefon, `md:` / `lg:` genişler.
2. **Uygulama kabuğu.**
   - `lg` ve üstü: bugünkü yan menü aynen.
   - `lg` altı: üstte yapışkan bir başlık çubuğu (logo + ad, bekleyen sayısı rozeti, menü düğmesi). Menü düğmesi, aynı içerikle (gezinme bağlantıları, kullanıcı, çıkış) soldan açılan bir çekmece açar. Çekmece erişilebilir: `packages/ui` içindeki `Dialog` temeli (native `<dialog>`, odak tuzağı, Escape, odak dönüşü) yeniden kullanılır ya da ona bir `side` varyantı eklenir; ayrı kütüphane eklenmez. Bağlantıya basınca çekmece kapanır. Menü düğmesinin erişilebilir adı ve `aria-expanded` değeri vardır.
   - Yan menü ve çekmece aynı gezinme bileşenini paylaşır (kopya yok).
3. **Sayfa boşlukları.** `main` dolgusu telefonda `p-4`, `md:p-6`, `lg:p-8`. Yapışkan aksiyon çubuğunun negatif kenar boşlukları bu dolguyla birlikte değişir (bugünkü `-mx-8 -mb-8` sabit).
4. **Kuyruk.**
   - Başlık: başlık ve eylemler (sıralama + toplu onay) telefonda alt alta, eylemler tam genişlik.
   - Özet kartları zaten `lg:grid-cols-3`; telefonda tek sütun, tablette uygun gördüğün 2 sütun.
   - Filtreler: telefonda her alan tam genişlik (sabit `w-40` / `w-64` yalnız `md` ve üstünde). Telefonda filtreler varsayılan kapalı bir açılır bölümde ("Filtreler", etkin filtre sayısıyla); filtre etkinse açık başlar. Native `<details>/<summary>` yeterli.
   - Liste: `md` altında tablo yerine kart listesi. Her kart tek bir bağlantı (bugünkü tablo satırı gibi tüm kart tıklanır): bant rozeti + skor, başlık (2 satır), mahkeme · daire, E/K, tarih, dergi sayısı, en fazla 2 sebep + "+N", mükerrer işareti. Tablo `md` ve üstünde aynen kalır; tablette tablo yatay kaydırılabilir kapsayıcı içinde (zaten `Table` sarmalayıcısı varsa onu kullan).
   - İki görünüm aynı veri ve aynı yardımcılarla (etiket, tarih, E/K biçimi) üretilir; ortak parça çıkarılır, kopyalanmaz. Gizli görünüm `display: none` ile erişilebilirlik ağacından da çıkar.
   - Sayfalama telefonda sığar (gerekirse yalnız önceki / sonraki + "x / y").
5. **Karar detayı.**
   - Başlık serif ve uzun: telefonda `text-xl`, `md:text-2xl`; rozetler kaydırmadan sarar.
   - Alan satırları (`FieldRow`): telefonda etiket üstte, değer altta (tek sütun); `md` ve üstünde bugünkü 1/3 - 2/3 düzen.
   - Aksiyon çubuğu: telefonda ekranın altında yapışkan, üç düğme eşit genişlikte tek satır (sığmıyorsa kısa etiketler yerine ikinci satır değil, eşit ızgara); `kbd` ipuçları ve kısayol açıklaması `md` altında gizli (kısayollar çalışmaya devam eder). Alt güvenli alan için `env(safe-area-inset-bottom)` kadar dolgu (token/`@utility` ile; bileşende keyfi değer yok). Çubuk son içeriği örtmez (sayfa altında yeterli boşluk).
   - PDF: telefon tarayıcıları gömülü PDF'i çoğu zaman göstermez (iOS yalnız ilk sayfa). `md` altında iframe yerine "PDF'i yeni sekmede aç" bağlantısı (aynı `/api/.../file` adresi, `target="_blank" rel="noopener"`), `md` ve üstünde iframe; iframe yüksekliği `h-screen` yerine görünür alana göre makul (`dvh` tabanlı, token/`@utility`).
   - Düzenleme formu (`fields-form`): alanlar telefonda tek sütun, tam genişlik.
6. **Diyaloglar** (ret, toplu onay): telefonda ekran genişliğine yakın (yanlarda küçük boşluk), yükseklik `max-h` + iç kaydırma, düğmeler alt alta tam genişlik ya da sığıyorsa yan yana. `overscroll-behavior: contain`.
7. **Giriş.** Zaten sol panel `lg` altında gizli; telefonda marka (logo + ad) formun üstünde görünür. Doğrulanır, gerekirse düzeltilir.
8. **Dokunma ve form ergonomisi** (`packages/ui` bileşenlerinde, tek yerde):
   - `pointer: coarse` cihazlarda (Tailwind `pointer-coarse:` varyantı) Button, Input, Select, Textarea, sekme ve gezinme bağlantılarının yüksekliği en az 44 px (`h-11`/`min-h-11`).
   - Input/Select/Textarea yazı boyutu telefonda en az 16 px (`text-base md:text-sm`): iOS odaklanınca yakınlaştırmasın.
   - Yakınlaştırma kapatılmaz (`maximum-scale` yok).
   - `touch-action: manipulation` düğme ve bağlantılarda (temel stil katmanında).
9. **Viewport.** Kök `layout.tsx`'te Next `viewport` export'u: `width=device-width, initial-scale=1, viewport-fit=cover`, `themeColor` token değeriyle eşleşen değer (token dosyasından okunamıyorsa tek sabit + yorum; renk tek yerde tanımlı kalsın).
10. **Kurallar belgelenir.**
    - `.claude/skills/frontend-ui/SKILL.md`'ye "Responsive" bölümü: mobil öncelikli, kırılım noktaları, 360 px'te yatay kaydırma yok, dokunma hedefi 44 px, input 16 px, tablo → kart, yapışkan çubuk + güvenli alan, PDF mobilde bağlantı, her UI PR'ında 360 / 768 / 1440 ekran görüntüsü.
    - `docs/design/dashboard-v0.md`'ye "Mobil" bölümü (yukarıdaki ekran kuralları kısa).
    - `docs/decisions.md`: 2026-10-05, Orhan: tüm UI projeleri responsive, mobil dahil.
11. **Testler.**
    - Vitest: yeni/değişen bileşenler kendi test dosyalarında (`app-shell` / `mobile-nav`, `queue-cards`, `field-row` vb.). Çekmece: düğme açar, Escape kapatır, odak düğmeye döner, bağlantı tıklanınca kapanır. Kart listesi: tablo testleriyle aynı veriyi gösterir (bant, başlık, E/K, sebepler, mükerrer), bağlantı `detailHref` ile.
    - jsdom CSS uygulamaz: iki görünüm de DOM'da olacağı için mevcut tablo testleri tablo içine (`within(table)`) daraltılır; testler gevşetilmez.
    - Playwright: `e2e/playwright.config.ts`'ye mobil proje (`devices["Pixel 7"]`, Chromium; WebKit kurulu değil) ve yeni `e2e/responsive.spec.ts` (salt okunur): 360x740 ve 768x1024'te giriş, kuyruk, detay sayfalarında `document.documentElement.scrollWidth <= clientWidth`; menü çekmecesi açılıp kuyruk bağlantısıyla gezinir; kart tıklanınca detay açılır; aksiyon çubuğu görünür ve son alanı örtmez; telefonda PDF bağlantısı var, iframe yok. Mevcut masaüstü projeleri değişmez. `e2e/README.md` tablosu güncellenir.

## Kapsam dışı

- Yeni ekran veya özellik, karanlık tema, PWA / çevrimdışı, kaydırma hareketleri (swipe).
- Token değerlerinin (renk, font) değişmesi.
- WebKit/Safari e2e (sunucuda kurulu değil; Orhan Mac'te elle bakar).

## Kabul kriterleri (Themis koşar)

1. `pnpm lint typecheck test build format:check` yeşil; CI yeşil. Bileşenlerde keyfi Tailwind değeri / sabit renk yok (mevcut lint ve `ui-styles` testi).
2. Demo veriyle gerçek Chromium'da 360x740, 390x844, 768x1024, 1440x900: giriş, kuyruk, detay, toplu onay diyaloğu, ret diyaloğu; hiçbirinde yatay sayfa kaydırması yok. Ekran görüntüleri PR'da.
3. Telefonda (360) etkileşimli öğelerin yüksekliği >= 44 px (sayfa içi kart bağlantısı hariç değil; tümü). Ölçüm çıktısı PR'da.
4. Masaüstü (1440) ekran görüntüleri değişiklik öncesiyle aynı düzende (yan menü, tablo, iki sütunlu detay).
5. Mevcut e2e (19 test) + yeni mobil spec demo verisinde yeşil.
6. Klavye: masaüstünde A/E/R/J/K çalışmaya devam eder; çekmece klavyeyle açılır/kapanır, odak döner.

## Notlar Claude Code için

- Önce oku: `frontend-ui` ve `task-pr-hygiene` skill'leri, `docs/design/dashboard-v0.md`, `packages/ui/src/styles.css`, `src/app/(app)/layout.tsx`, `src/components/side-nav.tsx`, `review-queue/*`, `review-detail/*`, `e2e/*`.
- Next.js 16: API'yi kullanmadan önce `node_modules/next/dist/docs/` (ör. `viewport` export'u).
- Tailwind 4: `pointer-coarse:` ve `@utility` mevcut. Keyfi değer gerekiyorsa `styles.css`'te token/utility olarak tanımla, bileşende değil.
- Tek DOM mu, iki görünüm mü kararı (tablo/kart) gerekçesiyle PR açıklamasına yazılır.
