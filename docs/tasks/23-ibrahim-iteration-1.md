# Görev 23: İbrahim test hesabı döngüsü, iterasyon 1

Durum: spec (2026-11-28). Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: issue #125 (bu görev), #121 (5510 m.102 low bant), #122 (yükleyici arama chunk'ları), `docs/tasks/11-statute-versioning.md` (kanun yükleyicisi), `docs/tasks/19-grounded-answer.md` (eval seti, `missing_in_kb`), `docs/tasks/20-journal-scan.md` (format), `docs/decisions.md` (2026-11-28 kaydı).
Skill'ler: `task-pr-hygiene`.

## Sorun

İbrahim'in test hesabı bizim için gerçek kullanıcı testidir (Orhan, 2026-11-28). İlk gün iki soru soruldu (10:51-11:03, 2 sohbet); ikisi de "doğrulanmış kaynakla cevap verilemedi" ya da yarım cevapla bitti.

- **Kök neden (belge indeksi):** canlı KB'de yalnız 5510 ve 4857 var, hiçbir genelge yok. SGK Genelgesi 2018/38, 2020/8 ve 1475 m.14 Drive'da duruyor, parser'lar bunları tanıyor, ama canlıya hiç yüklenmemiş.
- **Soru yakalama (ayrı konu):** işe giriş tarihi olay tarihi sanıldı; "soruyu tekrar düzgün algıla" sonrası konu ölüm toptan ödemesine kaydı, verilen olgular kayboldu ve aynı soru 3 kez soruldu; net maddeli soruda gereksiz ek soru soruldu.

## Döngü

soru (İbrahim) → inceleme (Themis hesabın geçmişini okur: cevaplar + geri bildirimler) → eksikler issue → uygulama + review + canlıya alma → **aynı sorularla canlıda yeniden test** (aynı olgular, aynı netleştirme cevapları) → sonuç WP grubuna. Her iterasyon bir issue'dur; hesaptan gelen sorular eval vakası olur (`eval/cases/IB-*.yaml`).

## Hedef

Döngünün ilk iterasyonunu kapatmak: İbrahim'in iki sorusunda eksik olan kaynakları canlı KB'ye koymak ve soruları eval vakası olarak repoya almak.

## Kapsam

1. **Üç belgeyi mevcut yükleyicilerle, kod değiştirmeden, `analyzed` (onay bekliyor) olarak yükle.** Arama chunk'ları aynı transaction'da kurulur (#122).
   - SGK Genelgesi 2018/38 (Emeklilik İşlemleri) ve 2020/8 (İdari Para Cezaları): `app.loaders.admin_acts`.
   - 1475 m.14 (mülga İş K., kıdem tazminatı): `app.loaders.statutes`, `statutes.jsonl`'dan **yalnız 1475 kaydı**. 6356 / 7036 yüklenmez (Orhan kararı bekliyor); 4857 / 5510 yeniden yüklenmez.
   - Kuru koşu (2026-11-28, main 4de4a0a, veritabanına yazmadan):

     | Belge | Birim | Bant |
     |---|---|---|
     | 2018/38 | 686 bölüm | high 551, medium 134, low 1; ek sayfaları 373 ve 511 bölünmedi |
     | 2020/8 | 177 bölüm | high 175, medium 2 |
     | 1475 m.14 | 1 madde | medium |
2. **Yükleme adımları:** (a) kuru koşu, çıktı yukarıdaki sayılarla karşılaştırılır; (b) yükleme; (c) aynı komutlar ikinci kez: 0 yeni kayıt; (d) canlıda aynı sorularla yeniden test. Yükleme canlıda Orhan'ın onayıyla yapılır (bu PR'da yükleme yok).
3. **İki eval vakası** (`eval/cases/IB-001.yaml`, `IB-002.yaml`), İbrahim'in sorularının olduğu gibi (yazım hatalarıyla) metni. Beklentinin tek kaynağı İbrahim'in geri bildirimi ve kaynak metnidir; hukuki beklenti İbrahim onayına tabidir:
   - **IB-001** (emeklilik, 4/c): konu yaşlılık aylığı hak kazanma koşulları; "Kuruma başvuru ya da emekliye sevk" koşulu ve hak sahipleri çerçevesi `must_not` (dar ifadeler: scorer olumsuzlamayı ayırmaz; konu kayması `expected.topic` ile ölçülür). Sorunun verdiği olgular (ilk sigortalılık tarihi 01.02.2008, statü, 4/a gün sayısı) sorulmaz: `must_ask` boş, olgular `facts`'te. Scorer "sorulmamalı"yı ölçmez; yalnız `must_ask` boşluğu ve yorum.
   - **IB-002** (işyeri bildirgesi cezası): `must_ask` boş; `must_cite` 5510 m.102, 2020/8 m.2.5, 5510 m.11; m.102 `missing_in_kb`: m.102 low bantta olduğundan (#121) vaka, m.102 okunana kadar `definite` verilemeyen SB-014 ile aynı durumda.
   - `eval/tests/test_score.py` vaka sayısı 20'den 22'ye çıkar (id kuralı: id dosya adıyla aynı, her `*.yaml` yüklenir; `IB-*` kabul edilir).
4. **Karar kaydı:** `docs/decisions.md` 2026-11-28 girdisi.

## Kapsam dışı

- 5510 m.102 low bant: #121 (ceza sorusu bu iterasyonda yarım çözülebilir).
- Soru yakalama ve olgu kaybı (olay tarihi karışıklığı, konu kayması, tekrarlanan soru, net soruda gereksiz soru): #127 (şablon: işyeri bildirgesi (b bendi) `fiil` seçeneği + açık soruda soru sorma).
- 6356 ve 7036 (parser hazır): Orhan kararı bekliyor.
- Kalan 44 genelge dosyası ve diğer kanunlar: parser kapsamına alınması ayrı iş.
- Yükleyici, parser ve konu şablonu kod değişikliği.

## Kabul kriterleri

- `cd eval && pytest tests` (veya `make test`) yeşil, 22 vaka yüklenir; `make lint` yeşil.
- Canlıda kuru koşu çıktısı yukarıdaki tabloyla aynı; yükleme sonrası üç belge yönetim ekranında `analyzed` olarak görünür; ikinci yükleme 0 yeni kayıt, 0 yeni chunk.
- Arama: "işyeri bildirgesi" (2020/8 m.2.5) ve "yaşlılık aylığı şartları" (2018/38 K2-B3-2.1.2.1) sorguları chunk döndürür.
- İki soru canlıda aynı olgularla yeniden soruldu; 2018/38 ve 2020/8 cevapta okunan kaynak olarak görünür; önce/sonra raporu issue #125'e ve WP grubuna yazıldı; kalan açıklar issue olarak açıldı.

## Notlar Claude Code için

- Genelge ve kanun yükleyicileri değişmez; bir hata çıkarsa düzeltme ayrı issue / PR.
- `IB-*` vakalarına İbrahim onayı gelmeden hukuki sonuç traps'a yazılmaz; emin olunmayan nokta `# İbrahim'e sorulacak:` yorumudur.
