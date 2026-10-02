# Veri Modeli v0.1

Durum: taslak, 2026-10-02. Bu doküman Faz 1'in temelidir; şema buradan Alembic'e çevrilir.

## 1. İlkeler

1. **Kaynak türleri ayrı** (md. 28). Sekiz kategori, her biri kendi tablosu ve alanlarıyla. Ortak bir `source` üst tablosu kimlik, provenance ve lisans tutar. "Document + chunk" tarzı tek genel tablo **yok**: atıf çözümleme için `4857 / madde 18 / 2019-03-01` gibi yapısal anahtar gerekir.
2. **Bitemporal.** Her yayınlanan kayıt iki zaman ekseninde yaşar:
   - `valid_from / valid_to`: hukuken geçerlilik (madde ne zaman yürürlükteydi, genelge ne zaman değişti). md. 4.
   - `recorded_at / superseded_at`: bizim sisteme ne zaman girdi, ne zaman yenisiyle değiştirildi. Denetlenebilirlik: "bu cevabı verdiğimizde KB'de ne vardı" sorusu cevaplanabilir (md. 35).
   Kayıt silinmez, `superseded_at` doldurulur.
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
| category | enum A..H | |
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
| `extraction` | id, file_id, parser_name, parser_version, extracted_at, fields jsonb, confidence jsonb, warnings jsonb, raw_text_ref |

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

**`statute`**: id, source_id, number (4857), kind (`kanun` / `khk` / `yönetmelik` / `tüzük` / `tebliğ`), short_name (İşK), full_title, rg_date, rg_number, repealed_at?

**`statute_article`**: id, statute_id, article_no (text: "18", "Ek 2", "Geçici 4"), ordinal (sıralama için)

**`statute_article_version`** (bitemporal çekirdek):

| alan | not |
|---|---|
| id | |
| article_id | |
| text | madde metni, o sürüm |
| heading | kenar başlığı |
| valid_from | yürürlük başlangıcı |
| valid_to | null = hâlâ yürürlükte |
| amending_ref | değiştiren kanun/RG künyesi |
| change_kind | `original` / `amended` / `repealed` / `added` |
| provenance alanları | |

Sorgu: `4857 m.18, 2019-03-01` → `article_version WHERE valid_from <= date AND (valid_to IS NULL OR valid_to > date)`. Tek satır dönmeli; birden fazla dönerse veri hatası, QA'da yakalanır.

`Eskiler/` klasörü: aynı kanunun eski tam metinleri. Pipeline iki sürümü madde düzeyinde diff'ler, farklı maddeler için yeni `article_version` önerir; `valid_from` tarihi RG'den veya değişiklik kanunundan çıkarılır, bulunamazsa inceleme ekranında sorulur. **Burası Faz 1'in en zor işi**; önce 4857 ve 5510 ile başlanır.

### 5.2 Yargı kararları (C)

**`decision`**:

| alan | not |
|---|---|
| id, source_id | |
| court | enum: `aym` / `yargitay` / `danistay` / `bam` / `bim` / `ilk_derece` / `aihm` / `abad` / `foreign` |
| court_level | enum: `aym` / `ibk` / `hgk_iddk` / `daire` / `bam_bim` / `ilk_derece` / `international` (md. 15-16 otorite sırası) |
| chamber | "9. HD", "10. HD", "İDDK" |
| decision_kind | AYM için: `norm_denetimi` / `iptal` / `bireysel_basvuru` / `red`; diğerleri: `karar` / `ibk` (md. 17) |
| esas_no, karar_no | "2017/16188" |
| decision_date | |
| event_date_hint | metinden çıkarılan olay tarihi (varsa; md. 4 için) |
| jurisdiction | `adli` / `idari` |
| related_articles | jsonb: `[{statute: 4857, articles: [18,19,20,21]}]` |
| keywords | text[] |
| outcome | `onama` / `bozma` / `kabul` / `red` / ... |
| full_text | |
| editorial_summary | Çalışma ve Toplum ÖZETİ; ayrı lisans; **atıf kaynağı değil** |
| text_completeness | `full` / `excerpt` / `summary_only` |
| verification | `unverified` / `verified_uyap` / `verified_official` / `mismatch` |
| journal_issue, journal_page | provenance ek |
| embedding (vector), tsv (tsvector) | arama |

### 5.3 İdari düzenleme (D)

**`admin_act`**: id, source_id, issuer (`sgk` / `csgb` / `hazine` / ...), kind (`genelge` / `tebliğ` / `genel_yazı` / `görüş` / `talimat`), number ("2018/38"), subject

