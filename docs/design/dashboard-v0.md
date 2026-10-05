# Dashboard tasarım yönü v0 (2026-10-03)

Durum: onaylandı (Orhan, 2026-10-03). Görev 10b ve 10c bu belgeye göre yapılır. Marka kesinleşince yalnız token değerleri ve ad değişir, bileşenler değişmez.

Kaynak taslak (repo dışında; karar metni ve dergi PDF'i içerdiği için commit edilmez): `hukuk-yz/design/2026-10-03-dashboard/`.

## Ad ve logo

- Çalışma adı **Libria** (test adı; Orhan, 2026-10-03). Ad tek yerde: `messages/tr.json` → `brand.name`, logo `packages/ui` içinde tek bileşen. Değişirse iki dosya değişir.
- Logo taslağı: terazi işareti, tek renk, `currentColor` ile boyanır.

## Yön

Yön A (kurumsal) temel alınır: açık zemin, beyaz yüzeyler, beyaz yan menü, orta yoğunluk. Detay ekranındaki karar başlığı ve "Çıkarılan metin" sekmesi serif yazıyla (B yönünden).

## Token'lar (`packages/ui`, CSS değişkenleri → Tailwind teması)

| token                                    | değer                             | kullanım                           |
| ---------------------------------------- | --------------------------------- | ---------------------------------- |
| `--bg`                                   | `#F4F6F9`                         | sayfa zemini                       |
| `--surface` / `--surface-2` / `--sunken` | `#FFFFFF` / `#F8F9FB` / `#E9EDF2` | kart, tablo başlığı, PDF zemini    |
| `--ink` / `--ink-2` / `--ink-3`          | `#16202E` / `#4A5668` / `#7A8596` | metin, ikincil metin, soluk        |
| `--line` / `--line-2`                    | `#DDE3EA` / `#EEF1F5`             | kenar, satır ayırıcı               |
| `--primary` / `--primary-soft`           | `#0B2A5B` / `#E6ECF5`             | ana düğme, seçili durum (lacivert) |
| `--accent`                               | `#C9A227`                         | odak halkası (altın)               |
| `--high` / `--high-soft`                 | `#24704F` / `#E3F1EA`             | yüksek güven                       |
| `--medium` / `--medium-soft`             | `#8A5D00` / `#FBF0D9`             | orta güven, "Kontrol et" işareti   |
| `--low` / `--low-soft`                   | `#A3392A` / `#F8E4E0`             | düşük güven, hata, ret             |
| `--ui-radius` / `--ui-radius-sm`         | `8px` / `6px`                     |                                    |
| `--row`                                  | `44px`                            | tablo satır yüksekliği             |

Yazı: IBM Plex Sans (arayüz), IBM Plex Mono (esas/karar no, tarih, sayılar; hizalı karşılaştırma için), IBM Plex Serif (detay başlığı, karar metni, giriş alıntısı). Fontlar `next/font` ile kendi sunucumuzdan; dış CDN yok (CSP).

## Ekran kuralları

- Durum sekmeleri (10g): kuyruğun üstünde Bekleyen / Onaylanan / Reddedilen / Tümü, sayılarıyla; bağlantı tabanlı gezinme (`nav`, `aria-current="page"`), seçim `?durum=onaylanan|reddedilen|tumu`. Onaylanan / Reddedilen / Tümü'nde durum rozeti, İnceleme (tarih, inceleyen) ve Ret notu sütunları, en yeni inceleme önce; toplu onay ve özet kartları yalnız Bekleyen'de. Her sekme, sütun ve başlık bir bilgi ipucu taşır. Detayda durum şeridi; geri bağlantısı ve J/K gelinen sekmede kalır.
- Kuyruk: üstte bant dağılımı (yatay çubuk + üç sayı, tıklayınca filtre) ve en sık 5 sebep; altında filtreler ve tablo. Varsayılan sıralama en şüpheli önce. Sebepler okunur etiketle (`enums.reason.*`), en fazla 2 + "+N".
- "Toplu onayla" düğmesi her zaman görünür, yalnız yüksek bant filtresinde etkin.
- Detay: sol alanlar + sabit aksiyon çubuğu (Reddet, Düzelt, Onayla; kısayollar A/E/R, J/K sonraki/önceki), sağ PDF / çıkarılan metin sekmeleri. Şüpheli alan "Kontrol et" işaretli; üstte sebebin açıklaması. Dergi özeti "Editoryal içerik, resmî kaynak değil" etiketli kesik çerçevede.
- Toplu onay: sayı büyük; "kendi adımla onaylıyorum" kutusu işaretlenmeden düğme kapalı; "teyit edilmemiş olarak yayınlanır" notu; ilerleme, yayınlanan / çakışan / başarısız sayaçları, durdur.

## Mobil (2026-10-05, görev 10e)

Kırılımlar Tailwind varsayılanı: telefon `< md` (768), tablet `md`-`lg`, masaüstü `>= lg` (1024). Masaüstü düzeni yukarıdaki gibi kalır; dar ekranda içerik yeniden akar.

- Kabuk: `lg` altında yan menü yerine üstte yapışkan çubuk (logo + ad, bekleyen sayısı, menü düğmesi); düğme soldan açılan çekmeceyi açar (aynı gezinme, kullanıcı ve çıkış). Sayfa dolgusu `p-4` / `md:p-6` / `lg:p-8`.
- Kuyruk: başlık ve eylemler alt alta, eylemler tam genişlik. Özet kartları telefonda tek, tablette 2, masaüstünde 3 sütun. Filtreler telefonda "Filtreler (N)" düğmesinin arkasında, filtre etkinse açık. `xl` altında tablo yerine kart listesi (`md`-`xl` arası 2 sütun, altında 1; tablo `xl` (1280) ve üstünden, çünkü yan menüyle içerik alanı 1024'te 704 px; incelenmiş sekmelerde inceleme bilgisi ve ret notu ayrı sütun değil, Durum sütununda rozetin altında; tüm kart bir bağlantı: bant + skor, başlık, mahkeme · daire, E/K · tarih, dergi sayısı, en fazla 2 sebep + "+N", mükerrer işareti). Sayfalama telefonda önceki / sonraki ve "x / y".
- Detay: başlık `text-xl`; alan etiketi değerin üstünde (`md`'de 1/3 - 2/3); aksiyon çubuğu ekranın altında yapışkan, üç düğme eşit genişlikte tek satır, kısayol ipuçları gizli (kısayollar çalışır), alt güvenli alan dolgulu. PDF telefonda "PDF'i yeni sekmede aç" bağlantısı, `md` ve üstünde gömülü görüntüleyici (`dvh` yüksekliği). Düzenleme formu tek sütun.
- Diyaloglar ekran kenarlarından küçük boşlukla, yükseklik sınırlı, içeride kaydırmalı; düğmeler alt alta tam genişlik, ana eylem üstte.
- Giriş: sol panel `lg` altında yok, logo ve ad formun üstünde.
- Dokunma: `pointer: coarse` cihazlarda düğme, input, select, sekme ve gezinme en az 44 px; input yazısı telefonda 16 px; yakınlaştırma kapatılmaz.

## Bilgi ipuçları (2026-10-05, görev 10f)

- `InfoTip` (`packages/ui`): küçük "i" düğmesi, adı "Bilgi: <konu>". Fare üstüne gelince ve klavye odağında açılır; dokunma ya da tıklama sabitler (telefonda hover yok), Escape, dışarı basma ya da ikinci tıklama kapatır; odak düğmede kalır. Ekran okuyucu için görünür kutu `aria-hidden`, metin düğmenin yanındaki `role="status"` bölgesine yalnız düğmeye basılınca yazılır (toggletip). Kutu `w-72`, ekran kenarından 8 px içeride kalır; dokunmatikte düğme 44 px, görünen ikon küçük.
- Metinler `review.queue.help.*`: sade Türkçe, 1-4 kısa cümle. Sebep açıklamaları `review.queue.help.reason.<kod>`; satırdaki rozetlerde ikon yok (satır tıklanır), açıklama ekran okuyucu için görünmez metin; görünür hâli "Sebep" filtresinde ve "En sık sebepler" kartında.
- Karşılama kutusu (`WelcomeCard`): "Anladım" ile kapanır, tercih `localStorage`'da; sunucu HTML'inde yok (kapatmış biri hiç görmez), ilk kez gelen kişi hidrasyondan hemen sonra görür. "Bu ekran nedir?" düğmesi geri açar.

- Sol panelde her sayfa yüklemesinde rastgele bir ünlü söz ve sahibi gösterilir (Orhan, 2026-10-03).
- Liste: `docs/design/login-quotes.tr.json`, 100 söz (`text`, `author`). Kaynak tartışmalı atıflar elendi; Türkçe atasözleri "Atasözü" olarak.
- Uygulamada `messages/tr.json`'a değil, dile göre içerik dosyasına (`services/dashboard-web/content/login-quotes.<locale>.json`) girer; başka dil eklenirse kendi listesi olur.
- Seçim sunucuda yapılır (hidrasyon farkı olmasın), sayfa önbelleğe alınmaz.
