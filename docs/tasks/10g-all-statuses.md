# Görev 10g: tüm kararlar durumlarıyla görünür (bekleyen, onaylanan, reddedilen)

Durum: onaylandı (Orhan, 2026-10-05: "Reddedilen kararları göremiyorum. Onlar da görünüyor olmalı." ve "Onaylanan ve bekleyen de dahil."). Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `services/app/app/review.py`, `services/app/app/kb.py` (`queue`, `newest_extractions`, `reject_extraction`), `packages/models` (review şemaları), `docs/tasks/09-review-api.md`, `docs/tasks/10b-dashboard-skeleton.md`, `docs/tasks/10c-review-detail.md`, `docs/design/dashboard-v0.md`.
Skill'ler: `frontend-ui` (bağlayıcı), `task-pr-hygiene`, `db-migration` (yalnız şema değişikliği gerekirse; beklenen: gerekmez).

## Sorun

Kuyruk yalnız `analyzed` (karar bekleyen) kaynakları listeliyor (`kb.queue`: `status == analyzed`). Bir karar reddedilince ya da onaylanınca listeden düşüyor; "Sonuçlar" kartı yalnız sayıyı gösteriyor. Reddedilen bir kararı bulmanın, nedenini (ret notu) ve kimin reddettiğini görmenin yolu yok. Detay sayfası (`/kararlar/{id}`) reddedilen kararı zaten gösterebiliyor (`source_status`, `reviews`; aksiyonlar `analyzed` değilse kapalı), ama oraya ulaşan bir liste yok.

## Kapsam

1. **API: durum filtresi.** `GET /review/decisions`'a `status` parametresi: `pending` (varsayılan, bugünkü davranış), `approved`, `rejected`, `all` (üçü birlikte). Her öğe kendi durumunu (`source_status`) taşır. Mevcut filtreler (bant, mahkeme, sebep, dergi sayısı, arama) ve sıralama her durumda çalışır.
    - `approved`, `rejected` ve `all` listelerinde incelenmiş öğe ayrıca son inceleme bilgisini taşır: `reviewed_at`, `reviewer_name`, `review_decision` (`approve` / `edit` / `reject`) ve ret notu (`note`, yalnız ret ve not varsa). Tek sorgu (N+1 yok): her kaynağın son `review` satırı lateral join ya da `DISTINCT ON` ile.
    - `approved` / `rejected`'te varsayılan sıralama en yeni inceleme önce (`reviewed_desc`); `all`'da varsayılan `score_asc`, bekleyenler incelenmemiş olduğu için `reviewed_desc`'te sona düşer; `score_asc` / `score_desc` da seçilebilir. Bekleyende `reviewed_desc` anlamsız: reddedilir (422) ya da yok sayılır, seçimini testle sabitle.
    - `bulk-approve` ve `summary` davranışı değişmez (toplu onay yalnız bekleyen + yüksek bant). `summary`'deki `approved` / `rejected` sayıları liste toplamıyla tutarlı olmalı (aynı tanım: kaynak durumu).
    - Pydantic şeması `packages/models`'te, OpenAPI tipleri yeniden üretilir (`frontend-ui`: generated types; generated dosya biçimlendirilmez).
    - Testler: her durum, filtrelerle birleşim, son incelemenin seçimi (bir kaynakta birden çok review), ret notu, sayfalama toplamı, yetkisiz erişim.
2. **Dashboard: durum sekmeleri.** Kuyruk sayfasının üstünde dört sekme: **Bekleyen** (sayı), **Onaylanan** (sayı), **Reddedilen** (sayı), **Tümü** (sayı). Sayılar `summary`'den. Seçim URL'de (`?durum=onaylanan|reddedilen|tumu`; bekleyen varsayılan, parametresiz). **Tümü**'nde her satır/kartta durum rozeti (Bekliyor / Onaylandı / Düzeltilerek onaylandı / Reddedildi) var; inceleme sütunu bekleyende boş. Sekmeler erişilebilir (bağlantı tabanlı gezinme olduğu için `nav` + `aria-current="page"`; ARIA tab deseni değil), 360 px'te taşmadan sığar.
    - "Sonuçlar" kartındaki Onaylanan / Reddedilen sayıları ilgili sekmeye bağlantı olur.
    - Bekleyen sekmesi bugünkü ekranla aynı (toplu onay, özet kartları dahil).
    - Onaylanan / Reddedilen / Tümü sekmelerinde: toplu onay düğmesi yok; başlık ve alt başlık duruma göre ("N karar reddedildi"); filtreler ve sıralama (en yeni inceleme önce varsayılan) var; özet kartları gizli ya da yalnız bekleyen için olduğu açık.
    - Liste (tablo ve kart görünümü, 10e kırılımları aynen): bu sekmelerde ek sütun / satır: **İnceleme** (tarih, inceleyen) ve reddedilende **Ret notu** (kısaltılmış, tamamı detayda). Onaylananda "düzeltilerek onaylandı" ayrımı rozetle.
    - Boş durum metinleri her sekmeye göre.
3. **Detay sayfası.** Reddedilen / onaylanan karar açıldığında üstte durum şeridi: "Reddedildi · <tarih> · <inceleyen>" ve ret notu; aksiyon çubuğu yok (bugün de yok, doğrula). Detaydan geri dönüş bağlantısı geldiği sekmeye döner (URL parametresi korunur). J/K (önceki/sonraki) bu sekmenin listesinde gezinir.
4. **Metinler** `messages/tr.json`'da; bileşende sabit metin yok.

## Kapsam dışı

- Reddedilen kararı yeniden açma / reddi geri alma (ayrı karar: kim yapabilir, iz kaydı nasıl tutulur). Orhan isterse ayrı görev.
- Onaylananın geri alınması, yayından kaldırma.
- Dışa aktarma (CSV).

## Kabul kriterleri

- `pnpm lint typecheck test build format:check` ve backend `ruff`, `mypy`, `pytest` yeşil; OpenAPI tipleri güncel (CI kontrolü).
- Birim / API testleri modüle göre (ör. `test_review.py`, `queue-tabs.test.tsx`); mevcut testler gevşetilmez.
- e2e: bir kararı reddet, bir kararı onayla; Reddedilen sekmesinde ret notu ve inceleyen adıyla, Onaylanan'da onaylananı, Tümü'nde üç durumu rozetleriyle gör; detayına git, geri dön; mobilde de sekmeler kullanılabilir.
- Themis tarayıcıda doğrular (360 / 768 / 1440): yatay taşma yok, dokunma hedefi 44 px, bekleyen sekmesi değişmedi.
