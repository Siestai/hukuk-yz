# Paket B1: Yeni 10 eval vakası (ham analiz notları)

Kaynak: proje soru bankası (ortakların gerçek soruları). Repo public olduğu için soran kişi yazılmaz; uzman düzeltmeleri
"Tuzak" olarak, kurumsal dille. `legal-case-analyst` her vakayı resmi metinden yeniden doğrular; buradaki künyeler
başlangıç noktasıdır, "belirlenecek" yazanlar analistin işidir. Doğrulanamayan künye vaka dosyasına girmez.

Genel ders (tüm vakalar): kanunda hüküm bulunması aramayı bitirmez; yönetmelik, genelge katmanı da taranır.
Benzer hükümler çoksa ilk eşleşen verilmez, önce netleştirme sorulur. Kip: "-iyor" yok.

---

## SB-002 · 4/c sigortalısının ölümünde ölüm toptan ödemesi ve gelir şartı
- **Soru (aynen):** "4/c sigortalısının ölümü sonrası hak sahiplerinin ölüm toptan ödemesi alabilmesi için gelir tespiti şartı var mıdır"
- **Kaynaklar:** 5510 m.34, m.37; 2018/38 Emeklilik İşlemleri Genelgesi (ilgili bölüm belirlenecek); ilgili AYM kararları (belirlenecek, yoksa `missing_in_kb`).
- **Tuzak:** genelge katmanı kanunla birlikte taranmalı; m.34'teki "gelirin asgari ücretin net tutarından az olma" şartının toptan ödemeye uygulanıp uygulanmadığı genelgeden kontrol edilir.
- **Şablon:** `olum_yaslilik_aylik`.

