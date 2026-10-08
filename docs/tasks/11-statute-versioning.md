# Görev 11: Mevzuat sürümleme (4857 + 5510, madde düzeyi)

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/data-model.md` §5.1 (`statute`, `statute_article`, `statute_article_version`), §3-4 (`ingest_*`, `extraction`, `review`, durum makinesi), §7 (atıf çözümleme), `docs/roadmap.md` ("Mevzuat sürümleme zorluğu"), `docs/tasks/03-ingest.md`, `docs/tasks/07-ocr-and-legacy-doc.md` (eski `.doc` okuyucu), `docs/tasks/05-decision-load.md` (yükleme + güven skoru kalıbı).
Skill'ler: `task-pr-hygiene`, `db-migration` (11b'de şema değişikliği olursa).

## Hedef

"4857 m.18, 2014-01-01 tarihinde nasıl yazılıydı?" sorusuna sistemin **ya doğru metni ya da "bu tarih için metin elimizde yok" cevabını** vermesi (md. 4). Yanlış sürümü güncel metinle doldurmak, hiç cevap vermemekten kötüdür (md. 25): bilinmeyen aralık boş bırakılır ve öyle raporlanır.

Bu görev 4857 (İş Kanunu) ve 5510 (Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu) ile sınırlı. Kalıp oturunca diğer kanunlar (4447, 6331, 6356...) aynı hattan geçer.

## Elimizdeki veri (Themis ölçümü, 2026-10-06)

Mevzuat metinleri resmî konsolide metnin (mevzuat.gov.tr) farklı tarihlerdeki kopyaları. Her biri o tarihteki **tam metin** (snapshot).

| Kanun | Dosya | Tarih (dosya adından / içerikten) | Durum (Görev 03 + 07) |
|---|---|---|---|
| 4857 | `Kanunlar/4857 sayılı İş Kanunu 13.05.2016 .docx` | 13.05.2016 | ok |
| 4857 | `Kanunlar/4857 sayılı İş Kanunu.pdf` | tarih yok; en yeni değişiklik notu 22/4/2026-7578 | ok |
| 5510 | `Kanunlar/1.5.5510 (27.09.2016).doc` | 27.09.2016 | eski `.doc` (Görev 07 okuyucu) |
| 5510 | `Kanunlar/Eskiler/5510 Tarih 04.05.2017.doc` | 04.05.2017 | eski `.doc` |
| 5510 | `Kanunlar/Eskiler/5510 tarih 04.10.2017.pdf` | 04.10.2017 | ok |
| 5510 | `Kanunlar/Eskiler/5510 tarih 08.01.2018.pdf` | 08.01.2018 | ok |
| 5510 | `Kanunlar/Eskiler/5510 tarih 14.07.2020.pdf` | 14.07.2020 | ok |
| 5510 | `Kanunlar/Eskiler/5510 tarih 17.07.2024.pdf` | 17.07.2024 | ok |
| 5510 | `Kanunlar/5510 ... tarih 24.11.2025.pdf` (ve `Eskiler/` altında aynı sha256) | 24.11.2025 | ok |

Metinde iki tür tarih bilgisi var:

1. **Satır içi değişiklik notları:** `(Değişik birinci fıkra: 12/10/2017-7036/11 md.)`, `(Ek cümle: 10/9/2014-6552/2 md.)`, `(Mülga: ...)`, `(İptal: ...)`. Hangi kanunun hangi tarihte (kabul tarihi) maddenin hangi parçasını değiştirdiğini söyler. Güncel 4857'de 93 not / 24 değiştiren kanun, 5510 (2025) metninde 503 not / 74 kanun; ikisi birlikte 87 farklı (tarih, kanun) çifti. Not eski metni vermez.
2. **Dipnotlar** (5510 PDF'lerinde ve 4857 docx'te): "…bu fıkranın 1/1/2015 tarihinde yürürlüğe gireceği hüküm altına alınmıştır" gibi **yürürlük tarihi istisnaları**. Sayfa altında `––––` çizgisinden sonra gelir, madde metnine karışmamalı.

Sonuç: eski metni **ardışık snapshot'ların farkı** verir, değişikliğin tarihini **satır içi not + değiştiren kanunun yürürlük tarihi** verir. İkisi birleşince sürüm aralığı kurulur. En eski snapshot'tan (4857 için 2016, 5510 için 2016) önceki metin elde yok.

## Yaklaşım

Görev iki PR'a bölünür (her biri 1-3 saatlik Claude Code işi); inceleme ekranı ayrı spec (11c).

### 11a: ayrıştırma + zaman çizelgesi (DB yok, `packages/ingest`)

1. **Madde bölme** (`hukuk_ingest.statutes.split`): snapshot metnini `statute` başlık bilgisi (numara, kabul tarihi, RG tarih/sayı) + madde listesine böler.
   - Madde başlığı biçimleri: `Madde 18 -`, `MADDE 18-`, `Ek Madde 2 -`, `EK MADDE 2-`, `Geçici Madde 4 -`, `GEÇİCİ MADDE 4-`. `article_no` normalize: `"18"`, `"Ek 2"`, `"Geçici 4"`; `ordinal` metindeki sıra.
   - Kenar başlığı (`heading`): madde başlığından önceki satır (ör. "Feshin geçerli sebebe dayandırılması"); bölüm başlıkları (BİRİNCİ BÖLÜM...) başlığa karışmaz.
   - Gürültü: sayfa numaraları, tekrar eden sayfa başlıkları, PDF satır kırılmaları (paragraf içi satır birleştirme), dipnot blokları. Dipnotlar metinden çıkarılır ama atılmaz: ait olduğu maddeye `footnotes` olarak bağlanır (dipnot işareti `(1)` metinde kalır).
   - `(Mülga: ...)` tek satırlık maddeler madde olarak kalır, durumları `repealed`.
2. **Değişiklik notu ayrıştırma** (`hukuk_ingest.statutes.annotations`): her madde için notların listesi `{kind: degisik|ek|mulga|iptal, scope: "birinci fıkra"|"cümle"|..., date: ISO, law: "6552"|"KHK-665", law_article: "2", raw}`. Ayrıştırılamayan not `unparsed_annotation` uyarısıyla `raw` olarak kalır, kaybolmaz.
3. **Snapshot farkı** (`hukuk_ingest.statutes.diff`): aynı kanunun ardışık iki snapshot'ında her madde için `unchanged | changed | added | removed`. Karşılaştırma normalize edilmiş metinde yapılır (boşluk, satır kırılması, tırnak ve dipnot işaretleri farkı değişiklik sayılmaz). Farkın gürültü mü gerçek mi olduğuna karar verilemezse `uncertain_diff` uyarısı.
4. **Değiştiren kanun kaydı** (`packages/ingest/hukuk_ingest/statutes/amending_acts.toml`, **repo'da**, kamu verisi; TOML çünkü stdlib `tomllib` okur, yeni bağımlılık yok. Repo'daki `data/` gitignored olduğu için oraya konmaz): her değiştiren kanun için `law, kabul_tarihi, rg_tarihi, rg_sayisi, yururluk` (varsayılan: RG tarihi), `article_exceptions` (dipnottaki ya da kanunun yürürlük maddesindeki istisnalar: `{madde: "18", fikra: "..", yururluk: ..}`) ve `source_url`. Kayıt Themis tarafından resmî kaynaktan (RG / mevzuat.gov.tr) doldurulur, her satırda kaynak URL'si zorunlu. Doldurulmamış satır `yururluk_unknown`. Uydurma tarih yok.
5. **Zaman çizelgesi** (`hukuk_ingest.statutes.timeline`): her madde için sürüm listesi `[{text, heading, valid_from, valid_to, change_kind, amending_ref, evidence, confidence}]`:
   - İki snapshot (S1 tarih d1, S2 tarih d2) arasında madde değişmişse: S2'deki metinde, kabul tarihi (d1, d2] aralığında olan değişiklik notları aranır. Tek kanun çıkarsa `valid_from` = o kanunun (madde istisnası varsa istisnadaki) yürürlük tarihi; eski sürümün `valid_to` = aynı tarih. Birden fazla kanun çıkarsa (aynı aralıkta iki değişiklik) ara metin bilinmez: ara sürüm oluşturulmaz, aralık `gap` olarak işaretlenir (`multi_amendment_in_window`). Hiç not çıkmazsa `unexplained_change` (veri ya da ayrıştırma hatası; low).
   - En eski snapshot'taki metin: maddenin o snapshot'taki **en yeni** notunun yürürlük tarihinden geçerli sayılır. Hiç notu yoksa ve madde `Ek`/`Geçici` değilse, kanunun yürürlük tarihinden (`statute` başlığı + kanunun yürürlük maddesi; 4857 için 10.06.2003, 5510 için md. 108'deki tarih ayrıca kayıtta) geçerli, `change_kind original`. Daha önceki dönem (notu olan maddede ilk yürürlük ile en yeni not arası) **`gap`**: sürüm satırı yok, çizelgede `{from, to, reason: "before_earliest_snapshot", known_amendments: [...]}` olarak yer alır.
   - En yeni snapshot'taki metin `valid_to = null` (hâlâ yürürlükte). En yeni snapshot'tan sonra yayımlanmış değişiklik bu görevin kapsamı dışında (bkz. "Güncellik" altında).
   - Kesişen aralık üretilmez; DB'deki EXCLUDE kısıtı zaten reddeder, ama çizelge üretiminde de test edilir.
6. **CLI:** `hukuk-ingest statutes --scan-report files.jsonl --acts <amending_acts.toml> (varsayılan paketteki dosya) --out <dir>` → `statutes.jsonl` (kanun başına bir kayıt: başlık + maddeler + çizelge), `statutes-report.md/.json`: kanun başına madde sayısı, snapshot başına bölünen madde sayısı, değişen / eklenen / kaldırılan madde sayısı, sürüm sayısı, `gap` sayısı ve toplam gün, uyarı dağılımı, yürürlük tarihi eksik kanunlar.
7. **Güven bandı** (11b'de toplu onay için): `high` = tüm geçişleri tek kanunla açıklanan ve yürürlük tarihi kayıtta olan madde; `medium` = istisna dipnotundan gelen yürürlük, `uncertain_diff`, `gap` içeren ama geri kalanı temiz madde; `low` = `unexplained_change`, `multi_amendment_in_window`, `unparsed_annotation`, `yururluk_unknown`, madde bölmede şüphe (numara atlaması, tekrar). Kurallar tek tabloda, Görev 05'teki `confidence.py` kalıbıyla.

### 11b: KB'ye yükleme + tarihli sorgu (`services/app`)

1. **Yükleyici** `python -m app.loaders.statutes <statutes.jsonl> [--dry-run] [--report <dir>]`: her snapshot dosyası `ingest_file`; her kanun bir `source` (category `statute`, `source_rank` `official_secondary`: konsolide metin resmî ama RG'nin kendisi değil; `license` `public`), her **madde çizelgesi** bir `extraction` (parser `statutes`, `fields` = çizelge, `confidence` = madde 7). İnceleme birimi **madde**, sürüm değil. Idempotent (sha256 + parser sürümü), Görev 05 ile aynı kural.
2. **Onay → tipli tablolar:** `kb.publish_statute_article(extraction_id, review_id)`: `statute` (yoksa), `statute_article`, çizelgedeki her sürüm için `statute_article_version` (`gap` satır üretmez). `--approve-band high --reviewer <id>` bayrağı Görev 05'teki gibi, varsayılan kapalı.
3. **Tarihli sorgu:** `kb.article_as_of(statute_no, article_no, as_of)` → `{status: found|gap|not_in_force|unknown_article, version?, gap?}`. `gap` dönerse bilinen değişiklikler (kanun no + tarih) listelenir, metin dönmez. API: `GET /statutes/{number}/articles/{article_no}?as_of=YYYY-MM-DD` (yetki: giriş yapmış kullanıcı; hata kodları `errors.py` kalıbında). Agent ve atıf kapısı bunu kullanacak (md. 25: `gap` atıf olarak geçemez).
4. **Şema:** `statute_article_version`'da eksik alan çıkarsa (`evidence` jsonb: hangi snapshot'lar + hangi not; `footnotes`) Alembic migration, `db-migration` skill'i. `gap` için ayrı tablo açılmaz: çizelge `extraction.fields`'ta kalır, sorgu `version` bulamazsa yayımlanmış çizelgeden `gap` bilgisini okur. (Bu karar PR'da gerekçesiyle yazılır; daha iyi yol çıkarsa önce Themis'e sorulur.)

### 11c: inceleme ekranı (spec: `docs/tasks/11c-statute-review.md`)

Madde çizelgesini zaman çizgisi olarak gösterir: sürümler, aralarındaki fark (eski / yeni metin yan yana), dayanak not ve yürürlük kaynağı, `gap` aralıkları. Toplu onay `high` bant için. 11b merge edildikten sonra yazılır.

## Kapsam dışı

- 4857 ve 5510 dışındaki kanunlar, yönetmelik, tebliğ, genelge (`admin_act`).
- En eski snapshot'tan önceki metni yeniden kurmak (RG'deki değiştiren kanun metninden geriye uygulama). Örnek: 4857 m.18'deki "(Ek cümle: 10/9/2014-6552/2 md.)" cümlesi 2016 snapshot'ında var, 2014 öncesi metin elde yok; bu görevde o dönem `gap`. Geri kurma ayrı görev (aşağıda "Açık sorular").
- mevzuat.gov.tr'den otomatik çekme / değişiklik izleme (sunucudan erişim yok, Mac'ten ya da ileride Context.dev Monitors ile; `tasks.md` "Sonraya").
- Karar kayıtlarındaki `related_articles` alanını sürüme bağlamak (atıf çözümleyici görevi).
- Embedding, `chunk`, arama.
- İnceleme arayüzü (11c).

## Kabul kriterleri (Themis koşar)

11a:
1. `make lint`, `make typecheck`, `make test` yeşil. Testler modüle göre: `test_statutes_split.py`, `test_statutes_annotations.py`, `test_statutes_diff.py`, `test_statutes_timeline.py`. Fixture'lar kısa madde parçaları (kamu metni, kişisel veri yok).
2. Tam koşu (9 snapshot): 4857 güncel metinde 132 madde başlığı (119 madde + 10 geçici + 3 ek; Themis ölçümü), 5510 (2025) metninde 226; rapordaki sayılar bununla tutar ya da fark PR'da madde madde açıklanır. Numara atlaması / tekrarı raporda sıfır ya da tek tek açıklanmış.
3. Değişiklik notlarının en az %98'i ayrıştırılır (4857 için 93, 5510 (2025) için 503 not); ayrıştırılamayanlar raporda listelenir.
4. Dipnot metni hiçbir maddenin `text`'ine karışmaz (testli; ayrıca tam koşuda `––––` ve `hüküm altına alınmıştır` içeren madde metni sayısı 0).
5. **Altın set** (`tests/fixtures/statutes/golden.toml`, en az 20 sorgu: madde + tarih → beklenen durum ve metnin ayırt edici bir ifadesi): Themis hazırlar, beklenen değerleri snapshot'lardan ve RG'den elle çıkarır, kaynağını yazar. En az 5'i `gap` dönmesi gereken durum (ör. 4857 m.18 @ 2014-01-01). Çizelge setin tamamını geçer.
6. `amending_acts.toml`'da 87 (tarih, kanun) çiftinin hepsi var; `yururluk` dolu olmayan satır sayısı raporda. Dolu her satırda `source_url`.
7. Çizelgelerde kesişen aralık 0 (test + tam koşu).

11b:
1. Lint / typecheck / test yeşil; DB testleri `DATABASE_URL` yoksa skip, CI'da koşar.
2. Yükleyici aynı girdiyle iki kez çalışınca yeni satır yok.
3. Altın setin 20 sorgusu `GET /statutes/.../articles/...?as_of=` ile aynı sonucu verir (DB'li test).
4. `gap` dönen sorguda cevapta metin alanı yok (test).

## Güncellik

En yeni 4857 metni 22/4/2026 tarihli değişikliği içeriyor, 5510 metni 24.11.2025 tarihli. Arada çıkan değişiklik varsa sistem eski metni "hâlâ yürürlükte" gösterir. 11a raporu her kanun için "son snapshot tarihi"ni yazar; ürün bu tarihi kullanıcıya gösterir. Güncel metni almak ayrı iş (Mac'ten çekme ya da ortaklardan güncel kopya).

## Açık sorular (Orhan)

1. **Snapshot öncesi dönem:** 2016 öncesi olaylar (ör. 2012'deki bir fesih) için metin yok. Seçenekler: (a) `gap` olarak bırak, kullanıcıya "bu tarih için madde metni doğrulanamadı" de (bu spec bunu varsayıyor); (b) mevzuat.gov.tr / RG'den eski konsolide metinleri ya da değiştiren kanunları toplayıp geriye kur (ayrı görev, Mac'ten). Hangi tarihten öncesi önemli? İbrahim'e sorulabilir: dava/denetim pratiğinde kaç yıl geriye gidiliyor.
2. **4857'nin 2016-2026 arası tek adım:** iki snapshot arasında 10 yıl var; bu aralıkta aynı maddeyi iki kez değiştiren kanun varsa ara metin `gap` olur. 5510'daki gibi ara snapshot'lar (2018, 2020, 2023...) ortaklardan istenebilir mi?
3. **Yürürlük kaydını kim doğrular:** 87 satırı Themis RG'den doldurur; kaynak URL'li. Uzman teyidi (İbrahim) her satır için mi, yoksa örneklem mi?
