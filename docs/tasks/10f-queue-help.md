# Görev 10f: inceleme kuyruğunda bilgi ipuçları ve kendini tanıtan dashboard

Durum: onaylandı (Orhan, 2026-10-05: "İnceleme kuyruğu sayfasına her elemente tooltip ekle ve bilgi ver. Ayrıca sayfa title'ına da tooltip ekle. Dashboard kendini tanıtmalı."). Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/design/dashboard-v0.md`, `docs/tasks/10b-dashboard-skeleton.md`, `docs/tasks/10e-responsive-dashboard.md`, `services/app/app/loaders/confidence.py` (sebep ve bant kuralları), `docs/decisions.md`.
Skill'ler: `frontend-ui` (bağlayıcı), `task-pr-hygiene`.

## Hedef

Dashboard'u ilk kez açan biri (ör. hukuk dışından bir ortak, yeni bir inceleyici) bu ekranın ne işe yaradığını ve her parçanın ne anlattığını ekranın içinden öğrenebilsin. Ekran kalabalıklaşmaz: açıklamalar istenince açılır, bir kez okunan tanıtım kapatılabilir.

## Kapsam

1. **`InfoTip` bileşeni (`packages/ui`).** Küçük "i" düğmesi + açılan kısa açıklama kutusu.
    - Masaüstünde fareyle üstüne gelince ve klavyeyle odaklanınca görünür; dokunmatikte dokununca açılır, dışarı dokununca ya da Escape ile kapanır (yalnız hover'a dayanan tooltip telefonda çalışmaz, bu yüzden "toggletip" deseni).
    - Erişilebilir: düğmenin adı "Bilgi: <konu>" (ör. "Bilgi: Güven dağılımı"); `aria-expanded`, açıklama `aria-describedby`/`role="tooltip"` ya da toggletip için uygun canlı bölge (seçimini PR'da gerekçelendir). Odak düğmede kalır.
    - Dokunmatikte dokunma alanı 44 px (`pointer-coarse:`), görünen ikon küçük kalır. Kutu ekrandan taşmaz (360 px'te de), içerik en fazla ~3-4 kısa cümle, gerekirse sarar.
    - Konumlandırma için `@radix-ui/react-popover` (shadcn/ui ile aynı aile; zaten Radix kullanıyoruz) ya da native Popover API; seçimini gerekçelendir. Yeni bağımlılık en fazla bir tane.
    - Renk/aralık yalnız token'larla; keyfi Tailwind değeri yok.
2. **Sayfa başlığı ipucu.** "İnceleme kuyruğu" başlığının yanında `InfoTip`: bu ekranın amacı (programın karar PDF'lerinden çıkardığı künye bilgilerini insanın kontrol edip onayladığı yer; onaylanan kayıtlar YZ'nin atıf yapabileceği kaynaklar olur; resmî teyit ayrıca Yargıtay sitesinden yapılır).
3. **Kendini tanıtan karşılama kutusu.** Kuyruğun en üstünde kısa bir tanıtım kartı: Libria nedir (iş ve SGK hukuku YZ asistanı), bu panel ne işe yarar, 3 adımlık akış (kararı aç, PDF ile karşılaştır, onayla / düzelt / reddet), toplu onayın yalnız yüksek güvende olduğu.
    - "Anladım" ile kapatılır; tercih tarayıcıda saklanır (`localStorage`), sunucu verisi yok. Kapatılınca başlık ipucundan ve/veya küçük bir "Bu ekran nedir?" bağlantısından tekrar açılabilir.
    - Hidrasyon kayması olmasın: ilk sunucu çiziminde kart görünür ya da yer tutucu yok; tercih istemcide okununca kaybolur. Seçimini ve layout shift'i PR'da açıkla (tercih edilen: kapatılmış ise kart hiç görünmesin diye küçük bir istemci bileşeni + `useSyncExternalStore`).
4. **Kuyruktaki her öğeye ipucu.** Metinler `messages/tr.json` içinde `review.queue.help.*` altında; düz, hukukçu olmayana anlaşılır Türkçe, kısa.
    - Başlık altı "N karar onay bekliyor" sayısı.
    - "Toplu onayla" düğmesi (yalnız yüksek güven bandı, kendi adınla onay, her kayıt tek tek kaydedilir).
    - Sıralama ("En şüpheli önce": puanı düşük olan önce).
    - Özet kartları: "Güven dağılımı" (bant nedir, nasıl hesaplanır: kural tablosu, puan 0-100, bant en kötü sebebe göre), "En sık sebepler", "Sonuçlar" (onaylanan / reddedilen).
    - Filtreler: Güven, Mahkeme, Sebep, Dergi sayısı, Arama, "Filtreleri temizle".
    - Tablo sütun başlıkları: Güven (bant + puan), Karar (başlık), Mahkeme, Esas / Karar (künyedeki iki numara: dosya numarası ve karar numarası), Tarih, Sayı (Çalışma ve Toplum dergi sayısı), Sebepler.
    - Kart görünümünde (lg altı) sütun başlığı yok: aynı açıklamalar kartın üstünde tek bir "Bu kartta neler var?" ipucunda toplanır ya da alan etiketlerinde verilir; telefonda her kartta tekrar eden ikon kalabalığı yaratma.
    - Mükerrer işareti.
    - Sayfalama.
5. **Sebep ipuçları.** Her sebep rozeti (25 kod, `confidence.py` `RULES`) kısa bir açıklama taşır: neden işaretlendi ve inceleyici neye bakmalı. Ör. `date_from_closing`: "Tarih kararın başından değil, son kısmından (kapanış) okundu; PDF'teki karar tarihiyle karşılaştırın." Metinler `confidence.py` docstring'iyle tutarlı; hukuki yorum içermez. Rozet bağlantı içinde olduğu için (satır/kart tümü tıklanır) iç içe etkileşim yaratma: masaüstünde rozetin `title`'ı yerine erişilebilir bir çözüm seç (ör. rozet ipucu yalnız Sebep filtresinde ve "En sık sebepler" kartında `InfoTip` olarak; satırdaki rozetlerde açıklama ekran okuyucu için görünmez metin). Seçimini gerekçelendir.
6. **Yan menü / üst çubuk.** "Onay bekleyen" rozeti ve "Yakında" öğeleri (Kaynaklar, Bilgi tabanı) için kısa ipucu.

## Kapsam dışı

- Karar detayı, toplu onay diyaloğu iç adımları, giriş ekranı (sonraki görev; aynı `InfoTip` kullanılacak).
- Ürün turu kütüphanesi (adım adım vurgulayan tur), video, çoklu dil.
- Sunucuda kullanıcı tercihi saklama.

## Kabul kriterleri

- `pnpm lint typecheck test build format:check` yeşil.
- Birim testleri modüle göre: `info-tip.test.tsx` (hover/odak/tıklama/Escape/dışarı tıklama, erişilebilir ad, `aria-expanded`), karşılama kartı (kapat, localStorage, yeniden aç), kuyruk bileşenlerinde ipucunun varlığı (rol + ad ile). Mevcut testler gevşetilmez.
- Yeni metinlerin hepsi `tr.json`'da; bileşende sabit Türkçe metin yok.
- e2e (`chromium` ve `chromium-mobile`): başlık ipucu fareyle ve dokunarak açılıyor, Escape kapatıyor; karşılama kartı kapanıp yeniden yüklenince gelmiyor.
- Themis tarayıcıda doğrular: 360 / 768 / 1440 px'te yatay taşma yok, ipucu kutusu ekranda kalıyor, dokunma hedefi 44 px, masaüstü düzeni bozulmadı.
