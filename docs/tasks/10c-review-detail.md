# Görev 10c: Karar detay ekranı, onay/ret ve toplu onay

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/tasks/09-review-api.md` (aksiyonlar, toplu onay sözleşmesi), `docs/tasks/10a-dashboard-api-prep.md` (hata kodları, PDF endpoint'i), `docs/tasks/10b-dashboard-skeleton.md`, `docs/data-model.md` §4 (durum makinesi).
Skill'ler: `frontend-ui` (bağlayıcı), `task-pr-hygiene`.
Önce: Görev 10b merge edilmiş olmalı.

## Hedef

Reviewer'ın bir kararı orijinal PDF'le yan yana görüp onaylaması, düzelterek onaylaması veya reddetmesi; yüksek güven bandını güvenli biçimde toplu onaylaması. Bu görevle dashboard ortakların gerçek inceleme yapabileceği hale gelir.

## Kapsam

1. **Detay ekranı** `/kararlar/[extractionId]` (kuyruk satırları buraya bağlanır; filtreler URL'de taşınır, "kuyruğa dön" filtreyi korur).
   - Sol: çıkarılmış alanlar (mahkeme, daire, BAM bölgesi, E/K, tarih, ilgili kanun/maddeler, sonuç, anahtar kelimeler, dergi sayısı), güven skoru ve sebepleri, parser uyarıları, kaynak durumu (`source_status`).
   - Sağ: sekmeler. **PDF** (`/api/review/decisions/{id}/file`, tarayıcının PDF görüntüleyicisiyle `iframe`/`object`; 415 `file_not_previewable` ve 404 `file_not_found` için açıklayıcı boş durum) ve **Çıkarılmış metin** (tam metin; dergi özeti ayrı kutuda, "editoryal içerik" etiketiyle).
   - Mükerrer grup: aynı gruptaki diğer extraction'lar (band, skor, metin uzunluğu), her birine bağlantı.
   - Önceki incelemeler: kim, ne zaman, karar, not, düzeltilen alanlar.
2. **Aksiyonlar** (yalnız kayıt kuyruktaysa, `source_status = analyzed`):
   - Onayla.
   - Düzelt ve onayla: alanlar düzenlenebilir forma döner; yalnız değişen alanlar `edits` olarak gider; tarih ve E/K için basit istemci doğrulaması (asıl doğrulama API'de, 422 `validation_error` alanları formda gösterilir).
   - Reddet: not zorunlu (boşsa gönderilmez).
   - Her aksiyon onay diyaloğu ister değil; yalnız reddet ve düzelt-onayla özet gösterir. Başarıda bildirim + aynı filtrelerdeki **sıradaki** bekleyen kayda geçiş (yoksa kuyruğa dönüş).
   - Hatalar koddan: `review_conflict` ("başkası bu kaydı az önce işledi", sayfayı yenile), `decision_conflict` (çakışan karara bağlantıyla), `validation_error`.
   - Klavye kısayolları: onayla, reddet, sonraki/önceki (kısayollar ekranda yazılı, form alanına yazarken çalışmaz).
3. **Toplu onay** (kuyruk ekranında, yalnız `band = high` filtresi seçiliyken görünür):
   - Diyalog: o anki filtrelerle eşleşen kayıt sayısı ve ilk birkaç örnek; "N kaydı onaylıyorum" onay kutusu.
   - Çağrı sözleşmesi Görev 09'daki gibi: `expected_count` ekrandaki sayı, `limit` 100, `next_cursor` `null` olana kadar döngü. İlerleme çubuğu, "durdur" düğmesi (o anki parti bittikten sonra durur).
   - `bulk_count_changed` gelirse döngü durur, yeni sayı gösterilir, kullanıcı yeniden onaylar.
   - Sonuç raporu: yayınlanan, çakışan (bağlantılarla), başarısız (sebep koduyla). Rapor kapanınca kuyruk ve özet yenilenir.
4. **Testler.** Vitest + Testing Library: detay ekranı (veri, PDF yok durumu), her aksiyonun doğru gövdeyi göndermesi, ret notu zorunluluğu, düzeltmede yalnız değişen alanların gitmesi, çakışma hata kodlarının gösterimi, toplu onay döngüsü (çok parti, `bulk_count_changed`, durdur).

## Kapsam dışı

- Karar teyidi (Görev 06) sonuçlarının ekranda gösterimi ve elle teyit; ayrı görev.
- PDF üzerinde vurgulama/işaretleme, metin-PDF eşleme.
- Onaylanmış kararı geri alma veya yeniden düzenleme (yeni sürüm akışı ayrı görev).
- Düşük/orta bandın toplu onayı (Görev 05 kuralı: tek tek).

## Kabul kriterleri (Themis koşar)

1. CI yeşil (Python + pnpm işleri).
2. Uçtan uca elle deneme (CI compose'unda veya yayın öncesi ortamda): bir kaydı onayla, birini düzelterek onayla, birini reddet, yüksek bantta 2 partilik toplu onay; her birinden sonra `review` ve `decision` satırları API'den kontrol edildi. Ekran görüntüleri PR'da.
3. İki sekmede aynı kayda aksiyon: ikincisi `review_conflict` mesajı gösterir, çift kayıt oluşmaz.
4. `frontend-ui` grep kontrolleri (DB yok, sabit renk yok, sabit metin yok) geçer.

## Notlar Claude Code için

- Toplu onayın veri bütünlüğü API'de; UI sözleşmeye harfiyen uyar, kendi sayım/filtre mantığı üretmez.
- Yeni metinler `messages/tr.json`'a, ekran bazlı anahtarlarla.
- Commit et, push etme.
