# Görev 10i: karar detayında PDF penceresi ve hep görünür "Düzelt"

Durum: uygulandı, PR Orhan'ın onayında. Ölçüm: aksiyon çubuğu sticky'si bozuk değildi (360 ve 1440'ta metin sonunda görünüyor, üstte `overflow` kapsayıcı yok); asıl sorun formun sayfanın üstünde kalmasıydı, bu yüzden form görünüme kaydırılıp odaklanıyor ve Vazgeç / gözden geçir düğmeleri aksiyon çubuğuna taşındı. (Taslak: İbrahim, 2026-10-12, karar detay ekranına 9/10 puan verdi, mobilden kullandı). Sahip: Themis (Claude Code çalıştırır). Onay: Orhan (dashboard işi Themis'e devredildi, 2026-10-12).)
Bağlam: `services/dashboard-web/src/app/(app)/kararlar/[extractionId]/page.tsx`, `src/components/review-detail/{pdf-panel,document-tabs,action-bar,review-session,fields-panel,fields-form}.tsx`, `docs/tasks/10c-review-detail.md`, `docs/tasks/10e-responsive-dashboard.md`.
Skill'ler: `frontend-ui` (bağlayıcı), `task-pr-hygiene`.

## Sorun

İbrahim'in iki isteği:
1. "PDF yeni sekmede değil, sayfanın üstünde pencere olarak açılsın." Bugün telefonda PDF sekmesi yalnız "PDF'i aç" bağlantısı, yeni sekme açıyor; kullanıcı karardan kopuyor.
2. "Kararı okurken Düzenle düğmesi hep görünür kalsın." Aksiyon çubuğu `sticky bottom-0`, ama uzun metni okurken düğmeye ulaşmak ya da düğmeye basınca açılan formu bulmak için en üste kaydırmak gerekiyor.

## Kapsam

1. **PDF penceresi (modal).** PDF sekmesinde (masaüstünde gömülü görünüm kalır) bir "PDF'i büyük aç" / telefonda "PDF'i aç" düğmesi, PDF'i sayfanın üstünde tam ekrana yakın bir pencerede açar (iframe, aynı `/api/review/decisions/{id}/file` route'u). Erişilebilir dialog: başlık, kapat düğmesi (44 px), Escape, odak tuzağı, kapanınca odak düğmeye döner, arka plan kaydırması kilitli. Telefonda (`md` altı) pencere tam ekran.
    - Telefon tarayıcısı gömülü PDF'i gösteremeyebilir (iOS yalnız ilk sayfa): pencerede her zaman "Yeni sekmede aç" yedek bağlantısı görünür. `frontend-ui` kuralı (PDF mobilde bağlantı) bu yedekle korunur.
    - PDF yoksa (`availability` ≠ `available`) bugünkü mesaj aynen; düğme çıkmaz.
2. **Hep görünür "Düzelt".** Önce 360 ve 1440 px'te Playwright ile ölç: uzun kararda metin sekmesinin sonuna kaydırınca aksiyon çubuğu görünüyor mu (sticky'yi bozan bir kapsayıcı `overflow` var mı). Görünmüyorsa kök nedeni düzelt.
    - "Düzelt"e basılınca (ya da kısayolla) alanlar formu görünüme kaydırılır ve ilk alana odaklanılır; kullanıcı yukarı kaydırmak zorunda kalmaz. Düzenleme sırasında "Kaydet / Vazgeç" düğmeleri de görünür kalır (formun kendi düğmeleri sticky ya da aksiyon çubuğunda).
    - `prefers-reduced-motion`'da kaydırma animasyonsuz.
3. **Metinler** `messages/tr.json`'da (ve repoda eşlenen diğer dil dosyalarında).
4. **Testler:** bileşen testleri modül adıyla (`pdf-panel.test.tsx`, `action-bar`/`review-session` ilgili test dosyaları); e2e'de mevcut karar detay spec'ine: PDF penceresi açılır/Escape ile kapanır; 360 px'te uzun metnin sonunda "Düzelt" görünür ve tıklanınca form görünüme gelir.
5. 360/768/1440 ekran görüntüsü (pencere açık, metin sonunda çubuk, düzenleme formu).

## Kapsam dışı

- Onaylanan/reddedilen kararda düzenleme (bugün "Onaydan çıkar" ile yeniden incelemeye alınıp düzeltilir; değişmez).
- Dosyalar ekranındaki PDF görünümü (`files/file-viewer.tsx`).
- Backend değişikliği.

## Kabul kriterleri

- Telefonda (360 px) PDF sekmesinden PDF sayfa üstünde açılır, yeni sekme açılmaz (yedek bağlantı hariç); Escape/kapat ile karara dönülür.
- 360 ve 1440 px'te uzun bir kararın metninin sonunda "Düzelt" görünür ve basınca form görünüme gelip ilk alan odaklanır.
- pnpm lint/typecheck/test/build/format:check yeşil; e2e yeni senaryolar geçer; 360 px'te yatay kaydırma yok.
