# Görev 13: Yüklemede otomatik tespit, insan onayı, silme

Bağlam: `docs/tasks/12-file-management.md` (dosya deposu, `/files` API, worker taraması, Dosyalar ekranı), `services/app/app/files/` (`api.py`, `upload.py`, `import_dir.py`), `services/app/app/worker.py`, `packages/ingest` (`detect`, `extract`, `decisions/fields.py`, `statutes/split.py`), `docs/architecture.md` (LLM bölgesi, KVKK), `docs/tasks/08-auth.md` (roller).

## Sorun

Yükleme formu dosyanın kendisinden okunabilecek her şeyi kullanıcıdan istiyor: tür zorunlu, tarih, resmî sayı elle. Orhan (2026-10-12) Drive'dan indirdiği bir kararı yükledi, türü ve tarihi rastgele girdi, sistem kabul etti ("kanun", 01.10.2026). Aynı karar arşivde zaten vardı (`90. Sayı` klasörü, aynı ad); içerik birkaç KB farklı olduğu için sha256 kontrolü yakalamadı. Yanlış yüklenen dosyayı geri almanın yolu da yok: yalnız arşivleme var, uydurma alanlar kayıtta kalıyor.

## Hedef (Orhan, 2026-10-12)

Kullanıcı yalnız dosyayı bırakır. Sistem tarar, türü ve künye alanlarını önerir, benzer / önceki sürümü bulur. İnsan önerileri kontrol eder, düzeltir, onaylar. Onaylanmamış dosya hiçbir yerde kaynak olarak kullanılmaz ve silinebilir.

