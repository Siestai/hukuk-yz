# Veri Modeli v0.2

Durum: v0.2, 2026-10-02 (v0.2: `decision` için `source_chamber`, `bam_region`, `uyusmazlik`; Alembic 0003). Bu doküman Faz 1'in temelidir; şema buradan Alembic'e çevrilir.

## 1. İlkeler

1. **Kaynak türleri ayrı** (md. 28). Sekiz kategori, her biri kendi tablosu ve alanlarıyla. Ortak bir `source` üst tablosu kimlik, provenance ve lisans tutar. "Document + chunk" tarzı tek genel tablo doğruluk kaynağı **değildir**: atıf çözümleme için `4857 / madde 18 / 2019-03-01` gibi yapısal anahtar gerekir. `chunk` tablosu (§8) yalnızca tipli kayıtlardan türetilen, yeniden üretilebilir bir arama indeksidir.
2. **Bitemporal.** Her yayınlanan KB kaydı iki zaman ekseninde yaşar:
   - `valid_from / valid_to`: hukuken geçerlilik (madde ne zaman yürürlükteydi, genelge ne zaman değişti). md. 4.
   - `recorded_at / superseded_at`: bizim sisteme ne zaman girdi, ne zaman yenisiyle değiştirildi. Denetlenebilirlik: "bu cevabı verdiğimizde KB'de ne vardı" sorusu cevaplanabilir (md. 35).
   KB kaydı silinmez, `superseded_at` doldurulur. Bu kural kişisel veri için geçerli değildir: case belgeleri (F) ve memory crypto-shredding ile silinir (`architecture.md` §6.1, md. 31).
3. **Provenance zorunlu.** Her kayıt: hangi dosya (hash), hangi parser sürümü, hangi iş (job), kim onayladı, ne zaman.
4. **İnsan onayı olmadan yayın yok.** Durum makinesi aşağıda.
5. **Metin ve özet ayrı** (md. 20). Editoryal özet (Çalışma ve Toplum ÖZETİ) ayrı alan, ayrı lisans, atıf olarak kullanılmaz.
6. **Generic pipeline, tipli şema.** Pipeline aşamaları her kaynak türü için aynı arayüz; çıkardığı alanlar türe özel.

## 2. Kaynak kategorileri (md. 28)

| Kod | Kategori | Tablo | Örnek |
|---|---|---|---|
| A | Mevzuat | `statute`, `statute_article`, `statute_article_version` | 4857, 5510, yönetmelikler |
| B | Uluslararası / ILO | `treaty`, `treaty_article_version` | ILO 158, AİHS |
| C | Yargı kararları | `decision` | Yargıtay 9. HD, HGK, AYM, BAM, Danıştay |
| D | İdari düzenleme | `admin_act`, `admin_act_version` | SGK genelgesi, tebliğ, genel yazı, görüş |
| E | TİS ve protokoller | `collective_agreement`, `ca_article_version` | sektör/işyeri TİS |
| F | Somut olay belgeleri | `case_document` | kullanıcının yüklediği bordro, sözleşme (KVKK; org'a özel, KB'ye girmez) |
| G | Doktrin | `doctrine` | makale, kitap bölümü (lisans kontrolü) |
| H | Hesaplama araçları | `calc_method`, `calc_parameter_version` | asgari ücret tablosu, tavan/taban, formül sürümü |

F kategorisi KB'nin parçası değil; org/case scope'unda ayrı yaşar, `agent` onu `memory` + `app` üzerinden görür.

## 3. Ortak tablolar

### `source`
Her kaynak türü kaydının üst kimliği.

| alan | tip | not |
|---|---|---|
| id | uuid | |
| category | enum | A..H, DB etiketleri: `statute` / `treaty` / `decision` / `admin_act` / `collective_agreement` / `case_document` / `doctrine` / `calc` |
| title | text | |
| official_ref | text | resmi künye (RG tarih/sayı, E/K no, genelge no) |
| source_rank | enum | `official_primary` / `official_secondary` / `editorial` / `academic` (md. 26) |
| license | enum | `public` / `licensed` / `internal_only` / `unknown` (md. 32) |
| origin_url | text? | |
| status | enum | bkz. durum makinesi |
| created_at, updated_at | | |

