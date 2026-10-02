# Görev 03: Ingest çekirdeği (tip tespiti + metin çıkarma)

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `AGENTS.md` (Data, Decision archive findings), `docs/architecture.md` §3-4 (`packages/ingest`, ingest akışı), `docs/roadmap.md` Faz 1 hafta 1-2, `docs/data-model.md` §3 (`ingest_file`, `extraction.raw_text_ref`).
Üstüne oturduğu iş: Görev 01 (iskelet), Görev 02 (şema).

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
   - `udf`: zip içindeki `content.xml`'in metin içeriği (CDATA dahil); stil bilgisi atılır.
   - `doc` (OLE2): saf Python yolu yoksa çıkarma yapılmaz, `status=unsupported`, `reason=legacy_doc`. Sistem aracı (antiword/LibreOffice) **eklenmez**; sayı az (≈11), ayrı karar.
   - `html`: metin çıkarılmaz, `status=rejected`, `reason=html_stub` (arşivdeki başarısız indirmeler).
   - `image`: `status=needs_ocr`. OCR bu görevde yok.
   - `xlsx_xlsm`, `unknown`, `Thumbs.db` vb.: `status=skipped`.
4. **Metin kalite sinyali** (`quality.py`): her çıkarımda basit, deterministik metrikler: karakter sayısı, sayfa başına karakter, Türkçe harf oranı, sözlük dışı "kelime" oranı (küçük bir sık-kelime listesiyle), kontrol/özel karakter oranı. Eşik altında `status=needs_ocr`, `reason=low_text_quality` (hedef: e-imzalı SGK genelgelerinin bozuk çıktısı ve metin katmansız taramalar). Eşikler sabit + gerekçe yorumu; korpus raporuna göre ayarlanır.
5. **Temel normalizasyon** (`clean.py`), yalnızca kaynaktan bağımsız olanlar: Unicode NFC, `\r\n` → `\n`, NBSP/soft hyphen temizliği, satır sonu tirelemesi birleştirme, madde işaretleri (⚫ • ▪) tek biçime. **Dergiye özgü** temizlik (sayfa başlığı, dergi sayfa numarası) bu görevde **yok**, parser görevine kalır. Ham metin de saklanır; temizlenmiş metin ayrı dosya.
6. **Önbellek düzeni:** `data/text/<sha256[:2]>/<sha256>.raw.txt` ve `.clean.txt` (gitignored). Aynı sha256 tekrar işlenmez (`--force` hariç). Bu yol ileride `extraction.raw_text_ref` olur.
7. **CLI:** `uv run hukuk-ingest scan <dir> --out <report_dir> [--text-cache data/text] [--workers N] [--force]`.
   - Her dosya için bir JSONL satırı (`files.jsonl`): `path, sha256, size, ext, detected_type, extension_mismatch, status (ok|needs_ocr|unsupported|rejected|skipped|error), reason, pages, chars, quality{...}, text_ref, extractor, extractor_version, duration_ms`.
   - Özet (`summary.json` + insan okunur `summary.md`): tip × durum sayıları, uyuşmazlık listesi, `needs_ocr` listesi klasöre göre, en yavaş 10 dosya, hata listesi.
   - Paralel çalışır (process pool); bir dosyadaki hata koşuyu durdurmaz, `status=error` + istisna metni.
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
- `docs/` değişikliği (çelişki varsa PR açıklamasına not).

## Kabul kriterleri (Themis koşar)

- [ ] `make lint`, `make typecheck`, `make test` temiz; CI yeşil.
- [ ] Tam korpus koşusu sunucuda (`data/drive`, 6.626 dosya) hatasız biter; süre ve `summary.md` PR açıklamasında.
- [ ] Rapordaki sayılar `AGENTS.md` envanteriyle tutarlı: karar arşivinde ≈6.334 `pdf/ok`, 2 `doc` + `extension_mismatch`, 6 `html/rejected`. Fark varsa PR'da açıklanır.
- [ ] Mevzuat altındaki e-imzalı SGK genelgelerinin çoğu `needs_ocr/low_text_quality` olarak yakalanıyor; elle 10 örnek kontrol (5 `ok`, 5 `needs_ocr`), sonuç PR'da.
- [ ] Rastgele 10 karar için `.clean.txt` elle okunur; Türkçe karakter bozulması yok.
- [ ] İkinci koşu önbellekten gelir (yeniden çıkarım yok), süre PR'da.

## Notlar Claude Code için

- Python 3.12, tipli (`mypy --strict` paket için açık), ruff. Bağımlılıklar: `pypdfium2`, `python-docx`; başka bir şey gerekirse gerekçesi PR'da.
- `pypdfium2` belge/sayfa nesnelerini açıkça kapat (bellek); işçi süreç başına dosya.
- `udf` içinde gömülü PDF olabilir; varsa `reason=udf_embedded_pdf` ile rapora, metin çıkarma yine `content.xml`'den.
- Gerçek veri dosyalarını test fixture'ı olarak kopyalama (telif + KVKK).
- İngilizce kod/yorum/commit; mesaj: `feat(ingest): content-based type detection and text extraction`.
