# Görev 12: dosyalar app'te yönetilir (yükleme, saklama, tarama)

Durum: 12a, 12b ve 12c uygulandı, PR'lar Orhan'ın onayında (2026-10-11); 12d (belge türü düzeltmesi, Orhan 2026-10-12) uygulandı, PR onayda; 12e (zamanlanmış yedek) önerildi, onay bekliyor. Taslak (Orhan, 2026-10-11: "bütün dosyalar da app üzerinden yönetilsin. Yeni dosyalar da oraya eklensin ve app ten taransın"; saklama: "şimdilik sunucu sonra ayrı bucket alacaz"). Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/data-model.md` §3 (`ingest_job`, `ingest_file`, `extraction`), `services/app/app/models/common.py` (`IngestJob`, `IngestFile`, `IngestKind.upload`), `services/app/app/worker.py` (şimdilik yalnız heartbeat), `services/app/app/review.py` (PDF uç noktası, `ARCHIVE_ROOT`), `packages/ingest` (`detect`, `extract`, `ocr`, `legacy_doc`; Görev 03 ve 07), `infra/compose/docker-compose.yml`, `docs/deploy.md`, `docs/tasks/08-auth.md` (roller).
Skill'ler: `db-migration`, `frontend-ui` (bağlayıcı), `task-pr-hygiene`.

## Sorun

Kaynak dosyalar üç yerde duruyor: İbrahim'in Google Drive klasörü ("Projem"), Orhan'ın Mac'i ve sunucudaki salt okunur kopya (`ARCHIVE_HOST_DIR`). Drive'a eklenen yeni belge sisteme hiç gelmiyor (2026-10-10'da yaşandı); gelmesi için Mac'te `rclone`, elle `hukuk-ingest scan`, elle yükleme gerekiyor. Dosyanın kimin tarafından, ne zaman, hangi sürüm olarak eklendiği hiçbir yerde tutulmuyor; md. 25 (doğrulanamayan kaynak kritik hata) için bu iz şart.

## Hedef

Dosyaların tek doğru yeri app olur. Yetkili kullanıcı dashboard'dan dosya yükler, belge türünü ve tarihini girer; app dosyayı içerik adresli olarak saklar, aynı dosyanın ikinci kez yüklenmesini yakalar, eski sürümü silmeden yenisini bağlar. `worker` her yeni dosyayı tarar (tür tespiti, metin çıkarma, gerekirse OCR) ve sonucu dosya kaydına yazar. Mevcut Drive arşivi bir kez içeri alınır; sonra Drive yalnız arşiv olarak kalır, iki yönlü senkron yok.

Saklama şimdilik sunucu diski (Docker volume). Kod bir `FileStore` arayüzünün arkasında yazılır; ileride S3 uyumlu bucket'a geçiş yalnız yeni bir uygulama + ayar değişikliği olur.

Görev üç PR'a bölünür: **12a** saklama + API + worker taraması, **12b** dashboard "Dosyalar" ekranı, **12c** mevcut arşivin içeri alınması ve PDF sunumunun saklama katmanına taşınması.

## Kapsam

### 12a: saklama, şema, API, tarama

1. **`FileStore` arayüzü** (`services/app/app/files/store.py`): `put(stream) -> (key, sha256, size)`, `open(key)`, `exists(key)`. Anahtar içerikten türetilir: `sha256/ab/cd/<sha256>` (aynı içerik bir kez saklanır). Tek uygulama `LocalFileStore(root)`; yazma önce geçici dosyaya, sonra atomik `rename`. Ayar: `FILE_STORE_ROOT` (mutlak yol, zorunlu değil; boşsa yükleme uç noktaları 503 `file_store_unavailable`). Compose'da `filestore` adlı volume, `app` ve `worker`'a okuma-yazma bağlanır.
2. **Şema** (Alembic, yeni sürüm; ORM tutarlılık testi `db-migration` skill'indeki gibi). `ingest_file`'a:
    - `storage_key` (null olabilir: eski, arşivden yüklenmiş kayıtlar 12c'ye kadar boş kalır),
    - `original_name` (kullanıcının yüklediği ad),
    - `doc_type` (yeni enum `document_type`: `kanun`, `cbk`, `yonetmelik`, `teblig`, `genelge`, `genel_yazi`, `ic_emri`, `karar`, `kitap`, `hesap_tablosu`, `diger`),
    - `doc_date` (belgenin yayım/imza tarihi, null olabilir), `official_ref` (resmî sayı, örn. "2020/39"), `origin_url`, `note`,
    - `uploaded_by` (kullanıcı FK, null: sistem/toplu aktarım), `uploaded_at`,
    - `supersedes_id` (aynı belgenin önceki sürümü, `ingest_file` FK, null olabilir),
    - `scan_status` (yeni enum `scan_status`: `queued`, `running`, `done`, `needs_ocr`, `unsupported`, `failed`) ve `scan_result` jsonb (tespit edilen tür, sayfa sayısı, metin uzunluğu, OCR kullanıldı mı, uyarılar),
    - `archived_at` (yumuşak silme; dosya ve kayıt kalır).
    Çıkarılan metin dosyanın yanında saklanır (`FileStore`, anahtar `text/<sha256>.txt`), `extraction.raw_text_ref` deseniyle `ingest_file.scan_result.text_key`'e yazılır. Yeni tablo yok.
3. **API** (`/files`, OpenAPI tipleri yeniden üretilir; `packages/models`):
    - `POST /files` (multipart: dosya + alanlar). Yetki `reviewer` ve `admin`. Sınırlar: en fazla 50 MB (`FILE_MAX_BYTES`), izinli uzantı/içerik: pdf, doc, docx, udf, png, jpg/jpeg, xlsx, xlsm, txt. İçerik türü uzantıya değil içeriğe göre de kontrol edilir (Görev 03 `detect`). Aynı sha256 canlı bir kayıtta varsa 409 `duplicate_file` + mevcut kaydın kimliği. Aynı sha256 **arşivlenmiş** bir kayıtta varsa da 409 `duplicate_file` döner: mevcut kimlik + `archived: true`; UI "Bu dosya arşivde" der ve (admin için) "Arşivden çıkar" sunar. Başarıda bir `ingest_job` (`kind=upload`, `created_by`) + `ingest_file` (`scan_status=queued`) yazılır, 201.
    - `POST /files/{id}/versions`: aynı belgenin yeni sürümü; yeni kayıt `supersedes_id` ile eskiye bağlanır, eski kayıt değişmez. Alanlar boş gelirse öncekinden kopyalanır.
    - `GET /files`: sayfalı liste (`cursor`), filtre `doc_type`, `scan_status`, `q` (ad / resmî sayı), `archived` (varsayılan hariç). Liste her belgenin yalnız en yeni sürümünü gösterir, `version_count` taşır.
    - `GET /files/{id}`: alanlar, tarama sonucu, sürüm zinciri (eskiden yeniye), yükleyen ve tarih.
    - `GET /files/{id}/content`: dosyanın kendisi (`Content-Disposition` ile orijinal ad); `GET /files/{id}/text`: çıkarılan metin. Her ikisinde sunmadan önce sha256 kontrolü (mevcut PDF uç noktasındaki kural).
    - `POST /files/{id}/archive` ve `/unarchive`: yalnız `admin`.
    - `POST /files/{id}/rescan`: `admin`; durumu `queued`'a çeker.
    - Hata kodları mevcut sözleşmede (`errors.py`): 400 `invalid_file`, 403, 404, 409 `duplicate_file`, 413 `file_too_large`, 415 `unsupported_file_type`, 503 `file_store_unavailable`.
4. **Worker taraması** (`worker.py`'deki heartbeat döngüsü yerine): `scan_status=queued` kaydı `SELECT ... FOR UPDATE SKIP LOCKED` ile alır, `running` yapar, `packages/ingest` ile tür tespiti + metin çıkarma (+ OCR, Tesseract varsa) çalıştırır, sonucu ve metni yazar, `done` / `needs_ocr` / `unsupported` / `failed` yapar; `ingest_job.status` ve `stats` güncellenir. Tek dosyanın hatası döngüyü durdurmaz (hata `scan_result.error`'a). Bir kayıt `running`'de 15 dakikadan uzun kalırsa (çökme) yeniden `queued` olur. Eşzamanlılık 1 (sunucu paylaşımlı). Sinyalle düzgün durma korunur.
5. **Tesseract worker imajına girer**: `services/app/Dockerfile`'a `tesseract-ocr` + `tesseract-ocr-tur` (+ `osd`); `HUKUK_TESSERACT` / `TESSDATA_PREFIX` imajda ayarlı. İmaj boyutu artışı PR'da yazılır.

### 12b: dashboard "Dosyalar" ekranı

6. Yan menüde **Dosyalar**. Liste: ad, belge türü, belge tarihi, resmî sayı, yükleyen, yükleme tarihi, tarama durumu rozeti, sürüm sayısı. Filtreler: tür, tarama durumu, arama. Mobilde kart (kuyruk ekranındaki kurallar).
7. **Yükleme**: sürükle-bırak alanı + "Dosya seç" düğmesi (telefonda dosya/kamera seçicisi açılır). Seçilen her dosya için kısa form: belge türü (zorunlu), belge tarihi, resmî sayı, kaynak adresi, not. Birden fazla dosya aynı anda; her biri için ilerleme ve sonuç. 409'da "Bu dosya zaten yüklü" + mevcut kayda bağlantı. 413 / 415 için Türkçe açıklama.
8. **Detay**: alanlar, tarama sonucu (tür, sayfa, OCR kullanıldı mı, uyarılar), "Dosyayı aç" (PDF masaüstünde gömülü, mobilde bağlantı), "Metni gör", sürüm geçmişi, **"Yeni sürüm yükle"**. Admin için "Arşivle" ve "Yeniden tara". Tarama sürerken durum kendiliğinden yenilenir (ör. 5 sn aralıkla, en fazla 2 dk).
9. Metinler `messages/tr.json`'da; 360 / 768 / 1440 ekran görüntüleri PR'da.

### 12c: mevcut arşivin içeri alınması

10. **Toplu aktarım CLI'si**: `python -m app.files.import_dir <klasör> --uploaded-by-system` klasör ağacını dolaşır; her dosya `FileStore`'a konur, `ingest_file` kaydı açılır ya da **aynı sha256'lı mevcut kayıt varsa (karar arşivi, Görev 05 yüklemesi) yalnız `storage_key` ve `original_name` doldurulur**, yeni kayıt açılmaz. `doc_type` Drive klasör adından eşlenir (Kanunlar → `kanun`, Genelge → `genelge`, Genel Yazı → `genel_yazi`, Yönetmelik → `yonetmelik`, Tebliğ → `teblig`, Yargi_Kararlari_Arsivi → `karar`, kökteki Excel'ler → `hesap_tablosu`, gerisi `diger`); `Eskiler/` altındaki dosya aynı adlı güncel dosyanın önceki sürümü olarak `supersedes_id` ile bağlanır, eşleşmezse tek başına kalır ve raporda listelenir. Orijinal göreli yol `scan_result.import_path`'e yazılır. Tekrar çalıştırılabilir (olanı atlar). Sonunda özet: eklenen, eşleşen, atlanan, hatalı. Tarama kuyruğuna yalnız daha önce taranmamış dosyalar girer.
11. **PDF sunumu saklama katmanına geçer**: karar detayındaki PDF uç noktası önce `storage_key`'den sunar; `storage_key` boşsa eski `ARCHIVE_ROOT` yolu çalışmaya devam eder (geçiş süresince). Aktarım tamamlanınca `ARCHIVE_ROOT` deploy.md'de "isteğe bağlı, eski" olarak işaretlenir; kaldırılması ayrı küçük iş.
12. **deploy.md**: `FILE_STORE_ROOT`, `filestore` volume, yedek notu (aşağıda), aktarım adımları (arşivin sunucuya kopyalanması, CLI'nin `app` konteynerinde çalıştırılması), Drive'ın aktarım sonrası "salt arşiv" olduğu.

### 12d: belge türü düzeltmesi

Sorun (2026-10-11, 12c sonrası canlıda görüldü): Görev 05 yüklemesinden gelen ~6.320 karar satırı 12c'de yalnız `storage_key` ve `original_name` aldı; `doc_type` NULL kaldı, Dosyalar ekranı "-" gösteriyor. Orhan (2026-10-12): her arşiv satırı Drive klasörüne göre türlensin. Drive kopyası yakında yeni klasörler de getirecek.

Hedef: arşiv satırlarının hepsinin `doc_type`'ı klasöründen dolu; yeni içe aktarımlar da aynısını yapar.

Kapsam:

1. **İçe aktarma:** sha256 ile eşleşen mevcut satırın `doc_type`'ı NULL ise yoldan (`doc_type_of`) doldurulur; dolu bir tür (kullanıcı yüklemede seçmiş olabilir) asla ezilmez.
2. **Yeni tür `gorus`** (SGK / bakanlık görüşleri ayrı bir kaynak türüdür, md. 28): Alembic 0011 (`ALTER TYPE document_type ADD VALUE`; downgrade `gorus` satırlarını `diger` yapıp tipi eskisiyle değiştirir), `DocumentType`, `DocType`, OpenAPI tipleri, web etiketi "Görüş".
3. **Klasör eşlemesi** (aksan / büyük-küçük harf / NFC-NFD fark etmez; yolda eşleşen ilk klasör belirler, alt klasörler üstünü izler): Kanunlar → `kanun`; Genelge (+ `... ekleri`, `Eskiler`) → `genelge`; Genel Yazı → `genel_yazi`; Yönetmelik (+ `İSG`) → `yonetmelik`; Tebliğ → `teblig`; Yargı Kararları ve `Yargi_Kararlari_Arsivi` → `karar`; **Görüş (+ `Trafik cezaları itiraz`, `Eskiler`) → `gorus`**; Diğer mevzuat ve Diğer → `diger`; kökteki Excel → `hesap_tablosu`; eşleşmeyen her şey → `diger`. `data/drive/Mevzuat` altındaki sekiz klasörün hepsi karşılanır.
4. **Tek seferlik düzeltme:** `python -m app.files.backfill_doc_type [--dry-run]` (ayrı modül; içe aktarma CLI'sinin `--uploaded-by-system` ve dosya deposu gereksinimi bunda yok). `doc_type` NULL her satırı `scan_result.import_path`, yoksa `path` üzerinden türler; yolu boş olmayıp klasör eşleşmeyen satır `diger` olur, yolu boş olan NULL kalır ve sayılır. Tekrar çalıştırılabilir (ikincide 0 günceller), toplu güncellenir, JSON özet basar (tür başına güncellenen, NULL kalan). **İkinci geçiş (düzeltme turu):** canlıda 0011 öncesi kodla içe aktarılan Görüş dosyaları `diger` aldı; bu yüzden sistem içe aktarmasından gelen satırlarda (`uploaded_by` NULL ve `scan_result.import_path` dolu) `doc_type = diger` iken `doc_type_of` `gorus` diyorsa `gorus` yapılır. Kullanıcının yüklemede seçtiği tür (`uploaded_by` dolu) ve diğer türler asla değişmez; ikinci koşu 0 günceller. `--dry-run` ve JSON özetinde ayrı sayaç: `retyped`. Alembic'te veri adımı yoktur: migration'lar yalnız şemadır.
5. **deploy.md:** düzeltmenin dağıtımdan sonra `app` konteynerinde çalıştırılması.

Kabul: eşleşen NULL satır türünü alır, dolu tür korunur; Görüş klasörü (NFC ve NFD) → `gorus`; demo karar satırlarında düzeltme hepsini `karar` yapar, ikinci koşu 0 günceller, sistem içe aktarmasından `diger` olan Görüş satırı `gorus` olur ve kullanıcı yüklemesindeki `diger` kalır (ikinci koşu 0 retype), `--dry-run` hiçbir şey yazmaz, yolu boş satır NULL kalır; migration 0011 ileri / geri test edilir. Kapsam dışı: arayüz yeniden tasarımı, desteklenmeyen dosyaların `scan_status`'ü, yeni türlerin KB'ye ayrıştırılması, zamanlanmış yedek (12e).

## Kapsam dışı

- **Yeni belge türlerini KB'ye ayrıştırmak** (genelge, genel yazı, yönetmelik → `admin_act`; Çalışma ve Toplum dışı karar biçimleri). 12 dosyayı saklar ve metnini çıkarır; türe özel ayrıştırma ve inceleme kuyruğuna düşürme her tür için ayrı görev. Yeni kanun snapshot'ının Görev 11 zincirine bağlanması da ayrı.
- S3 / bucket uygulaması (arayüz hazır, uygulama sonra).
- Otomatik yedekleme işi. Volume'ün düzenli yedeği gerekli; deploy.md'ye elle yedek komutu ve risk notu yazılır, zamanlanmış yedek ayrı görev: **12e olarak önerilir ve 12c'nin hemen ardından yapılmalıdır** (volume tek kopya olarak sunucu diskinde durur).
- mevzuat.gov.tr / Resmî Gazete'den otomatik çekme (ayrı görev; çekilen dosyalar aynı `POST /files` yolunu ya da `FileStore`'u kullanacak).
- Drive ile senkron ya da Drive'a geri yazma.
- Kalıcı silme (yalnız arşivleme), toplu arşivleme, klasör hiyerarşisi (tür + filtre yeterli).
- Virüs taraması (yalnız bilinen kullanıcılar yükler; dosya çalıştırılmaz, yalnız ayrıştırılır).

## Kabul kriterleri

- Her PR'da backend `ruff`, `mypy`, `pytest` ve frontend `pnpm lint typecheck test build format:check` yeşil; OpenAPI tipleri güncel; migration ileri / geri test edilir.
- Testler modüle göre (`test_files.py`, `test_store.py`, `test_worker.py`, ilgili `*.test.tsx`); mevcut testler gevşetilmez.
- 12a en az şunları test eder: yükle → 201, kayıt `queued`, dosya `FileStore`'da sha256 anahtarıyla; aynı dosyayı tekrar yükle → 409 ve mevcut kimlik; 50 MB üstü → 413; uzantısı `.pdf` içeriği başka → 415; yeni sürüm → `supersedes_id` dolu, liste tek satır ve `version_count=2`; worker metinli PDF'i `done`, görseli (Tesseract varsa) OCR ile `done`, bozuk dosyayı `failed` yapar ve döngü durmaz; `running`'de kalmış kayıt geri alınır; iki worker aynı kaydı almaz; rolsüz 401/403, reviewer arşivleyemez (403); `FILE_STORE_ROOT` yokken 503; içerik uç noktası sha256 tutmazsa dosyayı sunmaz.
- 12b: e2e (Playwright) PDF yükle → listede görünür → tarama "tamamlandı" olur → detayda metin ve sürüm geçmişi; aynı dosya tekrar yüklenince "zaten yüklü" mesajı; yeni sürüm yükleme. Themis 360 / 768 / 1440'ta doğrular (taşma yok, dokunma hedefi 44 px, input 16 px).
- 12c: demo arşivle (`infra/demo/archive`) CLI iki kez çalıştırılır; ikincide eklenen 0. Mevcut karar kayıtları yeni kayıt açılmadan `storage_key` alır; karar detayındaki PDF `ARCHIVE_ROOT` boşken de açılır. Tam Drive kopyasında (6.626 dosya) Themis yerel olarak çalıştırır ve özet sayıları PR'a koyar (eşleşen karar sayısı ≈ 6.334, `Eskiler/` eşleşmeyenlerin listesi).

## Notlar Claude Code için

- Upload'u belleğe tamamen okumadan diske akıt (FastAPI `UploadFile` + parça parça hash).
- `FileStore` çağrıları senkron dosya işlemi; async uç noktada `run_in_threadpool` / `anyio.to_thread`.
- Worker'ın taraması `packages/ingest`'teki mevcut fonksiyonları çağırır; tespit ve çıkarma mantığı kopyalanmaz.
- Commit et, push'u Themis yapar.
