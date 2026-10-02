# Görev 06: Kararların resmî kaynakta teyidi (E/K eşleştirme)

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/data-model.md` §5.2 (`decision.verification`, `verification_source`, `verification_ref`, `verified_at`), §11; `docs/decisions.md` (2026-10-02: resmî kaynak teyidi, Yargıtay spike'ı); `docs/spike-karararama-2026-10-02.md`; `docs/tasks/05-decision-load.md` ("Kaynak politikası"); `docs/tasks/04-decision-parser.md` (alan biçimleri).
Üstüne oturduğu iş: Görev 05 (`app.loaders.decisions`, `app.kb.publish_decision`). Görev 05 merge edilmeden implementasyon başlamaz. Tam koşu Orhan'ın onayına bağlıdır (aşağıda "Ağ politikası").

## Hedef

Onaylanmış `decision` satırlarını resmî kaynakta E/K ile aratıp sonucu `decision.verification` (+ `verification_source`, `verification_ref`, `verified_at`) alanlarına yazmak; teyit edilen kararın `source.source_rank` değerini `editorial`'dan `official_primary`'ye çıkarmak. Kaynaklar:

| Mahkeme | Resmî kaynak | `verification` (bulunursa) |
|---|---|---|
| Yargıtay (daire, HGK, İBK) | karararama.yargitay.gov.tr | `verified_official` |
| BAM / BİM | emsal.uyap.gov.tr (UYAP Emsal) | `verified_uyap` |
| AYM | kararlarbilgibankasi.anayasa.gov.tr | `verified_official` |
| Danıştay | karararama.danistay.gov.tr (Yargıtay ile aynı BİGM uygulaması; UYAP Emsal'de de Danıştay araması var) | `verified_official` |

Bulunamayan karar `not_in_source`, bulunup alanları uyuşmayan karar `mismatch` olur. Yabancı mahkeme, AİHM, ABAD kararları kapsam dışı: `verification` `unverified` kalır ve atıfa açılmaz (kaynak politikasında karşılığı yok, açık soru).

## Neden

- Kaynak politikası (2026-10-02, İbrahim): dergi arşivi yalnızca arama ve keşif aracıdır; kullanıcıya atıf = insan onayı **ve** resmî kaynakta teyit. Teyit olmadan hiçbir karar atıf olarak gösterilemez (md. 25).
- Atıf kapısı (`packages/citation`) `verification IN (verified_official, verified_uyap)` filtresini bu görevin yazdığı alana dayanarak uygular.
- Teyit, `source_rank` güncellemesinin tek meşru yoludur (md. 26): rank'i yükselten kod başka yerde olmamalı.

## Kapsam

### 1. Yer ve paket ayrımı

- **Yeni paket `packages/verify`** (`hukuk_verify`): kaynak adaptörleri, eşleştirme kuralları, hız sınırlayıcı, robots.txt kontrolü. **DB bilmez**, HTTP istemcisi enjekte edilir; çıktı saf veri sınıfı (`VerifyResult`). Gerekçe: `packages/ingest` ve `packages/calc` kalıbı (AGENTS.md: DB'ye yazan kod `app`'te, paketler saf), adaptörler kayıtlı yanıt fixture'larıyla ağsız test edilir.
- **`services/app` içinde `app.verification`**: DB okuma/yazma, aday seçimi, idempotentlik, rapor, CLI: `python -m app.verification [--court yargitay|bam|aym|danistay] [--limit N] [--dry-run] [--report <dir>] [--i-have-permission]`. Worker job'u bu görevde yok.
- `packages/ingest`, `packages/citation` değişmez. Yeni bağımlılık: yalnızca `httpx` (zaten varsa yenisi eklenmez; Görev 03 ile aynı karar).

### 2. Teyit yazımı: `decision` satırlarına (onaydan sonra), extraction adaylarına değil

Seçim: **`decision` satırı**, yani yalnızca Görev 05'in `publish_decision` ile ürettiği (insan onaylı) kayıtlar.

Gerekçe:
- `data-model.md` §5.2 alanları zaten `decision`'da; §3-4: extraction değişmezdir (yeniden parse eski onayı bozmaz), teyit extraction'a yazılırsa bu değişmezlik bozulur.
- İstek sayısı onaylanan kayıtla sınırlı: tam arşiv ~6.300 adaydan ~5.800 sorgu yerine yalnızca onaylananlar sorgulanır; resmî siteye gereksiz yük bindirmeyiz (ağ politikası).
- Atıf kapısının tek bir tabloya baktığı net bir model: `decision.verification`.

Ödünleşme (kabul edilen): inceleme sırasında hakem (Baran / İbrahim) kararın resmî kaynakta bulunup bulunmadığını **göremez**; "bulunamayan karar onaylanır, sonra `not_in_source` çıkar" olabilir. Hafifletme: Görev 05'in onay akışı teyitten bağımsız çalışır; inceleme ekranı görevinde `decision.verification` rozet olarak gösterilir, teyit toplu job'u onaylanan her partiden sonra koşar. Alternatif (extraction'a yazıp inceleme ekranında göstermek) daha iyi inceleme deneyimi verir ama ~6.300 sorgu ve extraction değişmezliğinin gevşetilmesi demektir; Orhan farklı seçerse bu bölüm değişir (açık soru 4).

### 3. Kaynak adaptörleri

Ortak arayüz (`hukuk_verify.adapters.base`): `lookup(query: DecisionKey) -> LookupResult`, `fetch_text(ref) -> OfficialText | None`. `DecisionKey` = `decision`'ın `court, court_level, chamber, source_chamber, bam_region, esas_no, karar_no, decision_date, decision_kind` alanları. Adaptör ağ hatasını ve 429'u istisna olarak yükseltir; **ağ hatası asla `not_in_source` sayılmaz** (satır `unverified` kalır, "tekrar dene" kuyruğuna girer).

**3.1 Yargıtay** (`adapters/yargitay.py`), `docs/spike-karararama-2026-10-02.md` ile aynı sözleşme:
- `GET /` (cookie) sonra `POST /aramadetaylist`, gövde `{"data": {birimYrgHukukDaire | birimYrgKurulDaire, esasYil, esasIlkSiraNo, esasSonSiraNo, kararYil, kararIlkSiraNo, kararSonSiraNo, siralama:"1", siralamaDirection:"desc", pageSize:10, pageNumber:1}}`; başlıklar `Content-Type: application/json; charset=utf-8`, `X-Requested-With: XMLHttpRequest`, `Referer`.
- Satır: `{id, daire, esasNo, kararNo, kararTarihi}`; tam metin `GET /getDokuman?id=<id>` → `{"data": "<html>"}`.
- Daire adı biçimi: `"9. HD"` → `"9. Hukuk Dairesi"`, `"n. CD"` → `"n. Ceza Dairesi"`. HGK: `birimYrgKurulDaire: "Hukuk Genel Kurulu"`, esas `YYYY/D-N` → `YYYY/N` (`source_chamber = D`, Görev 04 kuralı). İBK için ayrı kurul adı; İBK sayısı 5, eşleme elle doğrulanır.
- Önce daire filtreli sorgu; boşsa **dairesiz** ikinci sorgu (daire adı biçimi sapmasına karşı). Dairesiz sorguda gelen satırın `daire` alanı yine karşılaştırılır (aşağıda 4).

**3.2 UYAP Emsal, BAM** (`adapters/uyap_emsal.py`):
- Aynı BİGM uygulaması (aynı `POST /aramadetaylist`, `GET /getDokuman?id=`); BAM dairesi `birimHukukMah` alanında tam adla verilir: `"Gaziantep Bölge Adliye Mahkemesi 9. Hukuk Dairesi"`. Seçenek listesi (sayfadaki `select[name="Bam Hukuk Mahkemeleri"]`, 202 seçenek) **tam ad üzerinden**: `bam_region` + `" Bölge Adliye Mahkemesi "` + `n` + `". Hukuk Dairesi"`. Listede olmayan daire (probe'da İstanbul 61. HD, Ankara 5. HD, Kayseri 8. HD yoktu) için daire filtresi konmaz, yalnızca E/K ile sorulur ve dönen `daire` alanı karşılaştırılır. İstanbul seçeneklerinde `Istanbul` (noktasız) / `İstanbul` varyantı var: bölge adı Türkçe-duyarsız normalize edilir.
- Tarih alanı `dd.MM.yyyy` (`baslangicTarihi` `dd/MM/yyyy` ile `Unparseable date` hatası verdi); tarih filtresi **kullanılmaz**, tarih sonuçta karşılaştırılır.
- Yargıtay ve Danıştay aramaları da Emsal'den yapılabilir ("Yargıtay Karar Arama", "Danıştay Karar Arama" bağlantıları); Emsal ikinci kaynak olarak yedekte tutulur, bu görevde birincil değil.

**3.3 AYM** (`adapters/aym.py`):
- Tek sayfa uygulaması (React); aranan veri `POST /api/core/public/search`, JSON gövde: `{"kararTipi": "NormDenetimi" | "BireyselBasvuru", "esasNo": "2024/157", "kararNo": "2025/121", "_timestamp": <ms>, "page": 1, "size": 5, "sort": "yayinTarihi", "order": "desc"}`. `esasNo`/`kararNo` ayrı alanlar (probe: kesin eşleşme, `total: 1`). `kararTipi` verilmezse serbest `query` alanı yalnızca kelime araması yapar ve E/K'yi yakalamaz (probe'da `"2024/157"` sorgusu 19.386 alakasız sonuç döndürdü); bu yüzden `decision_kind` → `kararTipi` eşlemesi zorunlu (`norm_denetimi`/`iptal`/`red` → `NormDenetimi`, `bireysel_basvuru` → `BireyselBasvuru`).
- Bireysel başvuruda E/K yok, başvuru numarası (`basvuruNo`, `YYYY/N`) ve karar tarihi var. Probe'da bireysel başvuru **denenmedi** (örneklemde yoktu); adaptör `basvuruNo` ile eşler ve bu bir kabul kriteri olarak ayrıca elle doğrulanır.
- Stabil kimlik: UUID (`id`). Karar sayfası: `https://kararlarbilgibankasi.anayasa.gov.tr/kbb/pages/search/Tumu?id=<base64("kbb:"+uuid), dolgusuz>&type=<kararTipi>`; metin dosyaları `GET /api/core/public/kararlar/<uuid>/dosyalar?kararTipi=...` → `url: /files/normdenetimi/<dosya-uuid>.html`. Probe'da yalnızca dosya listesi alındı; HTML'in kendisi indirilmedi.

