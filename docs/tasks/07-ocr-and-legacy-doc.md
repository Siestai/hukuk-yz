# Görev 07: Taranmış Mevzuat'ın OCR'ı ve eski `.doc` dosyalarının okunması

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/tasks/03-ingest.md` (tip tespiti, kalite eşikleri, `files.jsonl`, önbellek), `packages/ingest/hukuk_ingest/{extract,quality,pipeline}.py`, `AGENTS.md` (Data).
Üstüne oturduğu iş: Görev 03 (`hukuk-ingest scan`). Görev 05/06'ya dokunmaz.

## Hedef

`hukuk-ingest scan` çıktısında Mevzuat'ta **okunamayan dosya kalmasın**:
- `needs_ocr` durumundaki 46 dosya (30 PDF + 16 görsel, 171 sayfa) yerel Tesseract OCR ile metne çevrilir.
- `unsupported/legacy_doc` durumundaki 11 dosya (9 Mevzuat + karar arşivinde uzantısı `.pdf` olan 2 OLE2 `.doc`) saf Python ile okunur.

Önemlisi `.doc` tarafı: 5510 sayılı Kanun'un 27.09.2016 ve 04.05.2017 hâlleri ile **mülga 506 sayılı Kanun** (01.10.2008 öncesi hâli) yalnızca `.doc` olarak var. Bunlar mevzuat sürümleme (md. 4) için kritik metinler.

## Neden yerel OCR (LLM vision değil)

- **KVKK (md. 31):** Görüş ve genel yazılarda gerçek kişi adı, TC kimlik no, işyeri sicil no ve plaka var (probe'da görüldü). LLM vision bu görüntüleri yurt dışı bir API'ye gönderir. Yerel Tesseract'ta veri sunucudan çıkmaz.
- **Kalite yeterli:** aşağıdaki probe'da 46 dosyanın 45'i ilk geçişte, sonuncusu ikinci geçişte okunur metin verdi.
- **Maliyet ve tekrar edilebilirlik:** ücretsiz, deterministik, sürüm sabitlenebilir.
- LLM vision bu görevde yok. Kalitesi düşük kalan sayfa için gerekirse ayrı bir karar ve görev olur (Orhan onayı + KVKK değerlendirmesi).

## Probe (Themis, 2026-10-02, sunucuda)

Tesseract 5.5.3, `tur` modeli, 300 dpi gri tonlama, `--psm 3`; kurulum conda-forge (root gerekmedi).

| Grup | Dosya | Sayfa | Sonuç |
|---|---|---|---|
| `no_text_layer` PDF | 21 | ~85 | 20'si ilk geçişte okundu; 1'i 4 karakter verdi (aşağıda) |
| `bad_ocr_layer` PDF | 5 | ~49 | hepsi okundu (stopword 0.078-0.120) |
| `partial_text_layer` PDF | 1 | 20 | okundu (0.077) |
| görsel (jpg/png, WhatsApp fotoğrafları dahil) | 16 | 16 | hepsi okundu (0.068-0.153) |
| **Toplam** | **46** | **171** | ~27 dk, ~9,3 sn/sayfa, 2 çekirdek |

- Stopword oranı (Görev 03'teki ölçü) okunan 45 dosyada **0.068-0.170**; Görev 03'ün `bad_ocr_layer` eşiği 0.03, `borderline` bandı 0.03-0.06. Hepsi eşiğin rahatça üstünde.
- Elle kontrol (6 örnek): SGK genel yazıları ve Resmî Gazete tebliği neredeyse hatasız; antet/logo/imza bölgelerinde birkaç satır çöp karakter, WhatsApp fotoğraflarında ara ara harf hatası.
- **Başarısız örnek:** `Görüş/KEP'ten Gönderilen Tebligatlara İPC Uygulanması Hakkında Görüş.pdf`: telefonla çekilmiş, düşük kontrastlı, hafif eğik sayfa. Varsayılan eşikleme (Otsu) metni siliyor; Tesseract "Too few characters" diyor. **Sauvola eşiklemesiyle (`-c thresholding_method=2`) ilk sayfa 3.393 karakter, temiz** (`thresholding_method=1` ile 5.059 karakter). Bu yüzden ikinci geçiş zorunlu.

`.doc` probe'u (`olefile` + Word 97 piece table, saf Python):

