# Görev 20: Dergi taraması (Çalışma ve Toplum, haftalık)

Durum: 20a (backend) uygulandı, PR Orhan'ın onayında (2026-11-10); 20b bekliyor. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: issue #84 (bu görev), #83 (91. sayı pilotu, kuralları buraya taşındı), `docs/tasks/04-decision-parser.md` (dergi düzenleri, `hukuk_ingest.decisions`), `docs/tasks/05-decision-load.md` (kararın inceleme kuyruğuna yazılması), `docs/tasks/12-file-management.md` (`FileStore`, `ingest_job` / `ingest_file`, worker), `docs/tasks/13-upload-detect-approve.md` (eşleşme, `matches`), `docs/decisions.md` (dergi özeti editoryal; karar metni kaynak).
Skill'ler: `db-migration`, `frontend-ui` (bağlayıcı), `task-pr-hygiene`.

## Sorun

Dergi her ay yeni bir karar sayısı yayımlıyor. Arşivimiz 90. sayıda kaldı. 91. sayı sitede 70 kararla duruyor, bizde yok (10.11.2026 kontrolü). Yeni sayıyı içeri almanın tek yolu kararları tek tek indirip yüklemek. Hangi kararın ne zaman, nereden geldiği de bir yerde tutulmuyor.

## Hedef (Orhan, 2026-11-10)

Sistem her cumartesi 11:00'de (Europe/Istanbul) dergiyi kendisi tarar, arşivde olmayan yeni sayıların kararlarını indirir ve inceleme kuyruğuna koyar. Her karar "otomatik taramadan geldi" bilgisini, kaynak adresini ve tarama zamanını taşır. Her taramanın sonucu dashboard'da bir tabloda görünür. Cumartesi WP grubuna kısa bir bilgi mesajı gider.

