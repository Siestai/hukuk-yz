# Görev 04b: karar gövdesinin başlangıcı bulunamayan kararlar ("Yalnız özet" yanlış etiketi)

Durum: uygulandı, PR bekliyor (Themis, 2026-10-26).
Sahip: Themis (uygulayan Claude Code).
Onay: Orhan (2026-10-26, WhatsApp grubu: "Tamam onaylıyorum. Normal implementation cycle kullanarak bitir, review et ve main e merge edebilirsin"). Bu onay görev dosyasını ve uygulamayı birlikte kapsar; ikisi aynı PR'da.
Bağlam: `docs/tasks/04-decision-parser.md`, `docs/tasks/05-decision-load.md` (idempotency: sha256 + parser adı + parser sürümü), `packages/ingest/hukuk_ingest/decisions/fields.py` (`_BODY_RE`, `_FORMULA_RE`, `_body_start`, `extract_fields`), `packages/ingest/hukuk_ingest/decisions/parse.py` (`PARSER_VERSION`), `services/app/app/loaders/decisions.py`, `services/app/app/kb.py` (`queue`: kaynağın en yeni extraction'ı).
Skill'ler: `task-pr-hygiene`.

## Sorun

Canlı panelde 53 karar "Yalnız özet" (`text_completeness = summary_only`) etiketli ve `full_text`'i boş. Bu etiket güven kuralını (`text_summary_only`) tetikliyor, kararlar düşük banda düşüyor. Ortak (İbrahim, 2026-10-24) bunları "metni yok" diye görüyor.

Taramada (Themis, 2026-10-26) bu 53 kararın hepsinin çıkarılmış metni (`data/extracted/<sha[:2]>/<sha>.clean.txt`) var:
- **50'sinde tam karar metni var** (hüküm ve "oybirliğiyle karar verildi" cümlesi dahil). Parser gövdenin başladığı satırı bulamadığı için (`_body_start` → -1) metni kayda yazmıyor.
- **3'ü gerçekten yalnız özet ya da kısmi:** Yargıtay 9. HD E.2022/16503 K.2023/10180, Yargıtay 9. HD E.2008/5763 K.2009/18544, ilk derece E.2006/366 K.2007/268. Bunlar `summary_only` kalmalı.

Liste (yerel, repo'ya girmez): `/opt/data/cache/scratch/wp/empty53.json` (`sha` ilk 12 hane, `tam` alanı: tam metin var mı).

## Hedef

Parser bu kararlarda gövdenin başlangıcını bulsun; kalıcı düzeltme parser'da, tek tek kayıt yaması yok.

## Kapsam

1. **Kök neden:** 50 kararın her birinde gövdenin neden bulunmadığını sınıflandır (hangi açılış kalıbı eksik: başlık biçimi, ayrı satıra bölünmüş etiket, farklı açılış cümlesi, mahkeme türüne özgü kalıp: BİM/Danıştay/AYM/ilk derece vb.). Sınıflar ve sayıları PR açıklamasında.
2. **Düzeltme** `fields.py`'de: eksik kalıpları `_BODY_RE` (ya da gerekiyorsa mahkeme türüne özgü yeni bir desen, `_FOREIGN_BODY_RE` gibi) içine ekle. Kalıplar genel olmalı (o kararın kelimesi değil, o tür kararların açılış biçimi). Özetin içinde geçebilecek bir ifadeyi gövde başlangıcı sanma riskini değerlendir ve testle kapat.
3. **Parser sürümü:** `PARSER_VERSION` "5" → "6" (çıktı değişiyor; yükleyici yeni extraction ekler, Görev 05 kuralı).
4. **Testler** modül adıyla (`test_decisions_fields.py`): her yeni kalıp için kısa, sentetik ya da kısaltılmış bir örnekle "gövde bulunur, `full` / `excerpt`" testi; gerçekten yalnız özet olan durum için "`summary_only` kalır" testi; özette geçen tuzak ifade için negatif test.
5. **Tam arşiv karşılaştırması** (kabul kriteri, PR'da çıktı): eski ve yeni parser'la tüm arşivi (6.334 karar) parse et ve farkı raporla:
   - 53 kararın kaçı `summary_only`'den çıktı (beklenen 50), 3 yalnız-özet kararı `summary_only` kaldı mı,
   - 53 dışında `text_completeness`, `full_text` başlangıcı, `editorial_summary`, `outcome` alanı değişen kayıt sayısı ve her değişen sınıftan elle okunmuş örnekler. Beklenmedik değişiklik (önceden doğru bulunan gövdenin yer değiştirmesi) olmamalı; varsa açıklanır ya da düzeltilir.
   - Karşılaştırma betiği repo'ya girmez (scratch'te kalır); komut ve özet PR'da.

## Kapsam dışı

- Canlı veritabanına yükleme (Themis merge sonrası yapar, aşağıda).
- Yükleyici, güven kuralı veya panel değişikliği.
- 3 yalnız-özet kararın tam metnini dış kaynaktan tamamlama (Yargıtay/UYAP teyidi ayrı iş).

## Kabul kriterleri

- `cd packages/ingest && uv run pytest` ve repo kökünde `make lint`, `make typecheck`, `make test` (Postgres gerektirmeyen kısım) yeşil; CI yeşil.
- Tam arşiv karşılaştırmasında 50 karar `full`/`excerpt`, 3 karar `summary_only`; 53 dışı değişiklikler açıklanmış.
- PR'da `data/` içeriği, karar metninin uzun alıntısı yok.

## Canlıya alma (merge sonrası, Themis)

1. Yeni parser'la `decisions.jsonl` üret; yalnız `text_completeness` ya da `full_text`'i değişen ve canlıda **henüz incelenmemiş** (kaynak durumu `analyzed`, review'sız) kayıtları içeren bir alt küme çıkar.
2. Alt kümeyi app konteynerine taşı, `python -m app.loaders.decisions <alt küme> --files ... --dry-run`, sonra gerçek yükleme. Yeni parser sürümü yeni extraction ekler; eski extraction ve onaylı kayıtlar değişmez.
3. Panelde 50 kararın "Yalnız özet" etiketinin kalktığını ve güven bandının yeniden hesaplandığını kontrol et.

## Notlar Claude Code için

Kök neden: 48 hedefin (50'den ikisi main'de zaten `full`) hepsinde özetten sonraki ilk satır `_BODY_RE`'nin tanıdığı bir açılış değildi (DAVA / I. DAVA / Davacı vekili ... yoktu). Sınıflar (hedef sayısı):

- Yargıtay, DAVA satırı olmayan numaralı temyiz maddesi: "1-Dosyadaki yazılara ..." 11 (biri özetin son kelimesine yapışık: "ortadadır1-Dosyadaki"), "1-Davalı vekilinin temyizi açısından" 1: **12**.
- Danıştay / BİM: "TÜRK MİLLETİ ADINA" 5 (biri OCR'la "ADİNA", kısa BİM kararı 617 karakter, `excerpt`), Danıştay "İSTEMİN_KONUSU" 1: **6**.
- AYM: "İTİRAZ YOLUNA BAŞVURAN" 1, "II. BAŞVURU SÜRECİ" (ilk bölüm başlığı OCR'la bozuk) 1: **2**.
- BAM: "Mahalli mahkemesinden verilen karara karşı" 5, "Davacı iddiası" 3, "TARAFLARIN İDDİA ..." 1, "Yukarıda mahkemesi ile esas ve karar numarası" 1, "İlk derece mahkemesince verilen karara karşı" 1: **11**.
- Yeni şablonlu Yargıtay (HGK / uyuşmazlığın giderilmesi), I. bölüm başlığı yok ya da "I-GİRİŞ": "I-GİRİŞ" 1, "II." / "III." / "IV." ile başlayan 5: **6**.
- Yargıtay diğer: "1. Taraflar arasındaki ... davasından dolayı" 2, "Davaya konu uyuşmazlık" 2, "A-5521 sayılı", "Başvurucu (davacı) vekili", "Yukarıda tarih ve numarası yazılı", "Bölge Adliye Mahkemesi kararı ... temyiz edilmekle" 1'er: **8**.
- İşaretsiz, `summary_only` kalan: **3** (aşağıda).

Eklenen kalıplar: `_BODY_RE`'ye güçlü açılışlar (yukarıdaki sınıfların başlık / formül biçimleri; romen başlık I. ötesine ve tireye genişletildi). `_ITEM_RE`: numaralı temyiz maddesi; kendinden önce temyiz formülü olan açılış paragrafı varsa o paragraf korunur (formül kazanır, `body_start_approximate`). `_FORMULA_RE`'ye zayıf açılışlar (TARAFLARIN İDDİA, "Bölge Adliye Mahkemesi kararı ... temyiz edilmekle", "İlk derece mahkemesince verilen karara karşı"): yalnız başka işaret yokken devreye girer, böylece zaten bulunmuş gövdelerin başlangıcı kaymaz. Özetin son kelimesine yapışık "1-Dosyadaki" için metin, eşleşmeden önce o noktada satıra bölünür.

Bilinen sınırlar:

- `summary_only` kalan 3 tam-metinli karar: 9. HD E.2012/2995 K.2012/30457 (arşivde iki kopya) ve 18. CD E.2015/16631. Özet gövdeyi aynen tekrarlıyor ve gövde açık işaret olmadan sürüyor; güvenilir kalıp yok. "Noktasız biten özet" sezgisi, yanlış kesimle "full" etiketli kirli veri üreteceği için eklenmedi.
- 5 yeni şablonlu karar gövdeyi II.–IV. başlıkta başlatır: ilk bölümlerin (I. başvuru / dava) başlığı çıkarılmış metinde yok, bu bölümler gövdeye girmez.
- Zayıf kalıplar `body_start_approximate` uyarısı verir (başlangıç satırı kesin, ama işaret zayıf).
- Özet `ÖZETİ` etiketsiz bir karar (21. HD E.2012/6998) artık gövde bulunduğu için özetini anahtar kelime listesine alıyor (önceden boştu); ayrı iş.
- Karşılaştırma: iki sürümle `hukuk-ingest decisions parse --scan-report ... --out <dizin>`, sonra scratch'teki betik (repo'ya girmez).
