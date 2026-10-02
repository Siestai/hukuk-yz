# Görev 03: Ingest çekirdeği (tip tespiti + metin çıkarma)

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `AGENTS.md` (Data, Decision archive findings), `docs/architecture.md` §3-4 (`packages/ingest`, ingest akışı), `docs/roadmap.md` Faz 1 hafta 1-2, `docs/data-model.md` §3 (`ingest_file`, `extraction.raw_text_ref`).
Üstüne oturduğu iş: Görev 01 (iskelet), Görev 02 (şema).

## Spike bulguları (Themis, 2026-10-02, sunucuda `pypdfium2` ile tam korpus)

- 6.558 `.pdf` uzantılı dosya, 2 çekirdekte **58 sn**. Korpus küçük; performans sorun değil.
- Karar arşivi: 6.334 metinli PDF, 6 HTML (`<!doctype`), 2 OLE2 `.doc`. `AGENTS.md` ile birebir.
- **E-imzalı SGK genelgeleri `pypdfium2` ile temiz çıkıyor** (ör. 2020/20, 228 sayfa; yalnızca imza satırında tek `???` dizisi). `AGENTS.md`'deki "scrambled" notu `pdftotext` içindi; bu görevde düzeltilir.
- Asıl sorun Mevzuat'taki **taramalar**: 25 PDF'te metin katmanı yok (0 karakter), ~5 PDF'te bozuk OCR katmanı var (`bo印dlgle料le`, `ııla kunılaıı`). Buna 16 görsel (jpg/png) eklenir. Toplam ~46 dosya, hepsi Mevzuat.
- UYAP `.udf` = zip(`content.xml` CDATA metin + `sign.sgn` e-imza).
- PDF metni `\r\n` satır sonlu. Dergi sayfa başlığı (`Yargıtay Kararları – Çalışma ve Toplum, 2014/4`) 43. sayıda da var, yalnız 76-90'da değil (parser görevi için not).

## Hedef

`data/drive/` altındaki 6.626 dosyanın her biri için **içerikten** tip tespiti ve düz metin çıkarımı yapan, DB'den bağımsız bir `packages/ingest` kütüphanesi ve bunu tüm korpusa koşan bir CLI. Çıktı: sha256 ile adreslenmiş metin önbelleği + makine okunur rapor. Parser (karar alanları) ve DB'ye yazma bu görevde yok; ikisi de bu çıktının üstüne oturacak.

## Kapsam

1. **Paket:** `packages/ingest` (`hukuk_ingest`), uv workspace üyesi, `py.typed`. `services/app`'e bağımlılık yok; `app`/`worker` ileride bunu import eder.
2. **Tip tespiti** (`detect.py`): uzantıya değil magic byte'a ve yapıya bakar. Döner: `DetectedType` enum (ASCII, `snake_case`):
   - `pdf`, `doc` (OLE2), `docx` (zip + `word/document.xml`), `udf` (zip + UYAP `content.xml`), `xlsx_xlsm` (zip + `xl/`), `html`, `image` (jpg/png), `text`, `unknown`.
   - Uzantı ile içerik çelişirse `extension_mismatch=True` (bilinen vakalar: `.pdf` uzantılı 2 `.doc`, `.pdf` uzantılı 6 HTML index sayfası).
3. **Metin çıkarma** (`extract.py`), tipe göre:
   - `pdf`: `pypdfium2` (pip wheel, sistem paketi gerektirmez). Sayfa sınırları korunur (`\f`), sayfa sayısı rapora.
   - `docx`: `python-docx` (paragraflar + tablolar).
   - `udf`: zip içindeki `content.xml`'in CDATA metni; `sign.sgn` varsa `signed=true` rapora.
   - `doc` (OLE2): saf Python yolu yoksa çıkarma yapılmaz, `status=unsupported`, `reason=legacy_doc`. Sistem aracı (antiword/LibreOffice) **eklenmez**; sayı az (≈11), ayrı karar.
   - `html`: metin çıkarılmaz, `status=rejected`, `reason=html_stub` (arşivdeki başarısız indirmeler).
   - `image`: `status=needs_ocr`. OCR bu görevde yok.
   - `xlsx_xlsm`, `unknown`, `Thumbs.db` vb.: `status=skipped`.