## SB-010 · Günlük ve maktu (aylık) ücretin tazminata ve SGK bildirimine etkisi
- **Soru (aynen):** "İşçinin ücretinin günlük yada maktu olarak belirlenmesi iş akdinin feshinden sonraki tazminatları nasıl etkiler? Primlerin sgk ya bildirimleri de dikkate alındığında işveren açısından günlük veya maktu ücreti seçmenin hangisi avantajlıdır"
- **Kaynaklar:** 1475 m.14; 4857 m.17, 46, 47, 49, 57; SSİY m.100 (KB'de yoksa `missing_in_kb`); Yargıtay 7. HD E.2014/4246 K.2014/11488 (225 bölen), 9. HD E.2010/13838 K.2012/19690 (7,5 bölen) (teyit edilecek).
- **Daralt:** "hangisi avantajlı" kısmı görüş; vaka hukuki farkları (bölen, hafta tatili, eksik gün) beklesin, tavsiye beklemesin.
- **Not:** hesap tutarı yok (md.29).
- **Şablon:** `sgk_bildirim_prim` ya da yeni `ucret_turu`: analist karar verir.

## SB-012 · 6 eksik gün koduyla en fazla kaç gün bildirilebilir
- **Soru (aynen):** "bie soru daha. 6 eksik gün koduyla bildirrilen bir işçi eksik gün bildirileceği varsayımıyla sgk ya en fazla kaç gün bildirilebilir."
- **Kaynaklar:** 4857 m.13 (kısmi süreli); SSİY eksik gün düzenlemesi ve kod listesi (belirlenecek).
- **Tuzak (kritik):** puantaj ile kısmi süreli çalışma ayrı rejimdir. Kısmi süreli çalışma yazılı sözleşmeyle olur (kod 06); puantaj gün usulüdür, puantaj belgesiyle olur (kod 07). İki rejim karıştırılmaz. Kod verilmişse o rejimin kuralı uygulanır; verilmemişse hangi kodla bildirildiği sorulur.
- **must_ask:** eksik gün kodu / çalışma biçimi.
- **Şablon:** `sgk_bildirim_prim`.

## SB-014 · İşe giriş bildirgesi cezasında tekrar halinde 5 kat: bir yıl ne zaman başlar
- **Soru (daraltılmış):** "İşverene uygulanan işe giriş bildirgesi cezasında bir yıl içinde tekrar halinde ceza 5 kat uygulanıyor. Bahsedilen bir yılın ne zaman başlayacağına ilişkin mevzuat nedir?"
- **Daralt:** orijinal soru karar karşılaştırması + yazı istiyor; eval yalnız sürenin başlangıcını ölçer. Yazı üretimi kapsam dışı.
- **Kaynaklar:** 5510 m.102/1-a; 2020/8 genelgesinin tekrar hâline ilişkin bölümü (belirlenecek); arşivde Danıştay / BİM kararı varsa (teyitli).
- **Tuzak:** kanunda hüküm olsa da alt mevzuat (genelge) taranmadan cevap verilmez.
- **Şablon:** `idari_para_cezasi`.

## SB-019 · Bordro hilesi (yalnız prime esas kazanç eksik) idari para cezası (KRİTİK)
- **Soru (bağımsızlaştırılmış):** "İşveren sigortalıyı ve gün sayısını tam bildirmiş, yalnız prime esas kazancı eksik bildirmiş. İdari para cezası defter türüne göre değişir mi, nasıl hesaplanır?"
- **Daralt:** orijinal soru önceki cevaba atıf yapıyordu ("tekrar eder misin"); tek başına anlaşılır hâle getirildi.
- **Doğru cevap:** 5510 m.102/1-m-4-ç. Sigortalı ve gün tam, yalnız kazanç eksikse defter türü ve asıl / ek ayrımı hesaba girmez; ceza her işyeri ve her ay için eksik kazanç tutarı kadardır, alt sınır asgari ücretin onda biri, üst sınır iki asgari ücret. Aynı ay için sonraki tespitte iki asgari ücrete kadar fark kesilir (2020/8 m.2.6.2.5).
- **must_not:** m.102/1-m-4-a / b defter türü oranları (bilanço esasına göre asgari ücret, tavan 3 asgari ücret vb.). Bilinen hata: alt bentlerin tamamı okunmadan defter türü oranı verildi.
- **Tuzak:** atıf öncesi tüm alt bentler vakayla tek tek eşlenir; açık hükümde hata kabul edilmez.
- **Şablon:** `idari_para_cezasi` (alt bent düzeyi).

## SB-027 · İK uzmanı: işçi 5 gün üst üste mazeretsiz işe gelmedi, ne yapmalı
- **Soru (aynen):** "Ben ik uzmanıyım çalışan 5 gün üstüste mazaretsiz işe gelmedi üstüme insan kaynakları uzmanı olarak ne yapmam lazım?"
- **Kaynaklar:** 4857 m.25/II-g (devamsızlık), m.26 (6 iş günü ve 1 yıl hak düşürücü süre), m.19 (savunma); işten ayrılış bildirgesi (5510 m.9; ayrılış kodu belirlenecek); savunma ve makul süreye ilişkin Yargıtay 9. HD kararları (teyitliyse).
- **must_ask:** devamsızlık günlerinin iş günü olup olmadığı, işçiye ulaşılıp ulaşılamadığı, mazeret bildirimi, tutanak.
- **must_not:** "savunma alınmasına gerek yoktur" gibi kesin ifade. Tuzak: uygulamada savunma isteme / ihtar adımı ve makul süre beklenir; kesin cümle kurulmaz.
- **Şablon:** `hakli_fesih_devamsizlik`.

## SB-032 · Giydirilmiş ücrete yemek, yol ve kupon eklenir mi
- **Soru (bağımsızlaştırılmış):** "Giydirilmiş ücrete yemek, yol ve kupon (yemek kartı) yardımı eklenir mi, neden eklenir? Dayanağı ve yerleşik içtihatla birlikte açıkla."
- **Daralt:** orijinal soru önceki bir hesabın senaryolarına atıf yapıyordu.
- **Kaynaklar:** 1475 m.14/11; sürekli ve düzenli ödenen yardım ile arızi ödeme ayrımına ilişkin Yargıtay 9. HD / HGK kararları (teyitliyse; değilse `missing_in_kb`).
- **Tuzak:** kıdem (giydirilmiş) ile ihbar ve izin ücreti hesap tabanı ayrı tutulur; ayni / nakdi ve süreklilik ayrımı.
- **Şablon:** `kidem_ihbar`.

## SB-035 · Yıllık izin ücreti ödenmezse işçinin haklı fesih hakkı
- **Soru (aynen):** "1 gün yıllık izin kullanan işçiye işveren ücretini vermezse fesih hakkı doğar mı? Doğar ise bu hakkı ne kadar süre içinde kullanmalıdır işçi? Ve usül nedir"
- **Kaynaklar:** 4857 m.24/II-e, m.26, m.57, m.34; 1475 m.14; fesih usulüne ilişkin Yargıtay 9. HD kararları (teyitliyse).
- **must_ask:** ücret hiç mi ödenmedi yoksa gecikmeli mi, ödenmeyen tutar, kıdem, ihtar.
- **Tuzak:** m.26'daki 6 iş günü / 1 yıl sürelerinin ücret alacağında nasıl işlediği kesin söylenmeden önce kaynaktan kontrol edilir; fesih yazılı ve gerekçeli; sonuç kıdem var, ihbar yok.
- **Şablon:** `hakli_fesih_devamsizlik` (ya da `yillik_izin` ile birlikte: analist karar verir).

## SB-039 · Sonradan dayanışma aidatı ödeyen işçinin TİS'ten yararlanması
- **Soru (daraltılmış):** "01.01.2025-31.12.2026 geçerlilik tarihli TİS 01.10.2025'te imzalandı. 10.12.2025'te sendikaya dayanışma aidatı ödemeye başlayan işçi TİS'ten nasıl ve hangi tarihten itibaren yararlanır? Aralık 2025'teki 13 günlük ilave tediye ve 20 günlük ikramiyeden yararlanır mı?"
- **Daralt:** orijinal soru 5 alt soru içeriyordu (ek protokol, ödenmeme, SGK bildirimi, YHK kararı). Eval yalnız 1. ve 2. alt soru.
- **Kaynaklar:** 6356 m.39 (dayanışma aidatıyla yararlanma); ilave tediye için 6772 sayılı Kanun (KB'de yoksa `missing_in_kb`).
- **must_ask:** aidat başvuru / ödeme tarihi, TİS'te yararlanma başlangıcına ilişkin hüküm, ödemelerin hak ediş tarihi.
- **Şablon:** `tis_sendikal`.

## SB-042 · 08 koduyla ayrılıp kıdem tazminatı: 2008 öncesi ve sonrası girişler
- **Soru (bağımsızlaştırılmış):** "08 koduyla (emeklilik için yaş dışındaki şartları tamamlayarak) işten ayrılıp kıdem tazminatı almak isteyen işçide, 2008 Ocak'ta işe giren ile 2008 Aralık'ta işe giren arasında şart bakımından fark var mı?"
- **Daralt:** tablo ve yazı istekleri kapsam dışı.
- **Kaynaklar:** 1475 m.14/1 (ilgili bent); 506 sayılı Kanun geçici m.81 ve 5510 m.28, geçici m.6 vd. geçiş hükümleri (KB'de olmayanlar `missing_in_kb`); 2018/38 Genelgesi (ilgili bölüm).
- **Tuzak:** 5510'un yürürlüğü 01.10.2008; Ocak 2008 girişli ile Aralık 2008 girişli farklı rejime düşer; gün ve süre şartı doğru kademeden alınır; her tarih kaynaktan doğrulanır, kesinlik iddiası kaynaksız kurulmaz.
- **Şablon:** `olum_yaslilik_aylik` (adı `emeklilik_aylik` olarak genişletilebilir).
