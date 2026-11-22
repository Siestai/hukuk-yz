# Görev 19: Esaslı ve kaynaklı cevap + 20 vakalık eval

Durum: kapandı (Orhan, 2026-11-22; sonuç ve açık kalanlar `eval/results/2026-11-22-ozet.md`).
Önceki durum: onaylı (Orhan, 2026-11-22). Sahip: Claude Code (orkestratör + subagent'lar). Onay ve merge: Orhan.
Ön koşul: Paket A (handoff A1-A5) main'de, yerel KB dolu.
Handoff: `docs/handoff/2026-11-22-chat-fix/` (`00-README.md` K1, K2; `B-cases-new10.md`; bütçe tavanı 5 USD, tüm turlar).
Bağlam: `docs/tasks/17-agent-v1.md` (graf, kapı, eval koşucusu), `18-chat-wiring.md` (2026-11-09 kapsam daraltması),
`eval/cases/*.yaml` (mevcut 10 vaka), `services/agent/agent/topics/*.yaml`, `B-cases-new10.md`, `00-README.md` (K1, K2).
Skill'ler: `task-pr-hygiene`.

## Hedef

20 eval vakasında ajan, okuduğu kaynaklara dayanan esaslı cevap versin: doğru netleştirme, doğru künye, desteklenen
başlık ve alıntı, doğru kip. Kaynak gerçekten yoksa dürüst "kaynak yetersiz" kalır (md.25), ama hangi kaynağın
eksik olduğunu söyler.

## Bilinen açıklar (Görev 17-18 gerçek koşularından)

- Konu şablonu eksik: SB-003, 005, 006, 013 ve yeni vakaların çoğu "genel" şablona düşüyor (yalnız olay tarihi + statü sorulur).
- Başlık (headline) okunan kaynakla desteklenmiyor; yanıltıcı başlık görüldü (SB-001).
- Kritik bilinmeyen olgu varken bazı koşullu dallar eksik kaldı (6 kritik olgudan 4'ü kapsandı).
- Kip onarımı: model "-iyor"dan düzeltme talimatına uymadan dönebiliyor; ikinci taslak da kapıda düşüyor.
- Taslakta şablon dışı, uydurma olgu anahtarı (`bildirim_tarihi` yerine başka anahtar).
- Holding satırında `fact_value` "bilinmiyor" olunca kip kapısı satırı reddediyor; doğru davranış koşullu dal.
- Alıntı (`condition_quote`) iddiayı desteklemiyor ama metinde geçtiği için geçiyor (birebir geçmek yetmiyor).

## Alt görevler

| # | Alt görev | Subagent | Bağımlılık | Paralel |
|---|---|---|---|---|
| B1 | 20 vaka: analiz ve vaka dosyaları | legal-case-analyst (vaka başına bir çağrı, 4-5 paralel) | - (A ile paralel) | evet |
| B2 | Yeni konu şablonları | legal-case-analyst (taslak) + implementer (şema/test) | B1 | şablon başına paralel |
| B3 | Kapı ve taslak düzeltmeleri | implementer | A | B2 ile |
| B4 | "Kaynak yetersiz" cevabının içeriği | implementer | A | B2, B3 ile (ayrı dosyalar) |
| B5 | Eval koşucusu ve kabul tablosu | implementer + eval-runner | B1-B4 | - |
| B6 | Tur döngüsü: başarısız vaka → kök neden → düzeltme | orkestratör | B5 | - |

### B1: 20 vaka

- Mevcut 10: SB-001, 003, 005, 006, 008, 013, 016, 021, 024, 026 (`eval/cases/` var; yeniden gözden geçir, değiştirme gerekirse gerekçe yaz).
- Yeni 10: `B-cases-new10.md` (SB-002, 010, 012, 014, 019, 027, 032, 035, 039, 042). Her biri için `eval/cases/SB-NNN.yaml`,
  mevcut şema: `question`, gerekiyorsa `facts`, `expected.status`, `headline_contains`, `must_cite`, `must_ask`, `must_not`, `traps`, `tags`.
- Analist kuralları:
  - Her `must_cite` künyesi KB'de var olan ya da Paket A'da yüklenen bir kaynağa denk gelmeli; olmayan künye için
    vaka dosyasında `missing_in_kb:` listesi (eval bunu "kaynak eksik" diye ayrı sayar, ajan hatası saymaz).
  - Yargıtay kararı künyesi yalnız arşivde ve mümkünse karararama'da E/K ile teyitliyse yazılır; teyitsiz künye yazılmaz.
  - `must_ask` anahtarları konu şablonundaki olgu anahtarlarıyla aynı ad (şablon yoksa B2'de oluşur).
  - Çok soruluk vakalar daraltılır (B-cases-new10.md'de hangisinin daraltılacağı yazılı); daraltma gerekçesi yorum satırında.
  - Repo public: kişi adı, "uzman X dedi" yok; uzman düzeltmeleri `traps` satırı olarak, kurumsal dille.
- Çıktı ayrıca: 20 vakanın konu → şablon eşleme tablosu (PR açıklamasında).

### B2: Yeni konu şablonları

En az (B1 tablosuna göre artabilir):
- `calisma_kosulu_degisikligi` (4857 m.22: ücret düşürme, çalışma saati kaydırma; SB-003, SB-013)
- `tis_sendikal` (6356: TİS alacağı, dayanışma aidatı; SB-005, SB-039)
- `grev_lokavt` (6356 m.58 vd.; SB-006)
- `sgk_bildirim_prim` (5510 m.8, eksik gün, PEK; SB-012, SB-010, SB-024'ün şablonu kontrol edilir)
- `olum_yaslilik_aylik` (5510 m.34, 37; 2018/38; SB-002, SB-042)
- `hakli_fesih_devamsizlik` (4857 m.24, 25, 26; SB-027, SB-035)
Mevcut `idari_para_cezasi` şablonu SB-014, SB-019, SB-021 için alt bent düzeyinde genişler (m.102/1-a, 1-e-5, 1-m-4-ç).

Her şablon: olgular, seçenekler, "neden soruyorum" metni + dayanak künyesi (mevcut biçim), `must_read`.
Kural: "neden soruyorum" metni ve seçenekler yalnız okunabilen kaynaktan; künyesiz cümle yok. Şablon dışı soru üretilmez (Görev 17).
Konu sınıflandırma testi: 20 vakanın her biri beklenen şablona düşer (sahte LLM ile değil, gerçek sınıflandırıcı mantığıyla; LLM ise kaydedilmiş yanıtla).

Uygulama notu (koşullu soru): kritik olgu `asked_when: {<olgu>: [<seçenek değeri> | unknown, ...]}` ile bir dala bağlanır; olgu yalnız adı geçen olgular listedeki durumdaysa sorulur ve yalnız o zaman kapıda kritik sayılır (`facts.critical_unknown`, saf kod). Dal olgusu ya hiç sorulmaz (yalnız `options`, giriş adımı seçer; koşulu `unknown` içermek zorundadır, dal bilinmiyorsa iki dalın olguları da sorulur) ya da kritik bir sorudur (seçeneği dalı açar). Cevap bir dal açarsa o dalın olguları tek bir ek netleştirmede sorulur; ek turun cevabı yeni tur açmaz. Seçeneklere uymayan olgu değeri (dal olgusu olsun olmasın, seçenekli her olguda) bilinmiyor sayılır; olgu kritikse sorulur. Doğrulayıcı geçersiz anahtar/değeri ve sessiz düşebilecek koşulu reddeder.

### B3: Kapı ve taslak düzeltmeleri

- **Başlık desteği:** başlık, en az bir holding satırının `result`'ına ve okunan kaynağa bağlanır; bağlanamayan başlık kapıda düşer.
- **Alıntı desteği:** `condition_quote` metinde geçmenin ötesinde, satırın `condition`'ını destekleyen fıkra / bent içinden olmalı
  (atıf verilen fıkra ile alıntının fıkrası aynı). Dar ve deterministik kural; LLM yargıcı bu pakette yok.
- **Bilinmeyen olgu:** `fact_value` bilinmiyorsa satır reddedilmez, koşullu dala gider; her kritik bilinmeyen olgu için en az bir koşullu dal (test).
- **Olgu anahtarı:** taslakta şablonda olmayan anahtar kapıda düşer ve bir kez düzelttirilir; ikinci kez de olursa o satır atılır.
- **Kip:** "-iyor" taraması aynen; düzeltme turunda talimat ve hatalı cümleler modele açıkça verilir; ikinci başarısızlıkta
  yalnız hatalı cümleler düşer, tüm cevap düşmez (cevap anlamını kaybediyorsa kaynak-yetersiz yolu).
- **K1:** onaysız kaynağa dayanan nokta işaretli (A4 alanı); tamamı onaysız kaynağa dayanan cevapta `status_note` bunu söyler.
- Her kural için RED → GREEN regresyon testi; Görev 17 gerçek koşularındaki hatalı taslaklar (varsa kayıtlı çıktılar) fixture olur.

### B4: "Kaynak yetersiz" cevabının içeriği

- Dürüst fallback cevabı boş kalmaz: hangi konu, hangi `must_read` künyeleri okunamadı (A4 `missing_source`), kullanıcının
  verdiği olgular, kullanıcıya bir sonraki adım ("soru şu kaynaklar eklenince cevaplanabilir").
- Sözleşmede (Turn / Answer) alanlar; UI'da asgari metin (mevcut bileşende tek satır liste; tasarım sonraki iş).
- Hata turunda da geri bildirim verilebilsin (geri bildirim şu an yalnız cevaplı turda): API ve UI.

### B5: Eval koşucusu ve kabul tablosu

- `python -m agent.eval eval/cases` 20 vakayı koşar; tablo: vaka, şablon, must_ask kapsama, must_cite kapsama,
  must_not ihlali, başlık eşleşmesi, kip ihlali, kapı düşüşleri, `missing_in_kb`, token, maliyet, süre.
- Bütçe kapısı: koşu öncesi tahmin, sert tavan (00-README), her çağrı sonrası toplam; tavanda durur.
- Sonuçlar `eval/results/<tarih>-<tag>.json` + md tablo (gitignore değil: küçük, kişisel veri yok).

### B6: Tur döngüsü

Her tur: eval-runner koşar → orkestratör başarısız vakaları kök nedene göre gruplar (şablon / kaynak eksik / kapı / model) →
grup başına bir implementer düzeltmesi → reviewer → yeniden eval. En fazla 3 tur; 3. turdan sonra kalan başarısızlıklar
açıkça raporlanır, kapı gevşetilerek "geçirme" yapılmaz.

## Kapsam dışı

- Hesap motoru (SB-010, SB-019 gibi tutar hesapları: yalnız "hangi bilgi gerekli" ve kuralın metni; sayı LLM'den gelmez, md.29).
- LLM yargıç / çürütücü ikinci geçiş, memory, uzmana eskalasyon.
- UI tasarımı, marka, canlı deploy (merge sonrası autodeploy; canlı doğrulamayı Themis yapar).

## Kabul kriterleri

- [ ] `ruff`, `mypy`, `pytest`, web lint/typecheck/test yeşil.
- [ ] 20 vaka dosyası; her birinde `must_cite` ya KB'de var ya `missing_in_kb`'de.
- [ ] 20 vakanın hepsi beklenen şablona düşer (test).
- [ ] B3'teki her kural için regresyon testi.
- [ ] Son eval turu (gerçek LLM, yerel KB): **eşik** (Orhan onayı; öneri):
  - must_ask kapsama ortalaması ≥ %80, hiçbir vakada < %50,
  - `missing_in_kb` dışı must_cite kapsama ortalaması ≥ %70,
  - must_not ihlali 0, kip ihlali 0, okunmamış kaynağa atıf 0 (md.25),
  - en az 12/20 vakada esaslı cevap (kaynak-yetersiz değil).
- [ ] PR'da: tur tablosu (tur başına), toplam maliyet, kalan başarısızlıkların kök nedeni.