4. **Metin kalite sinyali** (`quality.py`), deterministik:
   - `chars_per_page < 50` → `status=needs_ocr`, `reason=no_text_layer`.
   - **Sık kelime oranı** (≈30 Türkçe stopword: ve, bir, bu, ile, için, olarak, sayılı, madde...; token'ların içindeki pay) `< 0.06` ya da CJK/Türkçe dışı alfabe karakteri varsa → `needs_ocr`, `reason=bad_ocr_layer`. Spike'ta bozuklar 0.000-0.056, sağlamlar ≥ 0.069 çıktı; marj dar, bu yüzden `0.06-0.09` arası `ok` + `warnings: [borderline_quality]`.
   - **Korpus kalibrasyonu (uygulanan değerler):** tam korpusta bozuk OCR katmanları 0.000-0.021, sağlam kısa kararlar 0.036-0.059 çıktı; bu yüzden `bad_ocr_layer` eşiği 0.03, `borderline_quality` bandı 0.03-0.06 (0.03-0.09 bandı 308 dosyayı işaretliyordu). Boşluk dar (~0.016) ve 4 bozuk örneğe dayanıyor. **Bilinen kaçak:** kısmen bozuk OCR (ör. 0.094) `ok` geçer; sayfa bazlı `weak_page_text` uyarısı bunu işaretler ama yönlendirmez. Sayfa başına kontrol: sayfaların ≥ %30'u (son boş sayfalar hariç) metinsizse `needs_ocr/partial_text_layer`; Kiril/Arapça/CJK oranı ≥ %1 ise `bad_ocr_layer`; 50'den az token'da oran güvenilmez (`too_little_text` uyarısı). Önbellek anahtarı `PIPELINE_VERSION` + kod/eşik/stopword parmak izidir.
   - Ayrıca rapora: chars, pages, Türkçe harf oranı, `?`/U+FFFD oranı. Eşikler sabit + gerekçe yorumu.
5. **Temel normalizasyon** (`clean.py`), yalnızca kaynaktan bağımsız olanlar: Unicode NFC, `\r\n` → `\n` (pdfium çıktısı CRLF), NBSP/soft hyphen temizliği, satır sonu tirelemesi birleştirme, madde işaretleri (⚫ • ▪) tek biçime. **Dergiye özgü** temizlik (sayfa başlığı, dergi sayfa numarası) bu görevde **yok**, parser görevine kalır. Ham metin de saklanır; temizlenmiş metin ayrı dosya.
6. **Önbellek düzeni:** `data/extracted/<sha256[:2]>/<sha256>.raw.txt` (`data/text/` Mac'teki eski `pdftotext` önbelleği, karışmasın) ve `.clean.txt` (gitignored). Aynı sha256 tekrar işlenmez (`--force` hariç). Bu yol ileride `extraction.raw_text_ref` olur.
7. **CLI:** `uv run hukuk-ingest scan <dir> --out <report_dir> [--text-cache data/text] [--workers N] [--force]`.
   - Her dosya için bir JSONL satırı (`files.jsonl`): `path, sha256, size, ext, detected_type, extension_mismatch, status (ok|needs_ocr|unsupported|rejected|skipped|error), reason, pages, chars, quality{...}, text_ref, extractor, extractor_version, duration_ms`.
   - Özet (`summary.json` + insan okunur `summary.md`): tip × durum sayıları, uyuşmazlık listesi, `needs_ocr` listesi klasöre göre, en yavaş 10 dosya, hata listesi.
   - `--workers N` (varsayılan CPU sayısı, process pool). Bir dosyadaki hata koşuyu durdurmaz, `status=error` + istisna metni.
8. **Testler** (`packages/ingest/tests/`, telifli veri repoya girmez):
   - Sentetik fixture'lar test içinde üretilir ya da küçük elle yazılmış dosyalar commit edilir: metinli PDF, boş/taranmış benzeri PDF, docx, udf (zip + content.xml), `.pdf` uzantılı OLE2 başlıklı dosya, `.pdf` uzantılı HTML, jpg.
   - Her tip için tespit + durum doğru; uzantı uyuşmazlığı işaretleniyor; Türkçe karakterler (ğ, ı, İ, ş) bozulmadan çıkıyor; normalizasyon idempotent.
   - Korpus testi: `data/drive` yoksa **skip**; varsa küçük bir örneklem üzerinde CLI uçtan uca.
   - `testpaths`'e `packages/ingest/tests` eklenir.
9. **Dockerfile:** `services/app` imajı `hukuk-ingest`'i içerir (ileride worker kullanacak); yeni sistem paketi eklenmez.

## Kapsam dışı

- Karar alanlarını ayrıştırma (daire, E/K, tarih, ÖZETİ), dergi başlık/sayfa no temizliği: Görev 04 (karar parser'ı).
- DB'ye yazma (`ingest_job`, `ingest_file`, `extraction` satırları), Postgres kuyruğu, worker job'u, API endpoint'i.
- OCR, `.doc` dönüştürme, eksik 6 kararın yeniden indirilmesi (ortak onayı gerekir).
- Mevzuat madde bölme ve sürümleme.
- `docs/` değişikliği (çelişki varsa PR açıklamasına not). `AGENTS.md` e-imza düzeltmesi bu spec PR'ında yapıldı.

## Kabul kriterleri (Themis koşar)

- [ ] `make lint`, `make typecheck`, `make test` temiz; CI yeşil.
- [ ] Tam korpus koşusu sunucuda (`data/drive`, 6.626 dosya) hatasız biter, 5 dakikanın altında; süre ve `summary.md` PR açıklamasında.
- [ ] Karar arşivi: tam olarak 6.334 `pdf/ok`, 2 `doc/unsupported` + `extension_mismatch`, 6 `html/rejected`.
- [ ] Mevzuat: 25 ± 2 `no_text_layer`, 4-7 `bad_ocr_layer`, 16 `image/needs_ocr`; e-imzalı genelgeler `ok`. Listeler `summary.md`'de; Themis 5 `ok` + 5 `needs_ocr` örneği elle kontrol eder.
- [ ] Rastgele 10 karar için `.clean.txt` elle okunur; Türkçe karakter bozulması yok.
- [ ] İkinci koşu önbellekten gelir (yeniden çıkarım yok), süre PR'da.

## Notlar Claude Code için

- Python 3.12, tipli (`mypy --strict` paket için açık), ruff. Bağımlılıklar: `pypdfium2`, `python-docx`; başka bir şey gerekirse gerekçesi PR'da.
- `pypdfium2` belge/sayfa nesnelerini açıkça kapat (bellek); işçi süreç başına dosya.
- Gerçek veri dosyalarını test fixture'ı olarak kopyalama (telif + KVKK).
- İngilizce kod/yorum/commit; mesaj: `feat(ingest): content-based type detection and text extraction`.
