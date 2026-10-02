# Spike: karararama.yargitay.gov.tr ile otomatik teyit

Tarih: 2026-10-02. Yapan: Orhan + Claude Code. Okuyucu: Themis.
Bağlam: İbrahim'in 2026-10-02 kuralı (`decisions.md`): kullanıcıya gösterilen her Yargıtay kararı karararama.yargitay.gov.tr'den E/K ile teyit edilir ve kaynak olarak orası gösterilir.

## Sonuç (kısa)

1. **Otomatik teyit mümkün.** E/K + daire ile sorgu JSON döner, tam metin ayrı endpoint'ten gelir. Normal kullanımda captcha çıkmadı.
2. **Hız sınırı sıkı.** Art arda ~4-5 istekten sonra HTTP 429. 10 sn aralıkla sorun çıkmadı (~6 istek/dk).
3. **Kapsama karar yılına bağlı.** 2015 ve sonrası: örneklemde %100. 2010-2014: yarısı. 2009 ve öncesi: hiç yok.
4. **Arşivin ~%25'i (≤2009, ~1.500 karar) bu siteden teyit edilemeyecek.** İbrahim'in kuralıyla bu kararlar kullanıcıya "teyit edilemedi" işaretiyle gösterilir ya da hiç gösterilmez. Ortaklarla karar gerekiyor.

## Yöntem

- Arşivden rastgele 30 karar (seed=7, 6-90. sayılar), metinden daire + E/K regex ile çıkarıldı.
- Her karar `aramadetaylist`'e daire + esas + karar numarasıyla soruldu; bulunamazsa dairesiz tekrar.
- 3 "bulunamadı" sonucunu elle inceledik: ikisi BAM kararıydı (sitede yok, beklenen), biri HGK kararıydı ve E/K formatı farklıydı (aşağıda). Bunlar düzeltilerek tablo hesaplandı.

| Karar yılı | Bulunan / Yargıtay kararı | Arşivdeki yaklaşık karar sayısı |
|---|---|---|
| ≤ 2009 | 0 / 9 | 1.519 |
| 2010-2014 | 2 / 5 | 1.487 |
| 2015+ | 15 / 15 | 3.079 |
| Karar no çıkarılamadı | — | 249 |

Arşiv sayıları kaba: regex ilk "Karar No" yılını alıyor, BAM/AYM/yabancı kararlar da dahil. Örneklem küçük (n=29 Yargıtay); 2010-2014 oranı özellikle belirsiz.

## Teknik ayrıntı

Site: Adalet Bakanlığı BİGM uygulaması. `robots.txt` yok (404). Kullanım şartlarını okumadık.

**Arama:** `POST https://karararama.yargitay.gov.tr/aramadetaylist`

```json
{"data": {
  "arananKelime": "",
  "birimYrgHukukDaire": "9. Hukuk Dairesi",
  "esasYil": "2017", "esasIlkSiraNo": "17327", "esasSonSiraNo": "17327",
  "kararYil": "2020", "kararIlkSiraNo": "14291", "kararSonSiraNo": "14291",
  "siralama": "1", "siralamaDirection": "desc", "pageSize": 10, "pageNumber": 1
}}
```

- Header: `Content-Type: application/json; charset=utf-8`, `X-Requested-With: XMLHttpRequest`, `Referer`. Önce ana sayfa GET ile cookie alınır.
- HGK/CGK için `birimYrgKurulDaire: "Hukuk Genel Kurulu"`.
- Dönen satır: `{id, daire, esasNo, kararNo, kararTarihi}`.
- Hata zarfı: `metadata.FMTY = "ERROR"`. `aramalist` (basit arama) yanlış parametrede `ADALET_RUNTIME_EXCEPTION` döndü.

**Tam metin:** `GET /getDokuman?id=<id>` → `{"data": "<html>"}`. Örnek: 13.7 bin karakter, anonimleştirilmiş resmi metin, başlıkta `9. Hukuk Dairesi 2017/17327 E. , 2020/14291 K.`

**Captcha:** sayfada reCAPTCHA var ama koşullu (`isDisplayCaptcha=false`). Sunucu `DisplayCaptcha` ya da `reCaptchaTimeout` dönerse devreye giriyor. Bizim denemede tetiklenmedi.

**Hız sınırı:** ~4-5 hızlı istekten sonra 429, `Retry-After` header'ı yok. 60 sn beklemek yetti. 10 sn aralıkla 55 istekte yeni 429 olmadı.

## Parser için çıkan dersler

1. **HGK esas formatı farklı:** dergi `2024/10-389` yazıyor (10 = kaynak daire), site `2024/389` olarak tutuyor. Normalize: `YYYY/D-N` → esas `YYYY/N`, ayrıca `source_chamber = D`.
2. **Mahkeme tespiti başlıktan yapılmalı.** Gövdede "Yargıtay 10. Hukuk Dairesince" gibi atıflar geçiyor; ilk "Hukuk Dairesi" eşleşmesini almak BAM kararlarını Yargıtay sanıyor. `T.C. / X BÖLGE ADLİYE MAHKEMESİ` başlığı BAM demek.
3. **E/K bu iş için birincil anahtar.** Altın sette daire + E/K doğruluk hedefi %100 olmalı.

## Ürüne etkisi

- `decision.verification` değerleri: `verified_yargitay` (karararama'da bulundu, E/K/tarih eşleşti), `not_on_official_site` (sorgu boş döndü), `mismatch` (bulundu ama tarih/daire farklı), `unverified` (henüz sorulmadı), `not_applicable` (BAM/AYM/yabancı: başka kaynak gerekir). `data-model.md` §5.2 buna göre güncellenmeli.
- Teyit edilen kararda `full_text` resmi metinden alınabilir, dergi metni yedek olur. Kaynak URL'i: karararama (doğrudan karar linki yok, `id` ile `getDokuman`).
- Toplu teyit maliyeti: ~5.800 Yargıtay kararı × (1 arama + 1 tam metin) ≈ 11.600 istek. 10 sn aralıkla ≈ 32 saat, tek seferlik arka plan işi (worker). Sonrasında yalnızca yeni kararlar.

## Karar bekleyenler (ortaklar)

1. **≤2009 kararlar (~1.500):** "teyit edilemedi" etiketiyle gösterilsin mi, sadece arama aracı olarak mı kalsın, yoksa başka resmi kaynak (UYAP Emsal, Kazancı vb. lisanslı) mı aranmalı? (İbrahim / Baran)
2. **BAM (297), AYM (51), Danıştay (4) için teyit kaynağı:** emsal.uyap.gov.tr, anayasa.gov.tr kararlar bilgi bankası, danistay.gov.tr. Kural bunları da kapsıyor mu? (İbrahim)
3. **Toplu sorgu izni:** 11.600 istek resmi bir siteye. Kullanım şartlarına bakılmalı; gerekirse BİGM'den izin ya da daha yavaş tempo. (Orhan)

## Themis için önerilen sonraki işler

1. `decisions.md`'ye bu spike'ın sonucunu ve yukarıdaki 3 soruyu ekle; soruları gruba ilet.
2. `data-model.md` §5.2 `verification` enum'unu ve §11 açık sorusunu güncelle.
3. emsal.uyap.gov.tr ve anayasa.gov.tr için aynı spike'ı yap (BAM ve AYM teyidi).
4. karararama kullanım şartlarını bul ve özetle.

Ham sonuçlar (yerel, repoda değil): `/tmp/kk_sample.json`, `/tmp/kk_probe.log`, `/tmp/kk_probe.py`.