| Dosya | Karakter | Stopword |
|---|---|---|
| `Kanunlar/1.5.5510 (27.09.2016).doc` | 568.305 | 0.146 |
| `Kanunlar/Eskiler/5510 Tarih 04.05.2017.doc` | 598.889 | 0.147 |
| `Kanunlar/MÜLGA 506 ... (01 10 2008 öncesi haliyle).doc` | 307.206 | 0.141 |
| `Genelge/Eskiler/2011-51.doc` | 138.168 | 0.121 |
| `Genelge/2020-39 ... ekleri/Çalışma Talimatı.doc` | 455.678 | 0.127 |
| `Genel Yazı/Eskiler/Sahta Şüpheli ... 2012-2 eki-Genel yazı.doc` | 25.463 | 0.123 |
| `Genelge/2020-39 ... ekleri/EK.6 Bilgi belge isteme.doc` | 2.465 | 0.169 |
| `Genelge/2020-39 ... ekleri/EK.1.doc` | 1.163 | 0.048 (form) |
| `Genelge/2020-39 ... ekleri/EK.7 Oda kayıt.doc` | 1.538 | 0.008 (boş form) |
| arşiv `81.Sayı/ASIL İŞVEREN ALT İŞVEREN_2.pdf` (OLE2) | 35.388 | 0.147 |
| arşiv `86. Sayı/İŞYERİ İŞLETME AYRIMI.pdf` (OLE2) | 17.201 | 0.116 |

11/11 okundu; Türkçe karakterler temiz (8-bit parçalar `cp1254`, diğerleri UTF-16LE).

## Kapsam

### 1. OCR (`packages/ingest`)

- Yeni modül `hukuk_ingest/ocr.py`. Tesseract **harici ikili** olarak `subprocess` ile çağrılır. İkili yolu ve tessdata yolu ayarlanabilir (`HUKUK_TESSERACT`, `TESSDATA_PREFIX`); varsayılan `PATH`'teki `tesseract`. Python sarmalayıcı (`pytesseract`) eklenmez.
- PDF sayfaları **`pypdfium2` ile** 300 dpi gri tonlamaya render edilir (zaten bağımlılık; poppler gerekmez). Görüntüyü Tesseract'a vermek için dosya ya da stdin kullanılabilir. `Pillow` yalnızca workspace'te zaten varsa kullanılır; yoksa `pypdfium2`'nin kendi PNG/PPM çıktısı kullanılır, yeni bağımlılık eklenmez.
- **Geçişler** (sayfa başına):
  1. `-l tur --psm 3`.
  2. Sayfa metni zayıfsa (`< 50` karakter ya da sayfa stopword oranı `< 0.03`): `-c thresholding_method=2` (Sauvola) ile tekrar; daha iyi sonuç kalır.
  3. Hâlâ zayıfsa yön tespiti (`--psm 0`, OSD) yapılır; döndürme ≠ 0 ise döndürülmüş görüntüyle 1. geçiş tekrarlanır.
  Hangi geçişin kullanıldığı sayfa bazında kaydedilir.
- OCR **yalnızca** `needs_ocr` durumuna düşen dosyalarda çalışır (`no_text_layer`, `bad_ocr_layer`, `partial_text_layer`, `image`). Metin katmanı sağlam PDF'lere dokunulmaz. `partial_text_layer`'da yalnızca metinsiz sayfalar OCR'lanır, diğer sayfaların metin katmanı korunur.
- Sonuç: OCR metni Görev 03'ün kalite ölçüsünden (`quality.measure` + `judge`) geçer.
  - İyi: `status=ok`, `extractor="tesseract"`, `extractor_version` = Tesseract sürümü + `tur` modelinin sha256'sının ilk 12 hanesi, `warnings` içinde `ocr`; sayfa bazlı `ocr_pass` bilgisi `quality` altında.
  - Kötü: `status=needs_ocr`, `reason=ocr_low_quality` (bu dosya rapora düşer, elle bakılır).
- Tesseract kurulu değilse OCR adımı atlanır: dosya `needs_ocr` kalır, `warnings: [ocr_unavailable]`, tarama hata vermez. `hukuk-ingest scan --no-ocr` bayrağı OCR'ı bilinçli kapatır.
- Önbellek: OCR sonucu Görev 03'ün `data/extracted/` önbelleğine yazılır; önbellek anahtarına Tesseract sürümü, model hash'i ve OCR ayarları girer. İkinci tarama OCR'ı tekrarlamaz (ilk tam koşu ~27 dk, sonrakiler saniyeler). `PIPELINE_VERSION` artırılır.
- Paralellik: dosya başına süreç havuzu (varsayılan `os.cpu_count()`), Tesseract'ın kendi iş parçacığı `OMP_THREAD_LIMIT=1` ile sabitlenir.

### 2. `.doc` okuyucu (`packages/ingest`)

- Yeni modül `hukuk_ingest/legacy_doc.py`: `olefile` ile `WordDocument` + `0Table`/`1Table` akışlarından **piece table (CLX/PlcPcd)** okunur. 8-bit parçalar `cp1254`, diğerleri UTF-16LE. Alan kodları (`\x13 … \x14 … \x15`) sonuç metni korunarak temizlenir, `\r` → satır sonu, `\x07` (tablo hücresi) → sekme.
- Yeni bağımlılık: yalnızca `olefile` (saf Python, küçük). LibreOffice / antiword / catdoc yok.
- Şifreli `.doc` (`fEncrypted`) → `status=unsupported`, `reason=encrypted_doc`. Biçim dışı (Word 6/95, `nFib < 0xC1`) → `unsupported`, `reason=legacy_doc_pre97`.
- Sonuç Görev 03 kalite ölçüsünden geçer; `extractor="olefile-piece-table"`.
- `extract.py`'deki `DetectedType.DOC → unsupported/legacy_doc` dalı bu okuyucuya bağlanır. Uzantısı `.pdf` olup içeriği OLE2 olan iki arşiv dosyası da içerik tespiti sayesinde aynı yoldan geçer (`extension_mismatch` korunur).

