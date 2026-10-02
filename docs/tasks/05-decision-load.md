# Görev 05: Karar arşivinin KB'ye yüklenmesi (extraction + inceleme kuyruğu)

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/data-model.md` §3 (`source`, `ingest_*`, `extraction`, `review`), §4 (durum makinesi, toplu onay paragrafı), §5.2 (`decision`), `docs/tasks/04-decision-parser.md`, PR #15 açıklaması (QA bulguları).
Üstüne oturduğu iş: Görev 04 (`hukuk-ingest decisions` JSONL çıktısı, PARSER_VERSION 5) ve şema v0.2 PR'ı (#17: `source_chamber`, `bam_region`, bölgeli unique indeks). Şema PR'ı merge edilmeden implementasyon başlamaz.

## Hedef

Görev 04'ün ürettiği 6.334 karar kaydını Postgres'e **inceleme bekleyen** halde yüklemek: her karar için `source` (status `analyzed`) + `ingest_file` + `extraction` satırı, tek bir `ingest_job` (kind `bulk`) altında. Her extraction'a deterministik bir **güven skoru** ve sebep listesi yazılır; inceleme ekranı (sonraki görev) bu skora göre sıralayıp toplu onay verecek.

Bu görevde `decision` satırı **oluşmaz**. Durum makinesine göre tipli tabloya yazma onaydan sonra olur (§3: "onaydan sonra tipli tabloya kopyalanır"); hiçbir karar insan onayı olmadan aramaya ve atıfa açılmaz (md. 25). Onay tek başına da yetmez: dergi arşivi atıf kaynağı değil (aşağıda "Kaynak politikası"), onaylı ama resmî kaynakta teyit edilmemiş karar kullanıcıya atıf olarak gösterilmez. Onaylı extraction'ı `decision`'a kopyalayan fonksiyon bu görevde yazılır ve test edilir, ama yalnızca testten ve bir CLI bayrağıyla çağrılır (aşağıda madde 6).

## Kaynak politikası (WP grubu, 2026-10-02, İbrahim)

- Çalışma ve Toplum arşivi **arama ve keşif** içindir. Kullanıcıya gösterilen atıf resmî kaynaktan gelir: Yargıtay için karararama, BAM için UYAP Emsal, AYM için kararlar bilgi bankası, Danıştay için kendi sitesi.
- Resmî kaynakta bulunamayan karar kaynak olarak gösterilmez. Bu kayıtlar (yaklaşık 1.500, çoğu 2009 öncesi) için ürün kararı açık, aşağıda "Açık sorular".
- Bu görev için sonucu: yükleme ve onay aynı kalır, ama **atıfa açılma koşulu = insan onayı + `decision.verification` ∈ {`verified_official`, `verified_uyap`}**. `source_rank` `editorial` başlar, teyitte `official_primary`'ye güncellenir (teyit görevinin işi).
- Kitaplar sisteme yüklenmez; `academic` rank şimdilik kullanılmaz.

## Neden bu sırayla

- Resmî kaynak teyidi ayrı bir görev olur (Görev 06), DB'deki kayıtlar üzerinde çalışır ve `decision.verification` + `source_rank` alanlarını doldurur. Kaynak politikası nedeniyle teyit opsiyonel değil: teyit olmadan hiçbir karar atıf olarak gösterilemez, bu yüzden Görev 06 bu görevin hemen arkasından gelir. Karararama toplu sorgu izni sorusu açık (`data-model.md` §11); kapsam Yargıtay + BAM + AYM + Danıştay.
- İnceleme ekranı ve dashboard için DB'de veri olması gerekiyor; yol haritası Faz 1 hafta 3-4 "toplu işleme + QA raporu".

## Kapsam

1. **Yer:** `services/app` içinde `app.loaders.decisions` (DB'ye yazan kod `app`'te; `packages/ingest` DB bilmez, değişmez). Giriş noktası: `python -m app.loaders.decisions <decisions.jsonl> [--files files.jsonl] [--dry-run]`. Worker job'u bu görevde yok; CLI yeterli.
2. **Eşleme (JSONL → satırlar):**
   - `ingest_job`: kind `bulk`, `stats` = yükleme özeti (aşağıdaki rapor ile aynı sayılar).
   - `ingest_file`: path, sha256, detected_type, size (Görev 03 `files.jsonl`'den; yoksa JSONL'deki sha256/path).
   - `source`: category `decision`, title = dergi başlığı (dosya adı), `official_ref` = "Yargıtay 9. HD, E. 2017/16188 K. 2019/1234, 12.03.2019" biçiminde, alan yoksa o parça atlanır (uydurulmaz); `source_rank` `editorial` (kaynak resmî değil, dergi; teyit sonrası değişebilir), `license` `unknown` (telif sorusu açık, md. 32), status `analyzed`.
   - `extraction`: parser_name `decisions`, parser_version (JSONL'den), `fields` = parser alanları (normalize edilmiş, bkz. 3), `warnings` = parser uyarıları + yükleyicinin eklediği uyarılar, `confidence` = madde 4, `raw_text_ref` = önbellek yolu (`data/extracted/...`, mutlak yol değil). `full_text` ve `editorial_summary` `fields` içinde tutulur.
3. **Normalizasyon** (yükleyicide, parser'da değil; her kural test edilir):
   - `outcome`: "düzelterek onama" → `duzelterek_onama` ve şema v0.2'deki ASCII etiketler. Bilinmeyen değer → boş + uyarı `outcome_unmapped`.
   - `court` / `court_level`: parser etiketleri enum ile birebir; boş (`''`, 10 kayıt "Belirsiz") → enum'a zorlanmaz, alan boş kalır, uyarı `court_missing`, skor en düşük banda düşer.
   - `chamber`, `source_chamber`, `bam_region`: olduğu gibi; NOT NULL alanlar için `''`.
   - `decision_date`: ISO tarih; geçersizse boş + mevcut uyarı korunur.
4. **Güven skoru** (`extraction.confidence`): `{"score": 0..100, "band": "high"|"medium"|"low", "reasons": [...]}`. Deterministik, kurallar tek bir tabloda (kod içinde sabit + docstring'de gerekçe). Başlangıç kuralları:
   - `low`: kritik alanlardan biri eksik (court, esas_no, karar_no, decision_date; dairesi olan mahkemede chamber), `layout=unknown`, `body_not_found`, `text_completeness=summary_only`, veya mükerrer grubunda `different_text` / `date_mismatch`.
   - `medium`: `header_closing_date_mismatch`, `karar_year_ne_date_year`, `date_is_lower_court`, `date_from_closing`, `body_start_approximate`, `statute_inferred_from_date`, `statute_unmapped`, `date_outside_issue_year`, `multiple_esas_candidates`, mükerrer grubunda `excerpt`.
   - `high`: geri kalan.
   - Bant eşikleri ve kural listesi PR'da tam koşunun dağılımıyla birlikte raporlanır; Orhan onaylamadan toplu onay için kullanılmaz.
5. **Mükerrer kayıtlar** (PR #15: 94 aynı-anahtar grubu; 49 `same_text`, 27 `different_text`, 9 `excerpt`, 9 `date_mismatch`):
   - Aynı sha256 iki kez gelirse (aynı PDF iki sayıda) tek `ingest_file` / `source`; ikinci geliş `stats`'ta sayılır.
   - Farklı dosya, aynı (court, bam_region, chamber, esas_no, karar_no): her biri ayrı `source` + `extraction` olarak yüklenir (hangisinin doğru olduğuna yükleyici karar vermez); her birine `fields.duplicate_group` (grup anahtarı + `dup_kind`) yazılır. `same_text` grubunda en uzun metinli olan `medium`, diğerleri `low` + uyarı `duplicate_of`. Unique indeks `decision` tablosunda olduğu için çakışma onay anında yakalanır (madde 6).
6. **Onay → `decision` kopyalama** (`app.kb.publish_decision(extraction_id, review_id)` gibi tek fonksiyon): onaylı extraction'ın `fields` + `review.edits` birleşimini `decision`'a yazar, `verification` = `unverified`, `source.status` `approved`'a geçer. `approved` atıfa açık demek değil (kaynak politikası); atıf sorgusu teyit filtresini Görev 06 ve arama görevinde uygular. Bu görevde UI yok; fonksiyon testlerle ve `--approve-band high --reviewer <user_id>` CLI bayrağıyla çağrılabilir. Bayrak varsayılan kapalı; tam koşu bu bayrak olmadan yapılır. Embedding / tsvector / `published` bu görevde yok.
7. **Yeniden çalıştırma (idempotent):** aynı JSONL ikinci kez yüklenince yeni satır oluşmaz (anahtar: sha256 + parser_name + parser_version). Yeni parser sürümü gelirse yeni `extraction` eklenir, eski extraction ve varsa onaylı `decision` dokunulmaz (§3).
8. **Rapor:** `--report <dir>` ile `load-summary.md` + `load-summary.json`: toplam / yeni / atlanan / hatalı satır, bant dağılımı (mahkeme ve layout kırılımıyla), en sık 15 sebep, mükerrer grup sayıları, normalizasyon uyarıları. Kişisel veri içermez (karar metni ve taraf adı yazılmaz; ref = sayı + sha kısaltması, Görev 04 raporundaki gibi).
9. **Testler:** DB gerektirenler `DATABASE_URL` yoksa skip (mevcut `test_schema.py` kalıbı); eşleme, normalizasyon ve skor kuralları DB'siz birim testleriyle. Fixture: Görev 04 altın setinden 20-30 kayıt (metinler kısaltılmış, kişisel veri yok) + her mükerrer türünden en az bir grup.

## Kapsam dışı

- karararama / UYAP Emsal / AYM / Danıştay teyidi, ağ isteği (Görev 06; toplu sorgu izni bekleniyor).
- İnceleme ekranı, admin API, `dashboard-web` (sonraki görev).
- Embedding, `chunk`, tsvector üretimi, `published` durumu.
- Parser değişikliği. Yükleme sırasında parser hatası bulunursa PR açıklamasında listelenir, ayrı PR.
- Mevzuat ve taranmış Mevzuat dosyaları için OCR (ayrı görev).
- Görev 03'te `unsupported` / `rejected` kalan dosyalar.

## Kabul kriterleri (Themis koşar)

- [ ] `make lint`, `make typecheck`, `make test` temiz; CI yeşil (DB testleri CI'da Postgres ile koşar).
- [ ] Tam yükleme, tek komutla, boş bir veritabanına: 6.334 kayıt, `hata = 0`; süre PR'da. Hedef < 5 dk.
- [ ] İkinci koşu 0 yeni satır üretir (idempotent).
- [ ] `source` / `ingest_file` / `extraction` sayıları rapordaki sayılarla birebir; `decision` tablosu boş (bayraksız koşu).
- [ ] Bant dağılımı ve en sık sebepler PR'da; her bantta rastgele 5 kayıt elle bakılır, skorun sebebiyle tutarlı olduğu yazılır.
- [ ] `--approve-band high` bir test veritabanında koşulur: oluşan `decision` satırları unique indekse takılmadan yazılır, hepsi `verification = unverified`; çakışan olursa raporlanır; sonra veritabanı sıfırlanır.
- [ ] `fields` içinde parser alanlarının tamamı var; `outcome`, `court`, `court_level` değerlerinin hepsi şema enum'ları içinde veya boş + uyarılı.

## Açık sorular (Orhan)

- Sunucuda Postgres yok (konteyner içinde Docker da yok). Tam yükleme nerede koşulacak: Mac'teki `make up` ortamı mı, sunucuya ayrı bir Postgres mi? Karar verilene kadar kabul kriterlerindeki tam yükleme Mac'te koşulur, Themis CI + birim testleriyle doğrular.
- ~~`source_rank`~~ Kapandı (kaynak politikası): `editorial` başlar, teyitte `official_primary`.
- Resmî kaynakta bulunamayan ~1.500 karar: hiç gösterilmesin mi, yoksa tam metin + künye + "resmî veritabanında yer almamaktadır" notuyla mı? (İbrahim kaynak belirtmeden kullanmayı önerdi; ortaklarla karar.) Bu görevi etkilemez: hepsi yüklenir, gösterim kararı arama/atıf katmanında.
- Çalışma ve Toplum özeti (`editorial_summary`): arama sinyali olarak kalsın mı, hiç kullanılmasın mı? Kullanılmayacaksa `fields`'ta durur ama chunk'lanmaz.
- Toplu onay yetkisi: `high` bandı kim onaylar? Öneri: Baran veya İbrahim, inceleme ekranından; CLI bayrağı yalnızca test ve geliştirme için.

## Notlar Claude Code için

- Önce `docs/data-model.md` §3-§5.2 ve `services/app/app/models/` oku; tablo ve enum adlarını tahmin etme.
- `packages/ingest`'e dokunma; JSONL sözleşmesini `hukuk_ingest.decisions` içindeki dataclass'tan oku.
- Toplu yazmada satır satır `INSERT` yerine `executemany`/COPY; tek transaction yerine 500'lük partiler, her parti sonrası commit, hata satırı raporda.
- Yeni bağımlılık yok.