### `ingest_job`, `ingest_file`, `extraction`
| tablo | alanlar |
|---|---|
| `ingest_job` | id, org_id, created_by, kind (`upload` / `crawl` / `bulk`), status, started_at, finished_at, stats jsonb |
| `ingest_file` | id, job_id, path, sha256, mime, detected_type, size, error? |
| `extraction` | id, file_id, source_id? (inceleme kuyruğu tipli kayıt oluşmadan kaynağı bulsun diye), parser_name, parser_version, extracted_at, fields jsonb, confidence jsonb, warnings jsonb, raw_text_ref |

`extraction.fields` parser'ın çıkardığı ham alanlar; onaydan sonra tipli tabloya kopyalanır. Böylece parser değişince yeniden çıkarma eski onayı bozmaz.

### `review`
| alan | not |
|---|---|
| id, extraction_id | |
| reviewer_id | kim |
| decision | `approve` / `edit` / `reject` |
| edits jsonb | düzeltilen alanlar (fark) |
| note | |
| reviewed_at | |

### `provenance` (her tipli kayıtta gömülü alanlar)
`source_id, extraction_id, review_id, recorded_at, superseded_at, recorded_by`

## 4. Durum makinesi

```
draft ──analiz──▶ analyzed ──onay──▶ approved ──yayın──▶ published ──▶ withdrawn
   │                 │                                        │
   └── failed        └── rejected                             └── superseded (yeni sürüm geldi)
```

