# Görev 10k: telefonda PDF görüntüleyici (PDF.js)

Durum: uygulandı, PR Orhan'ın onayında; gerçek Android Chrome doğrulaması merge sonrası (Themis, 2026-10-15). Yakınlaştırma: +/- düğmeleri (adımlar %100-300; sayfa zoom'u canvas'ı yeniden çizmediği için parmakla yakınlaştırma yerine). Issue: #68. Bilinen sınırlama: PDF.js yazı tipi/cMap/wasm dosyalarını kendi origin'imizden vermiyor (`standardFontDataUrl`, `cMapUrl`, `wasmUrl` yok; ~4 MB ek varlık, build/standalone kopyalama adımı ve CSP kontrolü gerektirir, bu görevin kapsamını aşar); gömülü olmayan standart yazı tipli, CJK cMap'li veya JPEG2000/JBIG2 görüntülü PDF'lerde eksik/boş çizim olursa yeni sekme bağlantısı çıkış yolu olarak kalır. Ayrı görev önerilir. Onay: Orhan ("PDF olayını merge et", 2026-10-15, Telegram).
Bağlam: `services/dashboard-web/src/components/review-detail/pdf-panel.tsx` (#65, görev 10i), `src/components/files/file-viewer.tsx`, `src/lib/security-headers.ts`.
Skill'ler: `frontend-ui` (bağlayıcı), `task-pr-hygiene`.

## Sorun

10i ile karar PDF'i telefonda sayfanın üstündeki bir pencerede, `<iframe>` içinde açılıyor. Gerçek telefonlarda bu çalışmıyor:
- Android Chrome'da gömülü PDF görüntüleyici yok. iframe'de "gösterilemiyor" ikonu çıkıyor (ortak geri bildirimi, 2026-10-15).
- iOS Safari gömülü PDF'in yalnız ilk sayfasını gösteriyor.

Kullanıcı yine "Yeni sekmede aç"a basmak zorunda kalıyor. 10i'nin e2e testleri geçti, çünkü Playwright'ın telefon emülasyonu masaüstü Chromium'un PDF görüntüleyicisini kullanıyor.

Dosyalar ekranı (`file-viewer.tsx`) telefonda PDF'i hiç göstermiyor, yalnız yeni sekme bağlantısı var.

## Kapsam

1. **PDF.js görüntüleyici bileşeni** (`pdfjs-dist`): sayfaları canvas'a çizer, alt alta kaydırılır, genişliğe sığar.
   - Metin katmanı (seçilebilir metin). Yakınlaştırma: parmakla yakınlaştırma çalışır ya da +/- düğmeleri (44 px). Hangisi seçildiyse gerekçesi özette.
   - Uzun PDF'te sayfalar görünüme yaklaşınca çizilir (tüm sayfalar baştan çizilmez).
   - Yüklenirken iskelet/ilerleme, hata olursa mesaj + "Yeni sekmede aç" yedeği.
   - PDF.js yalnız görüntüleyici açılınca dinamik `import()` ile yüklenir; ilk sayfa yüklemesinde inmez.
   - Worker kendi origin'imizden sunulur (CDN yok).
2. **Kullanım:**
   - `pdf-panel.tsx`: `md` altında pencere içindeki iframe yerine bu görüntüleyici. `md` ve üstünde bugünkü iframe davranışı değişmez.
   - `file-viewer.tsx`: PDF ise `md` altında "Dosyayı aç" ile aynı pencere kalıbı (10i'deki Dialog) içinde bu görüntüleyici; PDF olmayan dosyalarda bugünkü davranış.
   - "Yeni sekmede aç" yedek bağlantısı her iki yerde kalır.
3. **CSP:** yalnız gereken en küçük değişiklik (ör. `worker-src 'self'`; PDF.js bunu istiyorsa font/`blob:`). `unsafe-eval` yok. Değişikliğin nedeni `security-headers.ts` testinde ve özette.
4. **Metinler** `messages/tr.json`'da.
5. **Testler:**
   - Bileşen testleri modül adıyla (`pdf-viewer.test.tsx` vb.).
   - e2e (360 px): karar detayında "PDF'i aç" → görüntüleyicide en az bir **canvas çizilmiş** olmalı (iframe değil), 2. sayfaya kaydırılabiliyor. Dosyalar detayında aynısı.
   - e2e (1440 px): bugünkü iframe görünümü değişmedi.
   - Testte `isMobile` emülasyonunun gerçek telefon davranışını yansıtmadığı not edilir. Kabulde canvas varlığı esas alınır.
6. 360/768/1440 ekran görüntüsü (karar PDF penceresi, dosya PDF penceresi).

## Kapsam dışı

- Masaüstünde iframe'in PDF.js ile değiştirilmesi.
- PDF içinde arama, açıklama/işaretleme.
- Backend değişikliği.

## Kabul kriterleri

- 360 px'te karar detayında ve dosya detayında PDF'in tüm sayfaları pencerede canvas olarak görünür, yeni sekme gerekmez.
- 1440 px'te görünüm değişmedi.
- PDF.js ayrı chunk'ta; ilk yüklemede inmiyor (build çıktısı özette).
- CSP'de yalnız gereken değişiklik, `unsafe-eval` yok.
- pnpm lint/typecheck/test/build/format:check yeşil; e2e yeni senaryolar geçer; 360 px'te yatay kaydırma yok.
- Canlıda gerçek Android Chrome'da doğrulama (merge sonrası, ortak teyidi).