**3.4 Danıştay** (`adapters/danistay.py`):
- `karararama.danistay.gov.tr`: Yargıtay/Emsal ile aynı BİGM kod tabanı (`/aramadetaylist`, `/getDokuman`), alan adları farklı: `daire` (örn. `"10. Daire"`, `"Büyük Gen.Kur."`, `"İdare Dava Daireleri Kurulu"`), `andKelime`/`orKelime`, `esasYil`, `esasIlkSiraNo`... Dönen satırda `daireKurul` alanı. Danıştay sayısı küçük (4); adaptör ilk sürümde yalnızca daire + E/K eşler.
- Probe'da iki Danıştay kararı da E/K ile bulunamadı (kontrol sorguları sitenin çalıştığını gösterdi, ancak hepsi 2004-2007 kararı; sitenin eski dönem kapsamı bilinmiyor). Danıştay için `robots.txt` sitenin ana alanında (`www.danistay.gov.tr`) var ve `Disallow:` boş; karar arama alt alanında yok (JSON hata döner).

### 4. Eşleştirme kuralları

Sonuç satırı ile `decision` karşılaştırılır; her alan için `match | fuzzy | mismatch | absent`:

| Alan | Kural |
|---|---|
| esas_no, karar_no | **Kesin**: `YYYY/N`, baştaki sıfırlar ve boşluklar normalize edilir. Biri uyuşmazsa sonuç aday sayılmaz (sorgu zaten E/K ile yapıldığı için buna yalnızca birden çok satır dönerse bakılır). |
| chamber | **Kanonik biçime çevirip karşılaştır**: `"9. HD"` ≡ `"9. Hukuk Dairesi"` ≡ `"Yargıtay 9. Hukuk Dairesi"`; `"n. D"` ≡ `"n. Daire"`; BAM `"İstanbul Bölge Adliye Mahkemesi 35. Hukuk Dairesi"` → (`bam_region="İstanbul"`, `"35. HD"`). Karşılaştırma Türkçe-duyarlı küçük harf (`İ/ı` dahil), noktalama ve fazla boşluk yok sayılır. Daire numarası ve tür (HD/CD/D) **tam eşit** olmalı. `source_chamber` dolu HGK kararında `D`, sonuç metninde (başlık satırı) aranır, uyuşmazlık `fuzzy` (karararama HGK satırında `D` tutmaz). |
| decision_date | `dd.MM.yyyy` → ISO. **Tam eşit**: `match`. ±3 gün: `fuzzy` (dergi karar tarihi yerine tebliğ/tashih tarihi yazabilir; Görev 04 `date_from_closing` uyarıları). >3 gün: `mismatch`. Karar tarihi boşsa `absent`. |
| court / bölge | Sonucun kaynağı (adaptör) zaten mahkemeyi belirler; BAM'da bölge uyuşmazlığı `mismatch` (iki bölgede aynı daire ve aynı E/K bulunabilir). |

