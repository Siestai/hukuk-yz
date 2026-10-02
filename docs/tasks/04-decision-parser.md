# Görev 04: Karar parser'ı (Çalışma ve Toplum arşivi)

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `AGENTS.md` (Decision archive findings, Planned pipeline), `docs/data-model.md` §5.2 (`decision`), `docs/spike-karararama-2026-10-02.md` (Parser için çıkan dersler), `docs/tasks/03-ingest.md`.
Üstüne oturduğu iş: Görev 03 (`packages/ingest`, `data/extracted/` önbelleği, `files.jsonl`).

## Hedef

Görev 03'ün çıkardığı 6.334 karar metninden (`detected_type=pdf`, `status=ok`, `Yargi_Kararlari_Arsivi/`) `decision` kaydına karşılık gelen alanları **deterministik** çıkaran bir parser ve bunu tüm arşive koşan bir CLI. Çıktı: karar başına bir JSONL satırı + alan doluluk / QA raporu. DB'ye yazma ve resmi kaynaktan teyit bu görevde yok; ikisi de bu çıktının üstüne oturacak (Görev 05: karararama teyidi).

LLM kullanılmaz. Regex + layout kuralları; çıkarılamayan alan boş kalır ve sebebiyle raporlanır, tahmin edilmez (md. 25).

## Girdi

- `hukuk-ingest scan` raporu (`files.jsonl`) + önbellek (`data/extracted/<sha[:2]>/<sha>.clean.txt`). Parser `.clean.txt`'i okur; `.raw.txt` yalnızca hata ayıklama için.
- Sayı numarası klasör adından: `Yargi_Kararlari_Arsivi/<N>.Sayı-Yargı Kararları (...)/<başlık>.pdf`. Dosya adı = derginin karar başlığı (anahtar kelime sinyali, kaynak değil).

## Kapsam

1. **Paket:** `packages/ingest` içinde yeni modül grubu `hukuk_ingest.decisions` (ayrı paket açılmaz; aynı pipeline). `services/app`'e bağımlılık yok.
2. **Dergiye özgü temizlik** (`decisions/clean.py`), Görev 03'ün `clean.py`'sinden ayrı:
   - Sayfa başlığı: `Yargıtay Kararları` ve `Yargıtay Kararları – Çalışma ve Toplum, YYYY/N` (76-90 ve 43. sayıda da var). Başlıktaki `YYYY/N` provenance'a (`journal_year`, `journal_no`) alınır, sonra silinir.
   - Dergi sayfa numarası: başlığın hemen altındaki tek başına sayı satırı. İlk sayfanınki `journal_page` olur.
   - Madde imleri (⚫ • ▪, Görev 03 sonrası tek biçim), satır sonu tek kelimelik iki yana yaslama artıkları, `Î` gibi bilinen OCR diakritik hataları (liste sabit, gerekçeli).
   - Bitişik yazılmış kelimeler (`uygulanmayadevamedileceği`) **düzeltilmez**; tam metin kaynağa sadık kalır.