Kararlar (Orhan, 2026-11-10):
1. Kapsam yalnız **yeni sayılar**. Eski sayılardaki eksik kararlar (90. sayıda sitede 97, arşivde 56) ayrı issue; bu görevde yok.
2. Tarama ürünün parçasıdır (app), Themis'in cron'u değildir.
3. Kaynağın "otomatik tarama" olduğu inceleme kuyruğunda görünür ve filtrelenir.
4. Siteden toplu çekme için şimdilik engel yok (robots.txt yalnız `/wp-admin/`'i kapatıyor; 10.11 kontrolü). Nazik hız sınırı uygulanır.
5. Dergi başlığı ve özeti: İbrahim'in kuralı (2026-10-03) yeni kararlarda da geçerlidir. Derginin başlığı ve özeti yalnız arama içindir, kullanıcıya kaynak olarak gösterilmez; kaynak, alttaki mahkeme kararı metnidir. (Bu, mevcut ayrıştırıcı ve yükleyici davranışıdır; yeni kod onu bozmaz.)
6. Canlıda ilk koşu **14.11.2026 cumartesi 11:00**.

İki PR: **20a** backend (keşif, indirme, kuyruğa alma, zamanlama, API), **20b** dashboard (Taramalar ekranı, kuyruk rozeti ve filtresi).

## Kapsam

### 20a: backend

1. **Keşif** (yeni modül `services/app/app/journal/`; HTTP istemcisi enjekte edilebilir, testte sahte istemci):
   - Site bir WordPress. Sayılar kategori: `GET https://yargi.calismatoplum.org/wp-json/wp/v2/categories?search=sayi&per_page=100` (10.11'de 93 kategori; slug `91-sayi-yargi-kararlari`, `count` 70). Sayı numarası slug'ın başındaki sayıdır.
   - Bir sayının kararları: `GET /wp-json/wp/v2/posts?categories=<id>&per_page=100&page=N&_fields=id,link` (sayfalama `X-WP-TotalPages` ile izlenir; 91. sayıda `X-WP-Total: 70`, 1 sayfa). Her yazı = bir karar sayfası.
   - PDF bağlantısı REST içeriğinde **yok**; karar sayfasının HTML'inde JetEngine bağlantısı olarak duruyor (`a.jet-listing-dynamic-link__link[href$=".pdf"]`, ör. `/wp-content/uploads/2026/10/70.pdf`). Sayfada tam bir PDF bağlantısı bulunmazsa o karar `error: pdf_link_missing` olur.
   - REST API cevap vermezse kategori HTML sayfasına düşülmez; tarama `failed` olur ve sebebi yazılır (sessiz yarım tarama yok).
   - **Yeni sayı** = numarası arşivdeki en yüksek sayıdan büyük olan ve arşivde hiç kararı olmayan sayı. Arşivdeki sayı numarası mevcut kayıtlardan okunur (`journal_no` / Görev 05 provenance'ı); sabit "90" yazılmaz.
2. **İndirme kuralları** (#83'ten):
   - İstekler arası en az 2 sn, tek bağlantı, tanımlı `User-Agent`; 429/5xx'te sınırlı geri çekilmeli tekrar (en fazla 3).
   - İçerik PDF imzasıyla (`%PDF`) ve boyutla kontrol edilir; HTML / hata sayfası PDF diye alınmaz, `error` ile listelenir.
   - Her dosya `FileStore`'a konur (12a). sha256 zaten varsa yeni dosya açılmaz, "mükerrer" sayılır.
3. **Kaynak bilgisi** (sorulan ana şey: kararın taramadan geldiği bilinsin):
   - Her tarama bir `ingest_job` satırıdır, `kind = crawl` (enum'da zaten var). `created_by` NULL (sistem).
   - Her indirilen dosya bir `ingest_file` satırıdır: `job_id` taramanın işi, `origin_url` PDF adresi, `uploaded_by` NULL, `uploaded_at` indirme zamanı. Karar sayfasının adresi, sayı numarası ve yazı kimliği `scan_result` içinde (`journal: {issue_no, post_id, page_url, pdf_url}`).
   - Böylece "otomatik taramadan geldi" bilgisi yeni bir bayrak değil, `ingest_job.kind = crawl` üzerinden türetilir. Kuyruk ve karar detayı API'si bunu `origin: "journal_scan"` (yükleme için `upload`, ilk arşiv için `archive`) ve `origin_url`, `scanned_at` olarak döner.
4. **Kuyruğa alma:** indirilen PDF Görev 04 ayrıştırıcısıyla (`hukuk_ingest.decisions`) okunur ve Görev 05 yükleyicisinin yazdığı biçimde `source` + `extraction` olarak **bekleyen** duruma yazılır (yükleyicinin yazma yolu yeniden kullanılır, kopyalanmaz). Kurallar:
   - `verification` teyitsiz; `source_rank = editorial` (Görev 05 kuralı). Otomatik onay ve yayın yok, toplu onay bandı uygulanmaz.
   - Aynı karar kimliği (mahkeme + daire + E/K) arşivde zaten varsa kayıt yine açılır, ama mevcut kayda işaretli "mükerrer adayı" olur (Görev 13 `matches` deseni). Mevcut onaylar ve düzeltmeler değişmez.
   - Ayrıştırıcının okuyamadığı dosya kuyruğa yine düşer (alanlar boş, sebep görünür); kaybolmaz.
5. **Tarama kaydı ve tekrar:** yeni tablo `journal_scan` (Alembic): `id`, `job_id` (FK `ingest_job`), `trigger` (`schedule` | `manual`), `started_at`, `finished_at`, `status` (`running` | `completed` | `completed_with_errors` | `failed`), `new_issues` (int[]), sayaçlar (`discovered`, `downloaded`, `duplicates`, `queued`, `errors`), `report` JSONB (sayı bazında: sitedeki karar sayısı, indirilen, hata listesi URL + sebep). Gerekirse `ingest_job.stats` yerine bu tablo; ikisi aynı bilgiyi iki kez tutmaz.
   - Aynı sayı ikinci kez tarandığında yeni kayıt üretilmez (sha256 + `post_id`). Yarıda kalan tarama bir sonraki koşuda kaldığı yerden devam eder.
   - Aynı anda iki tarama koşmaz (Postgres advisory lock); ikincisi `skipped` olarak hemen döner.
6. **Çalıştırma:** CLI `python -m app.journal.scan [--dry-run] [--issue N]`. `--dry-run` hiçbir şey yazmaz, yalnız keşif raporu basar. `--issue N` tek sayıyı tarar (prova ve elle kurtarma için; "yeni sayı" kuralını yalnız o sayı için atlar, mükerrer kuralları geçerli).
7. **Zamanlama:** Dokploy zamanlanmış işi, `app` servisinde, `0 11 * * 6`, `Europe/Istanbul`, komut `python -m app.journal.scan`. Kurulum adımı `docs/deploy.md`'ye yazılır (repo'ya sunucu kimliği girmez). Worker'a zamanlayıcı eklenmez.
8. **API** (OpenAPI tipleri yeniden üretilir): `GET /journal-scans` (sayfalı, en yeni önce), `GET /journal-scans/{id}` (rapor dahil). Yetki `reviewer` ve `admin`. Kuyruk uç noktasına `origin` filtresi ve alanı.
9. **WP bildirimi için özet:** `GET /journal-scans/latest/summary` yalnız sayıları döner, metin değil (`issues`, `queued`, `duplicates`, `errors`, `status`, `finished_at`); metni app üretmez. Mesajı Themis cumartesi 11:30'da bu uç noktadan okuyup gruba atar (aşağıda, repo dışı).

### 20b: dashboard

10. Yan menüde **Taramalar**. Tablo: tarih/saat, tetikleyen (otomatik / elle), durum rozeti, yeni sayılar, bulunan, kuyruğa alınan, mükerrer, hata. Satır → detay: sayı bazında rapor, hata listesi (URL + sebep), "Bu taramadan gelen kararlar" bağlantısı (kuyruk, bu işe filtreli). Mobilde kart (10e kuralları).
11. **İnceleme kuyruğu:** "Otomatik tarama" rozeti; kaynak filtresi (Tümü / Otomatik tarama / Yükleme / Arşiv). Karar detayında kaynak satırı: "Otomatik tarama, 14.11.2026 11:02, 91. sayı" + dergi sayfasına bağlantı.
12. Metinler `messages/tr.json`'da; 360 / 768 / 1440 ekran görüntüleri PR'da.

## Kapsam dışı

- Eski sayılardaki eksik kararlar (90. sayıda 41 eksik dahil): ayrı issue.
- Yargıtay sitesinden teyit (#86) ve otomatik onay / yayın.
- Dashboard'dan "Şimdi tara" düğmesi (elle tarama CLI ile yapılır; ihtiyaç olursa sonraki iş).
- Resmî Gazete / KAYSİS takibi (#85).
- Dergi PDF'inin görünümünü değiştirmek (başlık kırpma vb.).

## Kabul kriterleri

- Her PR'da backend `ruff`, `mypy`, `pytest`, frontend `pnpm lint typecheck test build format:check` yeşil; migration ileri / geri test edilir; OpenAPI tipleri güncel.
- 20a testleri (sahte HTTP istemcisiyle): yeni sayı doğru bulunur, arşivdeki sayı atlanır; sayfalama izlenir; HTML dönen "PDF" `error` olur, kayıt açılmaz; 429'da tekrar, 3 denemeden sonra hata; aynı tarama iki kez koşunca yeni `ingest_file` / `extraction` yok; yarıda kesilen tarama devam eder; eşzamanlı ikinci tarama `skipped`; yeni kayıtlar `pending` + teyitsiz + `editorial`; arşivde aynı E/K'li karar varsa mükerrer adayı işaretli, mevcut onaylı kayıt değişmez; `--dry-run` DB'ye yazmaz; kuyruk API'si `origin = journal_scan` döner ve filtreler.
- **Prova (yerel demo yığını, gerçek site):** `python -m app.journal.scan --dry-run` 91. sayı için 70 karar ve 70 PDF bağlantısı raporlar; ardından `--issue 91` gerçek koşu: indirilen + mükerrer + hata = 70, kuyruğa alınanlar dashboard'da "Otomatik tarama" rozetiyle görünür, birkaçının alanları PDF'le elle karşılaştırılır (sonuç PR'da). Aynı komutun ikinci koşusu 0 yeni kayıt.
- Canlıda etkinleştirme Orhan'ın ayrı onayıyla. Sonrasında canlıda `--dry-run` koşusu ve Dokploy zamanlanmış işin kaydı PR'a / deploy notuna yazılır.

## WP bildirimi (repo dışı, Themis)

Cumartesi 11:30 (TR) Themis cron'u son taramanın özetini okur, gruba tek kısa mesaj atar. Yeni bir şey yoksa ya da tarama o gün koşmadıysa mesaj atılmaz; tarama hata ile bittiyse mesaj gruba değil Orhan'a gider. Örnek:

> Haftalık dergi taraması: 91. sayı geldi. 70 karar inceleme kuyruğuna eklendi (68 yeni, 2 mükerrer adayı). Dashboard'da "Otomatik tarama" filtresiyle görebilirsiniz. (Themis)

## Notlar Claude Code için

- Görev 05 yükleyicisinin yazma yolunu (`app/loaders/decisions.py` `prepare` / `_write`) ortak fonksiyona çek, tarama onu çağırsın; kopyalama yok.
- Ağ erişimi testte yok: tüm HTTP sahte istemciyle. Gerçek site yalnız prova adımında, Themis tarafından koşulur.
- Hız sınırı ve tekrar sayısı ayar (`JOURNAL_SCAN_DELAY_SECONDS`, varsayılan 2), testte 0.