Birleştirme:
- Sonuç satırı yok (ve ağ hatası yok, sorgu geçerli): **`not_in_source`**.
- E/K eşleşti; chamber `match`, tarih `match` veya `fuzzy`: **`verified_official`** (Yargıtay, AYM, Danıştay) / **`verified_uyap`** (BAM). `fuzzy` alan varsa `verification_detail.fuzzy` içine yazılır, rapora girer, ama `verified_*` olarak kalır.
- E/K eşleşti ama chamber veya tarih `mismatch`: **`mismatch`**. Bu durum atıfa açılmaz ve inceleme kuyruğuna "elle bak" olarak düşer; sistem hangisinin doğru olduğuna karar vermez.
- Birden çok satır dönerse: tam eşleşen (chamber + tarih match) tek satırsa o; birden çoksa `mismatch` + `detail.ambiguous=true`.
- `source_rank`: yalnızca `verified_official` / `verified_uyap` olduğunda `official_primary`; `mismatch` ve `not_in_source`'ta `editorial` kalır. Teyit geri alınırsa (`mismatch`'e düşerse) rank `editorial`'a döner.

### 5. Ne saklanır

- `decision.verification`, `verification_source` (`karararama_yargitay` | `uyap_emsal` | `aym_kbb` | `karararama_danistay`), `verification_ref` (resmî belge kimliği: BİGM numerik `id`, AYM UUID), `verified_at` (UTC).
- **Yeni, eklemeli (additive) şema**: `decision_verification` tablosu, her deneme bir satır (append-only): `decision_id, attempted_at, source, outcome (verified_official|verified_uyap|mismatch|not_in_source|error), official_ref, official_url, matched jsonb (alan bazında match/fuzzy/mismatch + sitedeki daire, esas, karar, tarih), official_text_sha256, error text`. `decision.verification*` bu tablonun son başarılı satırının özetidir. Alembic migration + `data-model.md` §5.2 güncellemesi aynı PR'da (Orhan onayı gerekir).
- **Resmî metin: yalnızca hash + dosya önbelleği, DB'de tam metin yok.** `official_text_sha256` ve ham yanıt `data/official/<kaynak>/<ref>.json` altında (gitignored, KVKK + telif: Görev 03'ün `data/extracted` kalıbı). Gerekçe: resmî metin anonimleştirilmiş ama kullanım koşulları okunmadı (açık soru 2); `decision.full_text` dergi metni olarak kalır. Resmî metnin `full_text` yerine geçmesi ayrı ürün kararı, bu görevin işi değil. Hash, resmî metin sonradan değişirse (anonimleştirme güncellemesi) yeniden teyidi tespit etmeye yarar.
- Kişisel veri: rapor ve loglar karar metni veya taraf adı içermez; karar yalnızca mahkeme/daire/E/K ile anılır.