- `draft`: dosya alındı, kuyrukta.
- `analyzed`: parser çalıştı, `extraction` var, inceleme bekliyor.
- `approved`: insan onayladı (düzeltmeler `review.edits`'te). Henüz aramada görünmez.
- `published`: tipli tabloya yazıldı, embedding + tsvector üretildi, atıf çözümlemeye açık.
- `superseded`: aynı kaynağın yeni sürümü yayınlandı; eski kayıt `superseded_at` ile kalır, tarih sorgularında hâlâ bulunur.
- `withdrawn`: hata/telif nedeniyle çekildi; aramada yok, loglarda var.

Toplu yüklemede (6.342 karar) onay tek tek olmaz: inceleme ekranı güven skoruna göre sıralar, yüksek güvenlileri toplu onaylama izni verir, düşük güvenlileri tek tek gösterir. Eşikler konfigüre edilir; ilk değer parser QA raporundan gelir.

## 5. Tipli tablolar

### 5.1 Mevzuat (A)

**`statute`**: id, source_id, number (4857), kind (`kanun` / `khk` / `yonetmelik` / `tuzuk` / `teblig`), short_name (İşK), full_title, rg_date, rg_number, repealed_at?

**`statute_article`**: id, statute_id, article_no (text: "18", "Ek 2", "Geçici 4"), ordinal (sıralama için)

**`statute_article_version`** (bitemporal çekirdek):

| alan | not |
|---|---|
| id | |
| article_id | |
| text | madde metni, o sürüm |
| heading | kenar başlığı |
| valid_from | yürürlük başlangıcı |
| valid_to | null = hâlâ yürürlükte; CHECK `valid_from < valid_to` (yarı açık aralık `[from, to)`) |
| amending_ref | değiştiren kanun/RG künyesi |
| change_kind | `original` / `amended` / `repealed` / `added` |
| provenance alanları | |

Enum etiketleri DB'de ASCII ve `snake_case` (`yonetmelik`, `genel_yazi`); Türkçe karşılığı yalnızca arayüzde gösterilir.

Sorgu: `4857 m.18, 2019-03-01` → `article_version WHERE valid_from <= date AND (valid_to IS NULL OR valid_to > date)`. Tek satır dönmeli; birden fazla dönerse veri hatası, QA'da yakalanır.

`Eskiler/` klasörü: aynı kanunun eski tam metinleri. Pipeline iki sürümü madde düzeyinde diff'ler, farklı maddeler için yeni `article_version` önerir; `valid_from` tarihi RG'den veya değişiklik kanunundan çıkarılır, bulunamazsa inceleme ekranında sorulur. **Burası Faz 1'in en zor işi**; önce 4857 ve 5510 ile başlanır.

### 5.2 Yargı kararları (C)

**`decision`**:

| alan | not |
|---|---|
| id, source_id | |
| court | enum: `aym` / `yargitay` / `danistay` / `bam` / `bim` / `ilk_derece` / `aihm` / `abad` / `foreign` / `uyusmazlik` (Uyuşmazlık Mahkemesi: adli/idari görev uyuşmazlığı, `jurisdiction` null, otorite sıralamasında ayrı) |
| court_level | enum: `aym` / `ibk` / `hgk_iddk` / `daire` / `bam_bim` / `ilk_derece` / `international` / `uyusmazlik` (md. 15-16 otorite sırası; Uyuşmazlık Mahkemesi sıranın dışında ayrı tutulur) |
| chamber | Parser'ın ürettiği biçimler: Yargıtay `n. HD` / `n. CD`, Danıştay ve BİM `n. D`, BAM `n. HD` (+ `bam_region`). NOT NULL DEFAULT `''` (HGK, İBK, AYM gibi dairesiz kararlar boş string; unique indeks NULL'larda çakışmayı kaçırmasın diye) |
| source_chamber | HGK esası `YYYY/D-N` yazılır; `D` (kararın geldiği daire) burada tutulur, `esas_no` karararama biçimi `YYYY/N` kalır. Uygulanmıyorsa `''`; NOT NULL DEFAULT `''` |
| bam_region | BAM / BİM bölgesi ("İstanbul", "Ankara"...). Diğer mahkemelerde `''`; NOT NULL DEFAULT `''`. İki bölgede aynı daire ve aynı E/K bulunabildiği için canlı kayıt unique indeksine girer: `(court, bam_region, chamber, esas_no, karar_no)` WHERE `superseded_at IS NULL` |
| decision_kind | AYM için: `norm_denetimi` / `iptal` / `bireysel_basvuru` / `red`; diğerleri: `karar` / `ibk` (md. 17) |
| esas_no, karar_no | "2017/16188" |
| decision_date | |
| event_date_hint | metinden çıkarılan olay tarihi (varsa; md. 4 için) |
| jurisdiction | `adli` / `idari` |
| related_articles | jsonb: `[{statute: 4857, articles: [18,19,20,21]}]` |
| keywords | text[] |
| outcome | ASCII snake_case etiketler (ASCII enum kuralı): `bozma`, `onama`, `duzelterek_onama`, `kabul`, `red`, `ihlal`, `ihlal_yok`. Serbest metin kalır; parser `kismen_bozma` üretmez, o yüzden listede yok. Parser şu an "düzelterek onama" yazar; `duzelterek_onama` normalizasyonu toplu yükleme görevinde yapılır |
| full_text | |
| editorial_summary | Çalışma ve Toplum ÖZETİ; ayrı lisans; **atıf kaynağı değil**; yalnızca arama sinyali olarak gömülür (§8) |
| text_completeness | `full` / `excerpt` / `summary_only` |
| verification | `unverified` / `verified_official` (karararama, E/K eşleşti) / `verified_uyap` / `mismatch` (bulundu ama alanlar farklı) / `not_in_source` (resmi kaynakta yok; 2009 öncesi tipik) |
| verification_source, verification_ref, verified_at | teyit kaynağı, kaynak id (karararama `getDokuman?id=`), zaman |
| journal_issue, journal_page | provenance ek |
| tsv (tsvector) | kayıt düzeyinde tam metin arama; vektör arama `chunk` tablosunda (§8) |

Parser'a özgü alanlar (`layout`, `journal_year`, `journal_no`, `missing`, `warnings`, `parser_version`, `sha256`, `source_path`) `decision` kolonu **değildir**; `extraction.fields` / `extraction.warnings` / `ingest_file` içinde yaşar, çünkü kararı değil çıkarma koşusunu tanımlarlar ve yeniden parse onaylı bir kaydı yeniden yazmamalıdır.

