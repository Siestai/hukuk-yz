# Görev 11d: mevzuat ekranlarında bilgi ipuçları

Durum: onaylandı (Orhan, 2026-10-10: "mevzuat sayfası da açıklayıcı tooltip içermeli"). Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/tasks/10f-queue-help.md` (örnek; `InfoTip`, `HelpTip`, `lib/help-topics.ts`, `review.queue.help.*`), `docs/tasks/11c-statute-review.md` ve `11-statute-versioning.md` (bant ve sebepler, boşluk, `amending_ref`, yürürlük tarihi dayanağı, `as_of`, yayın), `services/dashboard-web/src/components/statute-review/*`, `src/app/(app)/mevzuat/page.tsx` ve `[extractionId]/page.tsx`, `docs/decisions.md`.
Skill'ler: `frontend-ui` (bağlayıcı), `task-pr-hygiene`.

## Hedef

Mevzuat ekranlarını ilk kez açan biri (hukukçu olmayan bir ortak dahil) kuyruktaki ve madde detayındaki her parçanın ne anlattığını ekranın içinden öğrenebilsin. Karar kuyruğuna 10f'de eklenen ipuçlarının aynısı mevzuat için de olsun. Ekran kalabalıklaşmaz: açıklamalar istenince açılır.

## Kapsam

Mevcut `InfoTip` (`packages/ui`) ve `HelpTip` deseni kullanılır; yeni bileşen yazılmaz, yeni bağımlılık eklenmez. Karar ipuçlarının metinleri değişmez. Mevzuat metinleri `messages/tr.json` içinde `review.statutes.help.*` altındadır; konu adları tipli bir listede tutulur (`lib/help-topics.ts` gibi, mevzuata ait ayrı liste ya da `HelpTip`'in ad alanı parametresi; seçimi PR'da gerekçelendir, kopya bileşen yaratma). Bileşende sabit Türkçe metin yok. Metinler düz Türkçe, kısa (en çok ~3-4 cümle); hukuk terimleri ilk geçtiği yerde kısaca tanımlanır: **yürürlük** (metnin geçerli olmaya başladığı gün), **mülga** (madde kanundan kaldırılmış), **değiştiren kanun** (maddenin metnini değiştiren sonraki kanun), **geçici madde** (belli bir geçiş dönemi için konmuş madde), **ek madde** (sonradan araya eklenmiş madde), **kenar başlığı** (maddenin yanındaki kısa başlık), **dipnot** (resmî metindeki not).

1. **Sayfa başlığı ipuçları.**
    - Kuyruk (`/mevzuat`, başlık 4 duruma göre: bekleyen / yayındaki / reddedilen / tüm maddeler): bu ekranın amacı (programın kanun kopyalarından çıkardığı her maddenin zaman çizgisini insanın kontrol edip onayladığı yer; yayına giren madde, YZ'nin "olay tarihinde geçerli metin" cevabının tek kaynağı olur; resmî teyit ayrıca Resmî Gazete / mevzuat.gov.tr'den yapılır).
    - Madde detayı başlığı: bu madde için ekranın ne gösterdiği ve onay / ret sonucu.
2. **Kuyruktaki her öğeye ipucu.**
    - Başlık altı "N madde onay bekliyor" sayısı (ve diğer sekmelerdeki sayı cümleleri).
    - Kanun sekmeleri (4857, 5510) ve durum sekmeleri (bekleyen / yayında / reddedilen / tümü), her biri kısa.
    - "Toplu onayla": yalnız Yüksek güven bandı seçiliyken, kendi adınıza, her madde tek tek kaydedilir.
    - Filtreler: Kanun, Güven (band), Durum (varsa), Arama (madde no ya da kenar başlığı), "Filtreleri temizle".
    - Özet / güven kartı: band nedir (kuralı kısaca: bant en kötü sebebe göre), bant sayıları ve bekleyen / yayında / reddedilen sayıları.
    - Tablo sütun başlıkları: Güven, Madde, Sürümler (sürüm ve boşluk sayısı ne demek), Son kopya (maddenin alındığı en yeni kanun kopyasının tarihi), Sebepler, Durum.
    - Kart görünümü (lg altı): sütun başlığı yok; açıklamalar kartın üstünde tek bir "Bu kartta neler var?" ipucunda toplanır. Her kartta tekrar eden ikon kalabalığı yok.
    - Sebep rozetleri: iç içe etkileşim yaratmamak için 10f'deki çözüm aynen izlenir (satırdaki rozette ekran okuyucu için görünmez metin, `InfoTip` yalnız ayrı yerlerde). Mevzuat sebep kodlarının (statute timeline loader) her birine gündelik dille açıklama yazılır; tanımsız bir kod ipucusuz kalır, hata vermez.
3. **Madde detayında ipucu.**
    - **Güven ve sebepler** kartı: bant ne demek, "Neden bu bantta" sebepleri, "Diğer uyarılar".
    - **Zaman çizgisi** başlığı: çizgi maddenin sürümlerini ve boşluklarını eskiden yeniye gösterir. Sürüm = metnin belli bir tarih aralığında geçerli olan hâli. **Boşluk** = metnin elimizde olmadığı dönem (metin gösterilmez; o dönemde değişiklik olduğu biliniyor ama hâlinin ne olduğu bilinmiyor). Tarih aralığı: başlangıç (`valid_from`) ve bitiş (`valid_to`; son sürümde "bugün"). Değişiklik türü rozetleri: ilk metin / değişik / ek / mülga (her biri kısa). Değiştiren kanun ve yürürlük tarihi.
    - **Seçili sürüm paneli**: kenar başlığı, **dipnot**, **dayanak** (başlangıç tarihinin neye dayandığı: kayıt / istisna / tablo ve hangi kopyalar), "Değiştiren kanunlar", "Metnin göründüğü kopyalar", "Bu sürümün uyarıları".
    - **Önceki sürümle fark**: silinen kelimeler üstü çizili, eklenenler altı çizili; ilk sürümde fark yok; iki sürüm arasında boşluk varsa fark iki bilinen metin arasındadır.
    - **Tarih sorgusu** ("Bu madde şu tarihte nasıldı?"): bir tarih seçince o tarihte hangi metnin geçerli olduğu çizgide işaretlenir; olası cevaplar (metin bulundu / metin elde yok / mülga / henüz yürürlükte değil) ve "son kopyadan sonraki tarih" uyarısı.
    - **Onayla / Reddet** (yalnız bekleyen maddede): onay maddeyi yayına alır; ret nedeni zorunludur. Düzelterek onay yoktur: çizelge elle düzenlenmez, hatalı çizelge reddedilir ve düzeltme kod tarafına gider.
    - **Yayında bildirimi** (`LiveNotice`, "Bu maddenin yayındaki metni başka bir kayda ait"): yayındaki kayıt neden başka, bu kaydı onaylamak ne yapar.
    - Önceki incelemeler / durum şeridi: durum ne demek (karar ekranındaki şerit ortak bileşense yeni metin kararın ipucunu bozmaz).
4. **Yan menü** "Mevzuat" öğesi: zaten ipucu varsa yeni iş yok; yoksa kısa ipucu eklenir (karar için 10f'de eklenmiş "Onay bekleyen" rozetinin davranışı değişmez).

## Kapsam dışı

- Karar ekranları, giriş ekranı, ürün turu, çoklu dil.
- Tanıtım karşılama kartı (yalnız sayfa başlığı ipucu; kart pahalıysa yok, ucuz değilse eklenmez).
- Backend / API / OpenAPI değişikliği, yeni bağımlılık, veri modeli.
- Sebep sözlüğünün hukuki yorum içermesi: metinler yalnız ekranın ne gösterdiğini ve neye bakılacağını anlatır.

## Kabul kriterleri

- `pnpm lint typecheck test build format:check` yeşil; backend'e dokunulmaz.
- Birim testleri modüle göre, bileşenin yanında `*.test.tsx`: mevzuat kuyruğu bileşenlerinde ve detay bileşenlerinde ipucunun varlığı (rol + "Bilgi: <konu>" adıyla), kart görünümünde tek "Bu kartta neler var?" ipucu, bilinmeyen sebep kodunda ipucu çıkmaz ve hata vermez, her konu adının `tr.json`'da metni var (tip ya da test ile). Mevcut testler gevşetilmez.
- Yeni metinlerin hepsi `tr.json`'da.
- Themis tarayıcıda doğrular: 360 / 768 / 1440 px'te ipucu masaüstünde fare / odakla, dokunmatikte (coarse pointer) dokunarak açılıyor; kutu 360 px'te taşmıyor, yatay kaydırma yok, dokunma hedefi 44 px, masaüstü düzeni bozulmadı. Kuyruk ve detay için ipucu açıkken ekran görüntüsü PR'da.