### 6. Yeniden çalıştırma (idempotent)

- Aday seçimi: `decision.verification = 'unverified'` veya `verified_at < now() - <yeniden teyit aralığı>` (varsayılan: `not_in_source` ve `error` için 90 gün, `verified_*` için hiç, `mismatch` için elle `--recheck mismatch`).
- Aynı anahtar için ikinci koşu: yeni `decision_verification` satırı yalnızca sonuç değiştiyse (outcome, `official_ref` veya `official_text_sha256`) yazılır; değişmediyse yalnızca `last_checked_at` günceller. Hiçbir koşu `decision.verification` değerini aşağı çekmez (ör. `verified_official` → `not_in_source`) **sunucu hata dönmediği sürece**: bu durumda `mismatch` yazılır ve raporlanır, sessizce silinmez.
- Yarıda kesilen koşu: her kayıt kendi transaction'ı; devam etmek için aynı komut yeterli.
- `--dry-run` yalnızca ağ sorgusu yapıp DB'ye yazmaz; ancak kaynak başına en çok `--limit` (varsayılan 20) istek atar.

### 7. Hız sınırı ve 2009 öncesi atlama

- **Hız sınırı** (kaynak başına, ayrı sayaç): varsayılan **12 sn** aralık (probe'da Emsal 3 sn aralıkla ~8. istekte, Yargıtay spike'ında 4-5 hızlı istekten sonra 429); 429 veya `Erişim Sınırı Aşıldı` sayfasında üstel geri çekilme (60 sn, 120 sn, 240 sn), 3 ardışık 429'da kaynak durdurulur ve rapora yazılır. `Retry-After` gelmiyor, yalnızca bekleme kullanılır. Eşzamanlılık = 1. Aralık ve geri çekilme ayarlanabilir ama alt sınır sabit (10 sn); bunun altına inen ayar reddedilir.
- **2009 öncesi atlama sezgisi** (yalnızca Yargıtay adaptörü): `decision_date.year <= 2009` ise sorgu **atılmaz**, `not_in_source` olarak yazılır ve `matched.skipped = "pre_2009_heuristic"` işaretlenir. Gerekçe: Yargıtay spike'ı ve bu görevin kapsamındaki bilinen bulgu: 2015+ tamamı bulundu, 2010-2014 yarısı, 2009 öncesi hiçbiri (~1.500 karar). Atlanan kararlar tek bir örneklem testiyle (kapsam doğrulaması) kontrol edilir: koşu başına rastgele 20 atlanan karar gerçekten sorgulanır; biri bulunursa sezgi **kapatılır** ve rapora yazılır. 2010-2014 aralığı atlanmaz (yarısı bulunuyor). Sezgi diğer kaynaklarda uygulanmaz (BAM 2020+ ve AYM'de eski kayıt alt sınırı bilinmiyor); `--no-pre2009-skip` bayrağı sezgiyi kapatır.
- Ürün etkisi: atlanan kayıt **gösterim kararı değildir**; `not_in_source` alanı, ~1.500 kayıt için nasıl gösterileceği (açık ürün sorusu) çözülünceye kadar atıf kapısında düşer.