### 5.3 İdari düzenleme (D)

**`admin_act`**: id, source_id, issuer (`sgk` / `csgb` / `hazine` / ...), kind (`genelge` / `teblig` / `genel_yazi` / `gorus` / `talimat`), number ("2018/38"), subject

**`admin_act_version`**: id, act_id, text, valid_from, valid_to, superseded_by_ref, provenance. Genelgeler sık değişir ve birbirini açıkça yürürlükten kaldırır; `superseded_by_ref` zinciri burada tutulur.

### 5.4 Uluslararası (B), TİS (E), Doktrin (G), Hesap (H)

Faz 1'de şema tanımlanır, veri girmez (elde yok). Hepsi aynı kalıp: üst kayıt + `*_version` (bitemporal). `calc_parameter_version` örnek: `(param: asgari_ucret_brut, value, valid_from, valid_to, source_ref)`; hesap motoru parametreyi tarihle çeker.

## 6. Atıf çözümleme

`GET /citation/resolve?ref=<string>&date=<YYYY-MM-DD>`

1. `packages/citation` ref'i ayrıştırır: `"4857 S. İşK/18-21"`, `"4857 m.18"`, `"İşK 18"`, `"Yargıtay 9. HD 2017/16188 E., 2018/1234 K."`, `"AYM 2015/58 E."`, `"2018/38 sayılı Genelge"`.
2. Türüne göre tabloya gider; mevzuat için `date` ile sürüm seçer.
3. Döner: `{status: verified|not_in_kb|ambiguous, record_id, category, display, valid_from, valid_to, url}`. `not_in_kb` için resmi kaynaklarda arama ve `external` / `not_found` ayrımı atıf kapısında yapılır (`architecture.md` §5.1).
4. `ambiguous` (birden fazla eşleşme) inceleme kuyruğuna düşer; veri hatası sinyali.

Parser'ın karar metinlerinden çıkardığı `related_articles` da aynı çözümleyiciden geçer; çözümlenemeyen referanslar QA raporunda listelenir.

## 7. Arama

`GET /kb/search?q=…&category=C&court_level=…&date_from=…&as_of=…`

- Hibrit: tsvector (Türkçe config + unaccent) + pgvector; RRF ile birleştirme.
- `as_of` verilirse bitemporal filtre (o tarihte geçerli olan sürümler).
- Kategori zorunlu değil ama sonuçlar kategori etiketli döner; agent her adımda kendi kategorisini ister (adım 8 mevzuat, adım 17 AYM, adım 20 daire...).
- Sıralamada `court_level` ve `source_rank` ağırlık (md. 18, 26).

## 8. Embedding

Kayıt başına tek embedding yetmez: uzun kararlarda birden fazla konu tek vektörde ortalanır, modelin token sınırı aşılır ve md. 20'nin istediği birebir alıntı için paragraf düzeyinde konum gerekir. Vektör arama bu yüzden ayrı bir `chunk` tablosunda yapılır.

**`chunk`**:

| alan | not |
|---|---|
| id | |
| category | A..H; sonuçlar kategori etiketli döner (md. 28) |
| parent_kind, parent_id | ebeveyn kayıt (`decision`, `statute_article`, `admin_act`...) |
| version_id | sürümlü kayıtlarda ilgili `*_version`; `as_of` filtresi chunk düzeyinde çalışır |
| kind | `body` / `editorial_summary` |
| license | ebeveynden kopya; `internal_only` chunk metni kullanıcıya veya LLM'e gitmez |
| ordinal, char_start, char_end | ebeveyn metindeki konum; nokta atıf ve alıntı doğrulaması için |
| header | embedding'e giren künye: `Yargıtay 9. HD · 2018-03-12 · 4857/17,32 · Kıdem tazminatı`. Gösterilmez |
| text | |
| embedding (vector), embedding_model | model değişince yalnızca bu tablo yeniden üretilir |
| tsv (tsvector) | |

