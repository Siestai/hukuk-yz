# Kararlar ve açık öneriler

## Kararlar

### 2026-10-01 (WP grubu, ilk gün)
- **Hedef kitle önceliği** (İbrahim): 1) Mali müşavirler 2) İK uzmanları 3) Avukatlar 4) Kurumsal şirket İK personeli 5) Kariyer meslek mensupları (SGK müfettişi, iş müfettişi, SGK denetmeni). → İsim ve dil "hukuk" değil "iş + sosyal güvenlik + güven" ekseninde olmalı.
- **Uzman döngüsü** (İbrahim): Themis emin olmadığı noktayı grupta dar bir soru olarak sorar, ortaklar kabataslak cevap verir, Themis kaynak atıflı metne çevirip "X teyidiyle" notuyla paylaşır. Kabul edildi.
- **Kaynak sınırlama** (Baran): sistem tüm webde değil, ortakların belirlediği site listesinde arar. Liste ortaklardan gelecek.
- **Süreç aşaması muhakeme girdisidir** (İbrahim'in düzeltmesi): denetim aşaması (tespit öncesi / tutanak açık / kapandı / tebliğ) cevabı tamamen değiştirir. Örnek: 5510 m.102 "kendiliğinden verme" penceresi tutanak kapanana kadar açık, ceza ciddi düşüyor. Sistem aşamayı sormadan cevap vermemeli; hesaplama motorunda m.102 dalları ayrı olmalı.
- **Hitap**: Baran "abi" istemiyor, "Baran".

### 2026-10-02
- **Resmi kaynak teyidi** (İbrahim, WP grubu): Çalışma ve Toplum arşivi yalnızca ilk arama aracıdır. Bulunan her Yargıtay kararı karararama.yargitay.gov.tr'den esas/karar numarasıyla teyit edilir ve kullanıcıya gösterilen kaynak orasıdır. Teyit edilemeyen karar açıkça işaretlenir, sessizce geçilmez. Üründe karşılığı: `decision.verification` alanı (`data-model.md` §5.2); `unverified` kayıt atıf kapısından `verified` olarak geçemez.
- **Pazar araştırması** (Themis, İbrahim'in isteğiyle): Türkiye'de iş hukuku + SGK odaklı, kaynak atıflı ve deterministik hesaplama yapan ürün yok. Avukat odaklı içtihat YZ'leri (emsal.ai, hukuk.chat, Kazancı AI, Jupytr, HukukOS) ve mali müşavir radarları (Müşavir AI, MALİİK) kesişmiyor. Farklılaşma: olay tarihindeki mevzuat, deterministik hesap, SGK genelge katmanı, mali müşavir persona'sı, uzman eskalasyonu. Rapor: `docs/market-research-2026-10-02.md`.
- **Mimari ve veri modeli v0.1 onaylandı** (Orhan, PR #2, #3): 6 servis, bitemporal KB, atıf kapısında `not_found` her zaman düşer, KVKK için crypto-shredding, chunk indeksi.
- **İş yönetimi**: ortakların da kullanacağı araç olarak Notion önerildi (Orhan karar verecek). GitHub = kod, Notion = planlama/kararlar/sorular.
- **Teknik karar bekleyen**: hesap motoru ve atıf kapısı `app`'te mi `agent`'ta mı (öneri `app`).

## Açık öneriler (karar bekliyor)
- **2026-10-01, Baran (WP grubu):** Yüksek riskli / acil vakalarda (ör. SGK tespiti sonrası "ne yapalım") sistem otomatik cevap vermesin, uzman insana (Baran/İbrahim) eskalasyon yapsın. Bu eskalasyon ayrı paket veya kredi olarak ücretlendirilsin. Themis olumlu görüş bildirdi (hibrit model: makine + insan onayı). Tetikleme kullanıcı seçimi değil sistem tespiti olmalı: konu sınıfı + süre işliyor mu + belirsizlik düzeyi. Fiyatlandırma, SLA ve kapsam kararı Orhan + Baran + İbrahim'de.
- **2026-10-01, İbrahim:** Marka/isim/tasarım. Şu an sıfır. Palet yönü: lacivert temelli (SGK/ÇSGB akrabalığı), kurumsal ama soru sormaya cesaretlendiren. Themis isim adayı listesi çıkaracak, Orhan'la gruba sunulacak.