### 8. Ağ politikası

- Kullanıcı ajanı: tanımlayıcı (`hukuk-yz-verify/<sürüm> (iletişim: <Orhan e-posta>)`), tarayıcı taklidi yok.
- `robots.txt`: her koşu başında okunur ve uyulur. Bilinen durum (2026-10-02 probe'u): `emsal.uyap.gov.tr` ve `karararama.danistay.gov.tr` `/robots.txt` için JSON hata döner (`No static resource robots.txt`), kuralı yok; `kararlarbilgibankasi.anayasa.gov.tr` 404 (nginx); `karararama.yargitay.gov.tr` bu probe'da erişilemedi (aşağıda); `www.danistay.gov.tr` `Disallow:` boş. `robots.txt` bulunmaması izin değildir: kullanım şartları açık soru 2.
- Captcha: bir sayfa captcha isterse (`DisplayCaptcha`, `reCaptchaTimeout`) adaptör o kaynakta durur, atlatma denenmez. Hiçbir sitede giriş yapılmaz.
- **Toplu koşu, karararama / Emsal toplu sorgu izni gelene kadar yapılmaz.** CLI `--i-have-permission` bayrağı olmadan 20'den fazla istek atmaz; tam koşu Orhan'ın açık onayına bağlıdır (PR'a yorum veya `decisions.md` notu olarak kaydedilir). Bu görevin kabul testleri en çok 50 canlı istek atar.
- Testler ağa çıkmaz (kayıtlı fixture); canlı testler `LIVE=1` ile elle.

### 9. Rapor

`--report <dir>` ile `verify-summary.md` + `.json`: kaynak başına `verified_*` / `mismatch` / `not_in_source` / `error` sayıları; yıl bandı kırılımı (≤2009, 2010-14, 2015+); `fuzzy` alan sayıları; 429 sayısı ve geri çekilme süresi; atlanan (2009 öncesi) sayısı ve örneklem sonucu; `mismatch` listesi (yalnız mahkeme/daire/E/K).

## Kapsam dışı

- UI (teyit rozeti, inceleme ekranı), arama, embedding, tsvector, atıf kapısındaki filtre (ayrı görev; yalnızca alanı doldururuz).
- Resmî metnin `decision.full_text`'e kopyalanması veya chunk'lanması.
- `unverified` dergi kararlarının kullanıcıya gösterilme biçimi (açık ürün sorusu, bu görev karar vermez).
- Captcha çözme, giriş gerektiren kaynaklar (UYAP vatandaş portalı, ücretli veritabanları).
- Bireysel başvuru dışında AYM alt türleri (siyasi parti, yüce divan), yabancı mahkemeler, AİHM, ABAD.
- Görev 05'in yükleme/onay akışının değiştirilmesi.

## Probe sonuçları (2026-10-02)

Yöntem: Görev 04 çıktısından (`decisions.jsonl`) 17 kararlık karışık örneklem (seed 6), tarayıcıyla (Chromium, oturum açılmadan) site sayfasından fetch ile 12-15 sn aralıklı sorgular, toplam ~25 istek. Kararlar yalnızca mahkeme/daire/E/K ile anılır.

| Kaynak | Örneklem | Arama yöntemi | Sonuç | Captcha / hız sınırı | Tam metin | Stabil kimlik |
|---|---|---|---|---|---|---|
| karararama.yargitay.gov.tr (Yargıtay) | 8 planlandı (3 ≤2009, 2 2010-14, 3 2015+); **0 sorgulandı** | `POST /aramadetaylist` (spike 2026-10-02, tekrar edilemedi) | **Probe makinesinden erişilemedi**: `curl` 20-25 sn zaman aşımı, tarayıcı `Page.navigate` zaman aşımı; DNS çözülüyor (212.175.130.144), `www.yargitay.gov.tr` 200. Büyük olasılıkla IP/coğrafya filtresi veya güvenlik duvarı, kesin neden doğrulanmadı | Sorgu atılamadı | Spike: `GET /getDokuman?id=` | Spike: numerik `id` |
| emsal.uyap.gov.tr (BAM) | 4: İstanbul 61. HD, Kayseri 8. HD, Ankara 5. HD, Gaziantep 9. HD (hepsi 2021-2025) | `POST /aramadetaylist`, `birimHukukMah` (tam ad) + `esasYil/esasIlkSiraNo/esasSonSiraNo`, `kararYil/...`; XHR uç noktaları sayfa JS'inden: `/arama`, `/aramalist`, `/detayliArama`, `/aramadetaylist` | **0/4 bulundu** (`recordsTotal: 0`). Siteyi doğrulayan kontrol: aynı daire (Gaziantep 9. HD) için kelime aramasında satır döndü (id `853364500`, 2022); 3 dairenin (İstanbul 61, Ankara 5, Kayseri 8) seçenek listesinde karşılığı yok. Emsal tüm kararları içermiyor; kapsam oranı örneklemden çıkarılamaz | Captcha yok (koşullu `isDisplayCaptcha`). **429** (`Erişim Sınırı Aşıldı` HTML sayfası) art arda ~8 istek sonrası (3 sn aralık) ve sonraki 10 sn aralıklı 2 istekte; ~25 sn beklemeyle ve 12 sn aralıkla düzeldi. Karar sayısı sayfada 858.997 | `GET /getDokuman?id=853364500` → `{"data": "<html>"}` (başlık: daire, E/K; kişi adları noktalı) | numerik `id` (satırda); doğrudan karar URL'i yok |
| kararlarbilgibankasi.anayasa.gov.tr (AYM) | 3 norm denetimi: 2024/157 K 2025/121; 2023/158 K 2024/187; 2015/105 K 2016/133 | `POST /api/core/public/search` JSON: `kararTipi: "NormDenetimi"`, `esasNo`, `kararNo` | **3/3 bulundu** (`total: 1`), E/K ve tarih birebir uyuştu | Captcha yok; 3 sorgu 4 sn aralıkla 429 yok (sayfa yüklemelerindeki ek istekler dahil ~20 XHR) | `GET /api/core/public/kararlar/<uuid>/dosyalar?kararTipi=NormDenetimi` → `/files/normdenetimi/<uuid>.html` (liste alındı, dosya indirilmedi) | UUID (`id`); sayfa URL'i `?id=<base64("kbb:"+uuid)>&type=NormDenetimi`. Bireysel başvuru denenmedi |
| karararama.danistay.gov.tr (Danıştay) | 2: 10. Daire 2004/6075 K 2006/2159; 3. Daire 2006/3799 K 2007/414 (2006-2007) | `POST /aramadetaylist`, E/K + (gerekirse) `daire`; alan adları `andKelime`, `daire` farklı | **0/2 bulundu**. Kontrol: 10. Daire kelime aramasında 2026 satırları döndü (arama çalışıyor, `daireKurul` alanı, id `1226554300`). Eski dönem kapsamı bilinmiyor | Captcha yok (kod var, koşullu); 429 görülmedi (8-20 sn aralık) | Denenmedi | numerik `id` |

Özet bulgular:
1. **BİGM kod tabanı ortak**: Yargıtay, Emsal ve Danıştay aynı `/aramadetaylist` + `/getDokuman` sözleşmesini kullanıyor; tek ortak adaptör taban sınıfı + kaynak başına alan eşlemesi yeter.
2. **AYM en temiz kaynak**: E/K kesin eşleşme, UUID, JSON, 3/3 bulundu.
3. **BAM kapsamı belirsiz**: Emsal yalnızca seçilmiş kararları yayımlıyor gibi görünüyor (4/4 bulunamadı; kontrol aramaları aynı dairelerde başka karar buluyor). Bu bir ürün riski: ~300 BAM kararının çoğu `not_in_source` çıkabilir. 4 örnek çok küçük; tam oran yalnızca onaylı kayıtlar üzerinde ölçülür.
4. **Hız sınırı sıkı ve kaynak başına ayrı** (Emsal 3 sn aralıkta ~8 istekte 429). 12 sn alt sınır bu yüzden.
5. **Yargıtay karararama bu probe ortamından açılmıyor.** Spike başka bir ortamda çalışmıştı. Tam koşunun nereden yapılacağı (Orhan'ın Mac'i, Türkiye çıkışlı IP) açık soru.
6. **Probe tekrar edilebilirliği**: tarayıcı oturumundan yapıldı, istek gövdeleri bu dokümandaki sözleşmeyle aynı; Themis implementasyonda `LIVE=1` testiyle yeniden doğrular.

## Kabul kriterleri (Themis koşar)

- [ ] `make lint`, `make typecheck`, `make test` temiz; CI yeşil. `packages/verify` testleri ağsız (kayıtlı JSON fixture; her kaynaktan bulundu / bulunamadı / mismatch / 429 örneği).
- [ ] Eşleştirme birim testleri: chamber kanonikleştirme (`9. HD` ≡ `9. Hukuk Dairesi`; BAM tam ad ↔ bölge + daire; `Istanbul`/`İstanbul`; `n. D`), HGK `YYYY/D-N`, tarih tam / ±3 gün / >3 gün, çoklu satır, ağ hatasının `not_in_source` OLMAMASI.
- [ ] `source_rank` yalnızca `verified_*`'ta `official_primary` olur; `mismatch`/`not_in_source` `editorial` bırakır (DB testi, `DATABASE_URL` yoksa skip).
- [ ] Idempotent: aynı girdiyle ikinci koşu yeni `decision_verification` satırı üretmez; `verified_*` aşağı çekilmez.
- [ ] Hız sınırı testi: sahte saatle kaynak başına ≥10 sn aralık; 3 ardışık 429'da kaynak durur; <10 sn ayar reddedilir.
- [ ] 2009 öncesi atlama: ≤2009 Yargıtay kararı sorgusuz `not_in_source` + `skipped` işareti; örneklem kontrolü ve `--no-pre2009-skip` testli.
- [ ] Ağ politikası: `--i-have-permission` yokken 20'den fazla istek atılmaz (test); `robots.txt` kuralı (sahte `Disallow`) uygulanır.
- [ ] **Canlı doğrulama (izin gelmeden en çok 50 istek, 12 sn aralıkla, elle `LIVE=1`)**: her kaynaktan 3-5 karar, bu dokümandaki probe tablosuyla uyumlu; sonuçlar PR'da (mahkeme/daire/E/K ile, metin yok). Yargıtay erişilemiyorsa bu madde Orhan'ın ortamında koşulur ve PR'da bunun yazılır.
- [ ] Rapor kişisel veri içermez (taramayla doğrulanır).
- [ ] `data-model.md` §5.2 güncel (`decision_verification`, `verification_source` değerleri); migration geri alınabilir.

## Açık sorular (Orhan / ortaklar)

1. **Toplu sorgu izni** (Orhan): karararama (Yargıtay, Danıştay) ve Emsal için ~5.800 + ~300 sorgu. Kullanım şartları okunmadı. İzin mi, BİGM'e yazı mı, yoksa yavaş tempo (12 sn aralık ≈ 20 saat/6.000 istek) yeterli mi? Karar gelene kadar toplu koşu yok.
2. **Kullanım şartları ve resmî metin** (Orhan): resmî metni önbellekte (DB dışı) saklamak serbest mi? Önerimiz hash + dosya önbelleği; ürün resmî metni göstermek isterse ayrı görev ve şart kontrolü.
3. **Koşu ortamı** (Orhan): karararama bu sunucudan açılmıyor. Teyit nereden koşacak (Mac, Türkiye çıkışlı sunucu)? Zaman aşımının IP filtresinden mi geçici bir kesintiden mi olduğu doğrulanmadı.
4. **Teyit nereye yazılsın** (Orhan): önerimiz yalnızca onaylı `decision` satırları (az istek, extraction değişmez), bedeli: hakem inceleme sırasında teyit sonucunu göremez. Alternatif: tüm extraction adaylarına yazıp inceleme ekranında göstermek (~6.300 sorgu).
5. **2009 öncesi ve resmî kaynakta bulunamayan ~1.500 karar** (İbrahim / Baran, açık ürün sorusu, bu görev karar vermez): hiç gösterilmesin mi, tam metin + "resmî veritabanında yer almamaktadır" notuyla mı? `not_in_source` yalnızca alanı doldurur.
6. **BAM kapsamı** (İbrahim): Emsal tüm BAM kararlarını yayımlamıyorsa (probe: 0/4) `not_in_source` oranı yüksek çıkabilir. Başka BAM kaynağı (UYAP vatandaş, lisanslı veritabanı) aransın mı, yoksa BAM kararı doğrudan atıf dışı mı kalsın?
7. **`mismatch` sahibi** (Baran / İbrahim): E/K bulundu ama daire veya tarih uyuşmuyorsa kim, hangi ekranda karar verir? Önerimiz: inceleme kuyruğuna geri düşer, atıfa kapalı kalır.
8. **AYM bireysel başvuru** (Orhan): parser `esas_no` alanında başvuru numarasını mı tutuyor? Probe'da bireysel başvuru örneği yoktu; adaptör `basvuruNo` eşlemesi varsayımdır.
9. **Yabancı mahkeme / AİHM / ABAD** (İbrahim): kaynak politikası bunları kapsamıyor; `unverified` kalıp atıf dışı mı kalsın, yoksa kendi resmî kaynakları (HUDOC, EUR-Lex) mı eklensin?

## Notlar Claude Code için

- Önce `docs/data-model.md` §3-§5.2, `services/app/app/models/` ve Görev 05'in `app.kb.publish_decision` kodunu oku; alan ve enum adlarını tahmin etme.
- `packages/ingest`'e ve `packages/citation`'a dokunma. `hukuk_verify` DB bilmez; `app.verification` tek DB yazıcısıdır.
- Yeni şema (`decision_verification`, rank güncellemesi) için Alembic migration ve `data-model.md` değişikliği aynı PR'da; Orhan onaylamadan merge yok.
- Adaptör fixture'ları gerçek yanıtlardan **kısaltılmış** ve kişi adı içermeyecek biçimde alınır; gerçek karar metni commit edilmez.
- Yanıt zarfı: `metadata.FMTY == "ERROR"` bir hatadır, `not_in_source` değil. `429` HTTP durumu ve `Erişim Sınırı Aşıldı` gövdesi ikisi de 429 sayılır (gövde HTML döner, JSON değil).
- Canlı istek atan her kod yolu `--i-have-permission` ve `LIVE=1` arkasında olsun; varsayılan çalıştırma ağsızdır.
- Tarayıcı gerekmez: tüm kaynaklar düz HTTP + JSON ile çalışıyor (Yargıtay'da önce `GET /` ile cookie).