**Bölme kuralları:**

- **Mevzuat:** madde sürümü tek chunk; çok uzun maddeler fıkra bazlı. Yeni sürüm yeni chunk'lar üretir, eskiler sürümüne bağlı kalır.
- **Karar:** bölüm başlıkları varsa (yeni şablon `I. DAVA … V. GEREKÇE … VI. KARAR`) bölüm bazlı, uzun bölümler paragraf bazlı. Başlık yoksa paragraf veya ~300–500 token pencere, hafif örtüşmeli. ≤ ~500 kelimelik karar tek chunk. Not: arşivdeki 6.334 kararın yalnızca 431'inde `GEREKÇE` başlığı var (çoğu 76–90. sayılar); 2. düzende gövde `DAVA:` ile `SONUÇ:` arasında başlıksız akar. Arşiv boyutu: medyan 959, p90 2.400, maks. 14.902 kelime; toplam ~7,9 M kelime.
- **Genelge:** madde/bölüm bazlı.
- **Editoryal özet:** ayrı chunk, `kind = editorial_summary`, `license = internal_only`. Yalnızca arama sinyalidir: eşleşirse kayıt bulunur ama gösterilen ve LLM'e giden metin kararın kendi `body` chunk'larıdır. İzin gelirse `license` güncellenir, yeniden gömme gerekmez.

**Arama davranışı:**

- Arama chunk üzerinde yapılır, sonuç kayda göre gruplanır (kayıt skoru = en iyi chunk skoru); arama sonucu chunk değil kayıt döner, eşleşen chunk'lar konumlarıyla birlikte gelir.
- Model seçimi Faz 1 sonunda eval ile (çok dilli, Türkçe hukuk metni).

## 9. Memory servisiyle ilişki

`memory` aynı bitemporal kalıbı kullanır ama KB'den ayrı şemada: `(scope_type, scope_id, key, value jsonb, valid_from, valid_to, recorded_at, superseded_at, source)`. Hukuk dosyası bağlamı (statü, kritik tarihler, "işçi 30+ işyerinde çalışıyor" gibi doğrulanmış olgular) buraya yazılır; `agent` adım 3-6'da buradan okur. KB kurumsal ve paylaşımlı, memory org/kullanıcı/dosya özel. İkisi birbirine FK vermez.

Memory'deki `value` case anahtarıyla şifreli tutulur. `forget` ve case silme bitemporal geçmişi de kapsar ve crypto-shredding ile yapılır (`architecture.md` §6.1). KB'nin "silinmez" kuralı memory'ye uygulanmaz.

## 10. Faz 1 kapsamı (bu modelden)

1. Alembic: `source`, `ingest_*`, `extraction`, `review`, `statute*`, `decision`, `admin_act*`, `chunk`. Diğer kategoriler boş tablo olarak.
2. Parser: karar (4 düzen), kanun madde bölme, genelge. `.udf` ve e-imzalı PDF için çıkarma stratejisi ayrı iş.
3. 6.342 karar toplu yükleme + QA raporu + inceleme ekranı.
4. 4857 ve 5510 madde düzeyi, `Eskiler/` ile ilk sürüm denemesi.
5. `/citation/resolve` ve `/kb/search`.

## 11. Açık sorular

- ~~Karar `verification`: otomatik mümkün mü?~~ Evet, karararama için (PR #5). Açık: 2009 öncesi kararlar (`not_in_source`) kullanıcıya gösterilsin mi; BAM/AYM/Danıştay teyit kaynağı; toplu sorgu izni.
- `valid_from` çıkarımı başarısız olduğunda varsayılan davranış: inceleme ekranına düşsün (öneri) / RG tarihini kullan.
- Çalışma ve Toplum özetleri `internal_only` kalırsa inceleme ekranında gösterilsin mi? (Faydalı, ama kullanıcıya gitmemeli.)
- Çok kiracılı KB: org'a özel kaynak (kendi TİS'i) ortak KB'ye mi, org scope'una mı? Öneri: `source.org_id` nullable; null = ortak.