Kararlar:
1. Tespit önce kurallarla (regex); kurallar bir alanı bulamazsa LLM'e sorulur.
2. Onayı yükleyen verebilir (yükleme yetkisi zaten `reviewer` / `admin`'de; onay yetkisi de bu iki rolde).
3. Onaylanmamış dosya silinebilir. Onaylanmış dosya silinecekse önce onayı kaldırılır, sonra silinir.

İki PR: **13a** backend (şema, tespit, eşleşme, onay / silme API'si), **13b** dashboard (yükleme ve onay ekranı).

## Kapsam

### 13a: backend

1. **Şema** (Alembic, 12d'nin `0011`'inden sonra):
   - `ingest_file.review_status` enum `pending | approved`, NOT NULL. Yeni yükleme `pending`. **Mevcut satırlar `approved`** (`approved_by` NULL = sistem içe aktarması; türleri klasörden geldi, 12d).
   - `approved_by` (FK `app_user`, null), `approved_at` (null).
   - `title` (null): belgenin başlığı (kanun adı, genelge konusu, karar için mahkeme + daire + E/K).
   - `suggestions` JSONB (null): alan başına öneri. Biçim: `{"doc_type": {"value": "genelge", "source": "rule" | "llm", "evidence": {"page": 1, "quote": "GENELGE 2024/5"}}, "doc_date": {...}, "official_ref": {...}, "title": {...}, "issuer": {...}}`. Bulunamayan alan yazılmaz.
   - `matches` JSONB (null): `{"previous_version": {"file_id", "reason"} | null, "similar": [{"file_id", "score", "reason"}]}`.
   - `doc_type` yüklemede artık zorunlu değil; **onayda zorunlu** (aşağıda).
   - Silinen dosyalar için iz tablosu `file_deletion` (id, `file_id` FK'sız, `sha256`, `original_name`, `doc_type`, `review_status` silinirken, `deleted_by`, `deleted_at`, `snapshot` JSONB: satırın tamamı). Silmenin kendisi kayıtta kalır (md. 25 izi).

2. **Yükleme** (`POST /files`): yalnız dosya zorunlu. Form alanları isteğe bağlı kalır; kullanıcı bir alanı doldurduysa o değer önerinin önüne geçer ve kaynağı `user` olarak işaretlenir. Yeni sürüm yükleme (`/files/{id}/versions`) aynı kalır; kullanıcının açıkça seçtiği bağ eşleşme önerisinden önce gelir.

3. **Tespit** (worker, metin çıkarıldıktan sonra; yeni modül `packages/ingest/hukuk_ingest/classify/`, tespit mantığı `services/app`'e kopyalanmaz):
   - **Kurallar** önce. En az şunlar:
     - **Kanun:** mevzuat.gov.tr başlığı ("Kanun Numarası", "Kabul Tarihi", "Yayımlandığı Resmî Gazete Tarih / Sayı"); `statutes/split.py`'deki `parse_header` kullanılır.
     - **Yönetmelik / Tebliğ:** başlık satırında "YÖNETMELİK" / "TEBLİĞ", Resmî Gazete tarih ve sayısı.
     - **Genelge:** "GENELGE" + yıl/sayı ("2024/5"), kurum başlığı (SGK, ÇSGB), "Sayı: E-..." ve tarih.
     - **Genel yazı:** "Sayı:" + "Konu:" ve kurum başlığı, ama "GENELGE" yok.
     - **Karar:** `decisions/fields.py` (mahkeme, daire, esas / karar no, tarih). Karar arşivini işleyen ayrıştırıcının aynısı.
     - **Hesap tablosu:** xlsx / xlsm.
   - **LLM**, yalnız kuralların doldurmadığı alanlar için. Şartlar:
     - Sağlayıcı arayüz arkasında (`Detector`), ayarla seçilir (`FILE_DETECT_LLM_PROVIDER`, `..._MODEL`, `..._API_KEY`, bölge). Ayar yoksa LLM adımı atlanır ve alanlar boş kalır (hata değil). Testler sahte detector ile koşar; CI'da ağ çağrısı yok.
     - Gönderilen metin: ilk 2 sayfa ya da ilk 6.000 karakter (hangisi kısaysa), dosya adı. Dosyanın kendisi gönderilmez.
     - Cevap yapılandırılmış (JSON şeması: `doc_type` enum'dan, `doc_date` ISO, `official_ref`, `title`, `issuer`, her alanda `quote`).
     - **Uydurma koruması:** her alanın `quote`'u çıkarılan metinde (boşluk / büyük-küçük harf normalize edilerek) birebir geçmiyorsa öneri atılır. `doc_type` için `quote` zorunlu değil ama `diger` dışı bir tür kanıtsız gelirse öneri `source: llm` ve kanıtsız olarak işaretlenir. Tarih metindeki tarihle tutmuyorsa atılır.
     - Her çağrı loglanır: model, token, süre, sonuç (alan adları). Metin loglanmaz.
     - Çağrı başarısız olursa (zaman aşımı, kota) tarama `done` kalır, öneri eksik kalır, uyarı `scan_result.warnings`'e yazılır. Yeniden tarama tespiti de yeniden koşar.
   - Tarama bitince dosya `review_status = pending` ve `suggestions` dolu olur. **Tespit asıl alanlara (`doc_type`, `doc_date`, ...) yazmaz**, yalnız `suggestions`'a. Asıl alanları onay yazar.

4. **Eşleşme** (tespitten sonra):
   - **Önceki sürüm adayı:** aynı `doc_type` ve aynı `official_ref` (normalize), ya da aynı normalize başlık / dosya adı (aksan, büyük-küçük harf, noktalama fark etmez; 12c'deki `Eskiler/` normalizasyonu yeniden kullanılır). Adayın zaten yeni sürümü varsa zincirin en yenisine bakılır. Arşivlenmişler hariç.
   - **Benzer dosya:** adaylar arasında çıkarılan metnin benzerliği (Python'da, yalnız adaylar üzerinde; yeni PG eklentisi yok). Eşik ve yöntem PR'da gerekçelendirilir. Orhan'ın vakası (aynı karar, farklı PDF) "benzer" çıkmalı.
   - Eşleşme bağ kurmaz, yalnız öneridir.

5. **Onay**: `POST /files/{id}/approve`, gövdede son alanlar (`doc_type` zorunlu, `doc_date`, `official_ref`, `title`, `origin_url`, `note`) ve sürüm kararı (`supersedes_id`: önerilen dosya, başka bir dosya ya da `null` = ayrı belge). Yetki `reviewer` / `admin` (yükleyen dahil). `pending` değilse 409. Sürüm bağının kuralları 12a'daki gibi (zincir dallanmaz, arşivlenmişe bağlanmaz). Onay `approved_by` / `approved_at` yazar.
   - `POST /files/{id}/unapprove`: yalnız `admin`. Dosyanın yeni sürümü varsa 409 (önce yeni sürüm ele alınır).

6. **Silme**: `DELETE /files/{id}`.
   - Yalnız `pending` dosya. `approved` ise 409 `file_approved` (önce onay kaldırılır).
   - Yetki: yükleyen kendi dosyasını, `admin` her dosyayı.
   - Dosyanın yeni sürümü varsa 409. `extraction` satırı varsa 409 (dosya KB'ye işlenmiş demektir).
   - Silme: satır `file_deletion`'a yazılır, `ingest_file` satırı silinir, iş (`ingest_job`) başka dosyası yoksa silinir, blob ve metin (`text/<sha256>.txt`) aynı sha256'yı kullanan başka satır yoksa depodan silinir. Hepsi tek transaction; depo silme commit'ten sonra, başarısızsa log + yetim blob olarak kalır (sonraki temizlikte gider).
   - Silinen dosya önceki bir sürüme bağlıysa o sürüm yeniden zincirin başı olur.

7. **Liste / detay**: `GET /files` `review_status` filtresi (varsayılan hepsi), yanıtta `review_status`, `suggestions`, `matches`, `approved_by`. **Onaylanmamış dosya hiçbir KB / ajan akışında kaynak olarak kullanılmaz**; bugün böyle bir tüketici yok, ama `ingest_file`'ı okuyacak gelecek kod için bu kural `docs/data-model.md`'ye yazılır.

8. **Ölçüm (kabulün parçası):** tespit, Drive'daki Mevzuat klasörü (281 dosya, klasör türü bilinen) ve karar arşivinden rastgele 200 karar üzerinde koşturulur. PR'a tür başına tablo: kural doğru / yanlış / boş, LLM ile doğru / yanlış / boş, tarih ve sayı için örnek. Klasör türü "doğru cevap" kabul edilir. LLM anahtarı yoksa yalnız kural sütunu, açıkça yazılır.

### 13b: dashboard

9. **Yükleme**: sürükle-bırak, çoklu dosya, form yok. Her dosya yükleme listesinde "Taranıyor → Onay bekliyor" ilerler. Opsiyonel alanlar "Bilgileri kendim gireceğim" altında kapalı.
10. **Onay ekranı** (dosya detayında, `pending` iken üstte):
    - Her alan önerilen değerle dolu, düzenlenebilir. Yanında kaynak etiketi ("Metinden okundu" / "Yapay zekâ önerisi" / "Siz girdiniz") ve kanıt alıntısı ("1. sayfa: 'Sayı: 2024/5'"). Kanıtsız LLM önerisi uyarıyla gösterilir.
    - Eşleşme kutusu: "Bu, X dosyasının yeni sürümü olabilir" (bağla / ayrı belge), "Şu dosyalara çok benziyor: ..." (bağlantılı, karşılaştırma için yeni sekmede açılır).
    - Butonlar: "Onayla", "Sil". Admin için onaylı dosyada "Onayı kaldır".
    - Tür seçilmeden onay butonu pasif.
11. **Liste**: "Onay bekliyor" sekmesi ve sayısı; satırda durum rozeti. Ana menüde onay bekleyen sayısı.
12. Responsive (360 / 768 / 1440), i18n, token'lı renkler: repo kuralları (`frontend-ui`).

## Kapsam dışı

- Onaylanan dosyanın KB'ye işlenmesi (mevzuatın madde ayrıştırması, kararın inceleme kuyruğuna düşmesi). Ayrı görev; o görev yalnız `approved` dosyaları alır.
- Toplu onay. Önce tek tek akış oturmalı.
- Onaylı dosyanın doğrudan silinmesi (önce onay kaldırma şart).
- Mevcut 6.598 satırın yeniden onaya sokulması.
- Görüntü / OCR kalitesine göre tespit iyileştirmesi.

## Kabul kriterleri

- Her PR'da backend `ruff`, `mypy`, `pytest`, frontend `pnpm lint typecheck test build format:check` yeşil; OpenAPI tipleri güncel; migration ileri / geri test edilir.
- 13a test eder: türsüz yükleme 201 ve `pending`; kurallar her tür için örnek metinden doğru öneri ve kanıt üretir; sahte LLM yalnız boş alanlar için çağrılır, metinde geçmeyen alıntı atılır, LLM ayarı yokken tarama `done` ve alan boş; LLM hata verince tarama düşmez; önceki sürüm adayı aynı sayıdan ve aynı addan bulunur; aynı kararın farklı PDF'i "benzer" çıkar; onay alanları yazar, `pending` olmayanı 409; tür olmadan onay 422; reviewer onaylar, rolsüz 403; onaylı dosyayı silme 409, onayı kaldırıp silme 204; başkasının dosyasını reviewer silemez (403), admin siler; silinen dosyanın blob'u başka satır kullanıyorsa kalır, kullanmıyorsa gider; `file_deletion` satırı yazılır; yeni sürümü olan dosya silinemez.
- 13a ölçüm tablosu PR'da (madde 8).
- 13b: e2e: dosya bırak → onay bekliyor → öneriler ve kanıt görünür → bir alanı düzelt → onayla → listede onaylı. Sil akışı. Themis canlıya çıkışta `hukuk-yz-live-verify` ile video çeker.

## Açık nokta (Orhan)

- **LLM sağlayıcısı ve bölgesi:** `architecture.md`'de "EU bölgesi zorunlu, sağlayıcı eval'e göre" diye açık. Yüklenen belgeler bugün mevzuat ve karar (kamuya açık metin), ama ileride müvekkil belgesi de yüklenebilir. 13a kodu sağlayıcıdan bağımsız; canlıda açmak için sağlayıcı + anahtar kararı gerekir.

## Notlar Claude Code için

- `.claude/skills/` altındaki `task-pr-hygiene`, `db-migration`, `frontend-ui`.
- Tespit kuralları saf fonksiyon, `packages/ingest`'te, kendi testleriyle (`test_classify.py`). Testler modüle göre dosyalanır.
- LLM istemcisi için yeni bağımlılık eklenirse tek ve gerekçeli olsun; HTTP ile doğrudan çağrı da kabul.
- Commit et, push'u Themis yapar.