### 3. Rapor

`summary.md`/`summary.json` ek bölüm: OCR'lanan dosya sayısı, sayfa, geçiş dağılımı (1/2/3), süre; `ocr_low_quality` listesi; `.doc` okunan / okunamayan listesi. Rapor metin içermez (Görev 03 kuralı).

### 4. Kurulum

- **CI:** `ci.yml`'e `apt-get install -y tesseract-ocr tesseract-ocr-tur` adımı; OCR entegrasyon testleri CI'da gerçekten koşar.
- **Docker (`services/app/Dockerfile`):** ingest bugün imajda CLI olarak var ama tarama imajdan koşulmuyor. Bu görevde imaja Tesseract **eklenmez** (imaj boyutu); ingest worker'a taşındığında eklenir. Not olarak `AGENTS.md`'ye yazılır.
- **Sunucu (Themis):** conda-forge `tesseract` (root gerekmez); kurulum komutu `AGENTS.md`'de.

## Kapsam dışı

- LLM vision / bulut OCR.
- Karar arşivinde OCR (6.334 karar metin katmanlı; gerek yok).
- OCR metninin düzeltilmesi (yazım düzeltme, antet/imza temizliği). Temizlik `clean.py`'nin genel kurallarıyla sınırlı kalır.
- KB'ye yükleme ve mevzuatın madde düzeyinde ayrıştırılması (sonraki görev). Form şablonları (`EK.1`, `EK.7`) da okunur; KB'ye girip girmeyecekleri o görevin kararı.
- Karar arşivindeki 2 `.doc`'un Görev 04 parser'ından geçirilip KB'ye yüklenmesi: parser girdisi `files.jsonl` olduğu için bu görevden sonra yeniden koşu yeterli olmalı; doğrulama ve yükleme bu görevde yok, rapora not düşülür.

## Kabul kriterleri (Themis koşar)

- [ ] `make lint`, `make typecheck`, `make test` temiz; CI yeşil (CI'da Tesseract kurulu, OCR testleri koşar).
- [ ] Birim testleri: geçiş seçimi (zayıf → Sauvola → OSD) sahte Tesseract çalıştırıcıyla; Tesseract yokken `ocr_unavailable`; `--no-ocr`; önbellek anahtarı model/sürüm/ayar değişince değişir; `partial_text_layer`'da yalnızca metinsiz sayfalar OCR'lanır.
- [ ] `.doc` testleri: küçük, sentetik (kişi adı yok) `.doc` fixture'ı: 8-bit ve UTF-16 parça, alan kodu, tablo hücresi, şifreli dosya bayrağı. Gerçek korpus dosyası commit edilmez.
- [ ] Entegrasyon testi: commit edilen tek sayfalık **sentetik** taranmış görüntü/PDF (Türkçe metin, kişi verisi yok) OCR'dan `ok` çıkar ve beklenen kelimeleri içerir.
- [ ] Tam korpus (`hukuk-ingest scan data/drive`, Themis sunucuda):
  - Mevzuat'ta `needs_ocr` **≤ 1**, `unsupported` **0** (`.doc` 11/11 `ok` ya da gerekçeli `unsupported`).
  - KEP görüşü (yukarıdaki başarısız örnek) 2. geçişle `ok`.
  - 5510 (2016, 2017) ve 506 `.doc`'larında madde başlıkları (`MADDE 4`, `MADDE 80` vb.) metinde var.
  - Karar arşivi sayıları değişmez (6.334 PDF `ok`), artı 2 `.doc` `ok`.
  - İkinci koşu önbellekten, OCR yapmadan (< 2 dk).
- [ ] Themis 5 OCR + 3 `.doc` çıktısını elle okur, PR'a dosya adı + 1 satır yorum yazar (metin alıntısı yok).
- [ ] Rapor ve loglar metin ve kişi verisi içermez.

## Açık sorular

1. ~~`ocr_low_quality` kalan dosya olursa ne yapılır?~~ **Karar (Orhan, 2026-10-02):** dosya `needs_ocr/ocr_low_quality` olarak kalır, elle yazılmaz ve atlanmaz; ortaklardan temiz kopyası istenir. Rapor bu listeyi ayrıca verir ki ortaklara gidecek istek doğrudan oradan çıksın.
2. Görüş yazılarında kişi adı / TC no var. KB'ye yüklenirken maskelenmesi gerekir (md. 31). Bu görev metni olduğu gibi `data/extracted/` (gitignored) altına yazar; maskeleme KB yükleme görevinde. Onay? (Orhan)