3. **Layout tespiti** (`decisions/layout.py`): dosya başına bir `layout` değeri, sayı numarasına göre değil **metindeki işaretlere** göre (sayı aralıkları yalnızca beklenti/QA için):
   - `era1_summary_first` (~1-15): `İlgili Kanun/md:` → `ÖZÜ` → mahkeme + `ESAS NO:/KARAR NO:/TARİHİ:` **özetten sonra**. (3. sayı örneğinde E/K başta; tespit işarete bakmalı.)
   - `era2_classic` (~16-75): İlgili Kanun → `T.C.` → `YARGITAY` → `n. HUKUK DAİRESİ` → Esas/Karar/Tarihi → başlık/anahtar kelimeler → `ÖZETİ` → `DAVA:` … `SONUÇ:`.
   - `era3_two_column` (40'lı sayılar): etiketler (`Esas No.`, `Karar No.`, `Tarihi:`) art arda, değerler ayrı satırlarda aynı sırayla.
   - `era4_new_template` (~76-90): dergi başlığı + yeni Yargıtay şablonu `I. DAVA` … `V. GEREKÇE` … `VI. KARAR`.
   - `unknown`: hiçbiri tutmazsa; alanlar yine denenir, rapora düşer.
4. **Alan çıkarma** (`decisions/fields.py`), `data-model.md` §5.2 adlarıyla:
   - `court`, `court_level`, `jurisdiction`: **künye bloğundan** (`T.C.` + mahkeme adı + E/K/Tarih satırlarının oluşturduğu blok; era1'de bu blok özetten sonra gelir, diğerlerinde özetten önce), serbest gövdeden değil. Gövdedeki "Yargıtay 10. Hukuk Dairesince" atıfları mahkeme sayılmaz. `T.C. / X BÖLGE ADLİYE MAHKEMESİ` → `bam`; `HUKUK GENEL KURULU` → `yargitay`/`hgk_iddk`; `İÇTİHADI BİRLEŞTİRME` → `ibk`; `ANAYASA MAHKEMESİ` → `aym` (+ `decision_kind` bireysel başvuru / norm denetimi metinden); AİHM, ABAD, Alman Federal → `aihm` / `abad` / `foreign`; Danıştay → `danistay`, `jurisdiction=idari`.
   - `chamber`: kanonik biçim `"9. HD"`, `"10. HD"`; ceza daireleri `"n. CD"`. Dairesizse `''` (şema varsayılanı). BAM için `"n. HD"` + `bam_region` (ör. "İstanbul") ayrı alan.
   - `esas_no`, `karar_no`: `YYYY/N`. HGK `YYYY/D-N` → `esas_no = YYYY/N`, `source_chamber = D` (karararama biçimi; spike dersi 1). Tek haneli/boşluklu yazımlar (`2010 / 37635`, `Esas No.`, `ESAS NO:`) aynı sonuca normalize olur.
   - `decision_date`: ISO `YYYY-MM-DD`; `07.06.2004`, `7.6.2004`, `07/06/2004` ve ay adlı yazımlar (`7 Haziran 2004`). Geçersiz tarih (ör. 31.02) → boş + `invalid_date` uyarısı.
   - `related_articles`: `İlgili Kanun / Madde` bloğu → `[{statute: 4857, label: "İşK", articles: ["18","19","20","21"]}]`. Aralık (`18-21`) açılır; virgüllü liste; `4/1-c`, `Geçici 4`, `Ek 2` gibi alt bentler **string** olarak korunur (int'e zorlanmaz). Kanun no'suz kısaltma (`İşK`, `SGK`, `STK`, `Bağ-Kur K`) için sabit eşleme tablosu (`4857`, `5510`, `6356`, `1479`, `506`, `1475`, `2822`, `6331`, `4447`, ...); eşlenemeyen etiket ham haliyle `statute=null` + uyarı. Ham etiket (`raw`) her zaman saklanır. **Tarihe bağlı kısaltmalar** (`BK` → 818 / 6098, 01.07.2012; `HUMK` / `HMK` → 1086 / 6100, 01.10.2011; `İşK` numarasız → 1475 / 4857, 10.06.2003) karar tarihine göre eşlenir ve `statute_inferred_from_date` uyarısı alır; karar tarihi yoksa `statute=null`. Örnek (1. sayı): `1475 s.İşK: 14`, `BK:90`.
   - `keywords`: başlık ile ÖZETİ arasındaki büyük harfli satırlar (madde imli ya da değil), satır kırılmaları birleştirilmiş.
   - `editorial_summary`: `ÖZÜ` / `ÖZETİ` sonrasından gövde başlangıcına (`DAVA:`, `I. DAVA`, `Taraflar arasındaki`, mahkeme bloğu) kadar. Data-model'e uygun olarak editoryal içerik, atıf kaynağı değil.
   - `full_text`: dergi gürültüsü temizlenmiş karar metni (başlık bloğu ve özet hariç gövde). `text_completeness`: gövde varsa `full`, yalnızca özet varsa `summary_only`, gövde kısa/kesikse `excerpt` (eşik gerekçeli).
   - `outcome`: son bölümden (`SONUÇ:`, `VI. KARAR`) `bozma` / `onama` / `düzelterek onama` / `kabul` / `red` / `ihlal` / `ihlal_yok`; bulunamazsa boş.
   - `verification = "unverified"` (sabit; teyit Görev 05).
   - Provenance: `journal_issue` (klasör), `journal_year`, `journal_no`, `journal_page`, `source_path`, `sha256`, `parser_version`, `layout`.
5. **Kalite / güven** (`decisions/qa.py`): her kayıtta `missing: [...]` ve `warnings: [...]` (ör. `court_from_body_only`, `multiple_esas_candidates`, `date_outside_issue_year`: karar tarihi dergi yılından >3 yıl önce/sonra, `statute_unmapped`, `layout_unknown`). Bir alan için birden fazla aday varsa ilk başlık adayı alınır, diğerleri uyarıya yazılır; sessizce seçilmez.
6. **CLI:** `uv run hukuk-ingest decisions parse --scan-report <files.jsonl> --text-cache data/extracted --out <dir> [--workers N] [--issue N]`.
   - `decisions.jsonl`: karar başına bir satır, yukarıdaki alanlar.
   - `summary.json` + `summary.md`: layout × sayı aralığı dağılımı; alan başına doluluk (genel + layout bazında); mahkeme dağılımı (`AGENTS.md` tablosuyla yan yana); en sık 20 uyarı; `layout=unknown` ve kritik alanı (court, esas_no, karar_no, decision_date) eksik dosya listesi; aynı (court, chamber, esas_no, karar_no) ile birden fazla dosya (mükerrer aday) listesi.
   - Hata koşuyu durdurmaz (`status=error` + istisna).
7. **Altın set** (`packages/ingest/tests/gold/decisions_gold.jsonl`): **yalnızca künye alanları** (sha256, court, court_level, chamber, esas_no, karar_no, decision_date, related_articles, layout); metin, özet, başlık yok (telif + KVKK). En az 60 karar: her layout'tan ≥10, HGK ≥5, BAM ≥5, AYM ≥3, İBK tümü (5), yabancı ≥3. Seçim script'i seed'li ve repoda; değerler Themis tarafından PDF'ten elle doğrulanır ve PR'da hangi kayıtların elle bakıldığı yazılır.
8. **Testler** (`packages/ingest/tests/`, modüle göre: `test_decisions_clean.py`, `test_decisions_layout.py`, `test_decisions_fields.py`, `test_decisions_cli.py`):
   - Sentetik metin fixture'ları (her layout için elle yazılmış, uydurma isim/E/K ile) test içinde; gerçek karar metni commit edilmez.
   - Normalizasyon birim testleri: E/K varyantları, HGK `D-N`, tarih varyantları, kanun/madde aralıkları ve alt bentler, chamber kanonikleştirme, gövdedeki daire atfının mahkeme sayılmaması, BAM başlığı.
   - Altın set testi: `data/extracted` yoksa **skip**; varsa altın set üzerinde alan bazında doğruluk ölçülür, eşik altı test kırılır.

## Kapsam dışı

- karararama / UYAP / AYM teyidi, ağ isteği (Görev 05).
- DB'ye yazma (`source`, `decision`, `extraction` satırları), worker job'u, API.
- `event_date_hint` (olay tarihi) çıkarımı: ayrı iş, md. 4 tasarımıyla birlikte.
- Mevzuat parser'ı ve madde sürümleme.
- 2 `.doc` ve 6 eksik karar (Görev 03'te `unsupported`/`rejected`).
- `docs/` değişikliği; `data-model.md` ile çelişki (ör. yeni alan `source_chamber`, `bam_region`, `layout`) PR açıklamasında listelenir, şema güncellemesi ayrı PR.

## Kabul kriterleri (Themis koşar)

- [ ] `make lint`, `make typecheck`, `make test` temiz; CI yeşil.
- [ ] Tam arşiv koşusu (6.334 karar) sunucuda hatasız (`status=error` = 0), 5 dakikanın altında; süre ve `summary.md` PR'da.
- [ ] **Altın set doğruluğu:** court, court_level, chamber, esas_no, karar_no, decision_date **%100**; related_articles ≥ %95; layout ≥ %95.
- [ ] **Doluluk** (AGENTS.md'deki keşif oranlarının altına düşmez): chamber ≥ %98 (dairesiz mahkemeler hariç), esas_no ≥ %95, karar_no ≥ %96, decision_date ≥ %95, related_articles ≥ %98, editorial_summary ≥ %99. Altında kalan her alan için eksik dosyalardan 10 örnek elle incelenip sebep PR'da.
- [ ] Mahkeme dağılımı `AGENTS.md` tablosuyla ±%2 içinde (BAM 297, HGK 154, İBK 5, AYM 51 civarı); fark varsa açıklanır.
- [ ] `layout=unknown` ≤ %1.
- [ ] Rastgele 10 kararda (her layout'tan en az 2) `full_text` ve `editorial_summary` elle okunur: sayfa başlığı/sayfa numarası kalmamış, özet gövdeye karışmamış.

## Notlar Claude Code için

- Python 3.12, `mypy --strict`, ruff. Yeni bağımlılık beklenmiyor (stdlib `re`, `unicodedata`); gerekirse gerekçesi PR'da.
- Kayıt modeli Pydantic v2 ya da `dataclass`; alan adları `data-model.md` §5.2 ile birebir, ek alanlar açıkça işaretli.
- Regex'leri modül seviyesinde derle, her desenin yanında hangi layout/örnek için olduğu kısa yorumla.
- Gerçek karar metnini, tarafların adlarını ya da dergi özetini test fixture'ı veya altın sete koyma.
- Testler modüle göre dosyalanır; süreç adlı test dosyası (`test_review_fixes.py` gibi) yok. Spec dışı ekleme, ölü kod yok.
- İngilizce kod/yorum/commit; mesaj: `feat(ingest): decision parser for the journal archive (task 04)`.