**`admin_act_version`**: id, act_id, text, valid_from, valid_to, superseded_by_ref, provenance. Genelgeler sık değişir ve birbirini açıkça yürürlükten kaldırır; `superseded_by_ref` zinciri burada tutulur.

### 5.4 Uluslararası (B), TİS (E), Doktrin (G), Hesap (H)

Faz 1'de şema tanımlanır, veri girmez (elde yok). Hepsi aynı kalıp: üst kayıt + `*_version` (bitemporal). `calc_parameter_version` örnek: `(param: asgari_ucret_brut, value, valid_from, valid_to, source_ref)`; hesap motoru parametreyi tarihle çeker.

## 6. Atıf çözümleme

`GET /citation/resolve?ref=<string>&date=<YYYY-MM-DD>`

1. `packages/citation` ref'i ayrıştırır: `"4857 S. İşK/18-21"`, `"4857 m.18"`, `"İşK 18"`, `"Yargıtay 9. HD 2017/16188 E., 2018/1234 K."`, `"AYM 2015/58 E."`, `"2018/38 sayılı Genelge"`.
2. Türüne göre tabloya gider; mevzuat için `date` ile sürüm seçer.
3. Döner: `{status: verified|unverified|ambiguous, record_id, category, display, valid_from, valid_to, url}`.
4. `ambiguous` (birden fazla eşleşme) inceleme kuyruğuna düşer; veri hatası sinyali.

Parser'ın karar metinlerinden çıkardığı `related_articles` da aynı çözümleyiciden geçer; çözümlenemeyen referanslar QA raporunda listelenir.

## 7. Arama

`GET /kb/search?q=…&category=C&court_level=…&date_from=…&as_of=…`

- Hibrit: tsvector (Türkçe config + unaccent) + pgvector; RRF ile birleştirme.
- `as_of` verilirse bitemporal filtre (o tarihte geçerli olan sürümler).
- Kategori zorunlu değil ama sonuçlar kategori etiketli döner; agent her adımda kendi kategorisini ister (adım 8 mevzuat, adım 17 AYM, adım 20 daire...).
- Sıralamada `court_level` ve `source_rank` ağırlık (md. 18, 26).

## 8. Embedding

- Chunk'lama kayıt türüne göre: madde sürümü tek chunk; karar `GEREKÇE` bölümü paragraf bazlı; genelge madde bazlı.
- Her chunk ebeveyn kaydını ve sürümünü bilir; arama sonucu chunk değil kayıt döner.
- Model seçimi Faz 1 sonunda eval ile (çok dilli, Türkçe hukuk metni). Boyut ve model adı `embedding_model` alanında, model değişince yeniden üretim job'ı.

## 9. Memory servisiyle ilişki

`memory` aynı bitemporal kalıbı kullanır ama KB'den ayrı şemada: `(scope_type, scope_id, key, value jsonb, valid_from, valid_to, recorded_at, superseded_at, source)`. Hukuk dosyası bağlamı (statü, kritik tarihler, "işçi 30+ işyerinde çalışıyor" gibi doğrulanmış olgular) buraya yazılır; `agent` adım 3-6'da buradan okur. KB kurumsal ve paylaşımlı, memory org/kullanıcı/dosya özel. İkisi birbirine FK vermez.

## 10. Faz 1 kapsamı (bu modelden)

1. Alembic: `source`, `ingest_*`, `extraction`, `review`, `statute*`, `decision`, `admin_act*`. Diğer kategoriler boş tablo olarak.
2. Parser: karar (4 düzen), kanun madde bölme, genelge. `.udf` ve e-imzalı PDF için çıkarma stratejisi ayrı iş.
3. 6.342 karar toplu yükleme + QA raporu + inceleme ekranı.
4. 4857 ve 5510 madde düzeyi, `Eskiler/` ile ilk sürüm denemesi.
5. `/citation/resolve` ve `/kb/search`.

## 11. Açık sorular

- Karar `verification`: UYAP Emsal'e otomatik doğrulama mümkün mü, yoksa manuel mi? (Baran)
- `valid_from` çıkarımı başarısız olduğunda varsayılan davranış: inceleme ekranına düşsün (öneri) / RG tarihini kullan.
- Çalışma ve Toplum özetleri `internal_only` kalırsa inceleme ekranında gösterilsin mi? (Faydalı, ama kullanıcıya gitmemeli.)
- Çok kiracılı KB: org'a özel kaynak (kendi TİS'i) ortak KB'ye mi, org scope'una mı? Öneri: `source.org_id` nullable; null = ortak.
