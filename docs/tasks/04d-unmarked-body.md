# Görev 04d: işaretsiz gövdeli kararların metnini bul

Durum: uygulandı, PR bekliyor (Themis, 2026-10-26).
Sahip: Themis (uygulayan Claude Code).
Onay: Orhan (2026-10-26, Telegram: "Başla parser düzeltmesini yap merge et test et").
Bağlam: 04b (#75) sonrası panelde 7 karar hâlâ "yalnız özet" ya da metinsiz. Ortak testi (WP, 2026-10-26) ve Themis'in PDF kontrolü: bunların 6'sında (5 karar, biri iki kopya) çıkarılan metinde tam karar var; parser gövdenin başladığı yeri bulamıyor. Yalnız özet içeren kayıt (`3a48a1a56f55`) yalnız özet kalmalı; `6c3c1de7481b` ve `beb94741d68d` Themis'in metin kontrolüyle tam karar çıktı (notlara bkz.).

## Hedef

Ölçüt `text_completeness` ve `full_text`. Aşağıdaki kayıtlar (sha256 ilk 12 hane) `full` olmalı, gövde doğru yerden başlamalı, özet (`editorial_summary`) kısalmamalı:

- 9. HD E.2012/2995 K.2012/30457: `f4562568f421`, `6739ee11ae7d` (aynı karar, iki kopya). 04b notu: özet gövdeyi aynen tekrarlıyor, gövde açık işaretsiz sürüyor.
- 18. CD E.2015/16631 K.2015/10632: `a11bc3d92c42` (04b'de aynı sınıf).
- 10. HD E.2014/21595 K.2014/22216: `d362bd21a667`.
- 9. HD E.2023/8147 K.2023/8784: `be542ca980de`.
- Adana BAM 11. HD E.2023/1083 K.2024/20: `eadd4c287e44`.

Kontrol edilecek (tam metin var mı bilinmiyor; varsa hedefe girer): `f80c8ef0131c` (10. HD E.2014/22067), `bbf384d6470b` (22. HD E.2014/2858).

`summary_only` kalmalı (yalnız özet): `3a48a1a56f55`. (`6c3c1de7481b` ve `beb94741d68d` ilk taslakta bu listedeydi; Themis metni kontrol etti, ikisi de tam karar, hedefe `full` olarak girdi.)

## Kurallar

- Tek bir kararın kelimesine değil, o açılış biçimine bakan genel kural. 04b'nin üç katmanı (güçlü başlık, romen başlık, önceki satırı cümle bitiren düzyazı açılışı) korunur.
- 04b'de bilinçli olarak eklenmeyen "noktasız biten özet" sezgisi gibi kirli `full` üretecek bir kısayol yok. Gövde özetle aynı cümlelerle başlıyorsa (özetin gövdeyi aynen tekrar etmesi), bu tekrarın kendisi bir işaret olabilir: özetten sonra özetin ilk cümlesinin tekrar başladığı yer. Bu ya da benzeri, ancak yanlış eşleşme riski testle kapatılırsa.
- Bir kayıt güvenle çözülemiyorsa `summary_only` kalır ve sebebi notlara yazılır. Yanlış `full` eksik `summary_only`'den kötüdür.
- Tam arşivde (6.336 kayıt) hedef dışındaki her değişiklik okunur ve açıklanır; daha önce `full` olan bir kararın gövde başlangıcının kayması gerilemedir (açıkça daha iyi değilse).
- `PARSER_VERSION` "7". Panelde düzeltmeler 04c ile ekranda ve yeniden onayda korunur; `refresh_text` yeni metni canlı karara taşır.

## Kabul

1. Hedefler `full`, gövde doğru başlıyor (her biri için ilk 120 karakter notlarda, kısa).
2. `3a48a1a56f55` `summary_only` kalır; `6c3c1de7481b` ve `beb94741d68d` `full` (Themis kontrolü, notlarda).
3. Hedef dışı değişiklikler sayılı ve açıklanmış.
4. `packages/ingest/tests/test_decisions_fields.py`'ye yeni kural ve tuzak testleri (kısa, sentetik metin; telifli metin yapıştırılmaz).
5. `make lint`, `make typecheck`, ingest testleri yeşil.

## Teslim sonrası (Themis)

Canlıda `refresh_text` (04b'deki gibi) ile metinler kayda alınır; onaylı 4 kararın canlı metni dolar, bekleyen kopyalar panelde metinle görünür. Ortağa WP'den haber yalnız Orhan isterse.

## Notlar Claude Code için

Kök neden: 8 kararın hepsinde özetten sonraki ilk gövde satırı `_BODY_RE` / `_ITEM_RE` / formül katmanlarının tanıdığı bir açılış değildi ya da özet noktasız bittiği için düzyazı açılışı (`Davaya konu uyuşmazlık`, `A-5521 sayılı`, `Başvurucu (davacı) vekili`, `İlk derece mahkemesince`) 04b'nin "önceki satır cümleyi bitirir" koşuluna takıldı; kalanlarda (`Mülga 2821 ...`, `6100 Sayılı HMK geçici 3 ...`) hiç kalıp yok. Ortak özellik düzen: dergi özeti ~45-70 karakterde sarıyor, gövde 80-110 karakter genişliğinde basılıyor.

Eklenen kural (`_wide_line_start`, yalnız başka hiçbir işaret gövde bulamadığında ve özet varken çalışır, `body_start_approximate` uyarısı verir): özetin ilk 4 satırından sonra, o ana kadarki en geniş özet satırından 8 karakterden fazla geniş ilk satır gövdenin başlangıcıdır. Çalışma ve Toplum sayfa başlığı yapışmış satırlar (`Çalışma ve Toplum, YYYY/N`) atlanır. Yalnız `-1` dönen kayıtlara dokunduğu için daha önce bulunmuş gövdeler kayamaz; zaten `full` olan hiçbir kayıt değişmedi.

Hedeflerin gövdesinin ilk ~120 karakteri:

- `f4562568f421`, `6739ee11ae7d` (9. HD 2012/2995): "6100 Sayılı IIMK geçici 3. Madde I. Fıkrasına göre; "Bölge adliye mahkemelerinin. 26/9/ 2004 tarihli ve 5235 sayılı Adl..." (özet gövdenin kısaltılmış tekrarı; gövde bu paragrafla başlıyor, "karar verildi" ile bitiyor)
- `d362bd21a667` (10. HD 2014/21595): "Davaya konu uyuşmazlık, 6552 sayılı Kanun kapsamında yapılandırmaya tabi Kurum alacağına ilişkindir. 11.09.2014 tarihli..." (SONUÇ: BOZULMASINA ile biter)
- `a11bc3d92c42` (18. CD 2015/16631): "Mülga 2821 ve 7.11.2012 tarihinde yürürlüğe giren 6356 sayılı Kanunda sendikalar “işçilerinin ve işverenlerin çalışma i..."
- `be542ca980de` (9. HD 2023/8147): "Başvurucu (davacı) vekili, İstanbul Bölge Adliye Mahkemesinin 24. Hukuk Dairesinin 21.11.2022 tarihli ve 2019/3044 Esas..."
- `eadd4c287e44` (Adana BAM 11. HD 2023/1083): "İlk derece mahkemesince verilen karara karşı istinaf başvurusu üzerine dosya Dairemize gönderilmekle incelendi. GEREĞİ ..."

Kontrol edilecekler: ikisinde de tam metin var, hedefe girdi. `f80c8ef0131c` (10. HD 2014/22067): "Davaya konu uyuşmazlık, 6552 sayılı Kanun kapsamında ..." (SONUÇ: BOZULMASINA ile biter). `bbf384d6470b` (22. HD 2014/2858): "A-5521 sayılı İş Mahkemeleri Kanunu'nun 8. maddesine göre iş mahkemesinden verilen kararlar tefhim veya tebliğ tarihinden..." (GERİ ÇEVRİLMESİNE, karar verildi).

Hedef dışı değişiklik (tam arşiv, 6.336 kayıt; `cmp.py`: summary_only→full 10, başka geçiş yok, başka alan değişimi yok). İki kayıt ilk taslakta `summary_only` listesindeydi; Themis metni kontrol etti, ikisi de `full` doğru:

- `6c3c1de7481b` (Kütahya 2. Sulh Ceza 2006/366): Themis kontrolü: tam birinci derece ceza hükmü (İDDİA, SAVUNMA, DELİLLERİN DEĞERLENDİRİLMESİ VE GEREKÇE, HÜKÜM bölümleri); "usulen anlatıldı" bu tür hükmün olağan kapanışı. `full` doğru.
- `beb94741d68d` (9. HD 2008/5763): Themis kontrolü: kısa ama tam 2008 Yargıtay kararı (temyiz kesinlik sınırı gerekçesi, "REDDİNE ... karar verildi"). `full` doğru.

Kayıt başına istisna yok; yalnız `3a48a1a56f55` gerçekten yalnız özet (40 satır, hepsi dar), `summary_only` kaldı.

Koruma: gövde olarak seçilen satırdan metnin sonuna en az ~1000 karakter ve 8 satır olmalı, yoksa kural -1 döner (`summary_only`). Özet içindeki geniş satırı kısa bir kalan izliyorsa gövde sayılmaz; bu durumda `body_start_approximate` uyarısı da verilmez. Aynı 10 kayıt korumadan sonra da geçiyor.

Bilinen sınırlar:

- Kural yalnız düzen (satır genişliği) varsayar: özet ile gövde aynı genişlikte basılmışsa ya da özet satırı sayfa başlığı dışında bir nedenle taşıyorsa yanlış başlangıç ya da kayıt `summary_only` kalır. Tam arşivde yanlış eşleşme gözlenmedi, ancak yalnızca bu 10 kayıt etkileniyor.
- Başlangıç yaklaşıktır (`body_start_approximate`); ilk paragraf özetin tekrarıysa (9. HD 2012/2995) gövde o tekrar paragrafla başlar.
- `f80c8ef0131c` karar no yılı (2015) ile tarih yılı (2014) farklı: kaynakta zaten öyle (`karar_year_ne_date_year` uyarısı).
