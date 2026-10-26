# Görev 04c: ortağın düzeltmeleri ekranda ve yeniden onayda kaybolmasın

Durum: onaylandı, uygulanıyor (Themis, 2026-10-26).
Sahip: Themis (uygulayan Claude Code).
Onay: Orhan (2026-10-26, Telegram: "bu durum için gerekli değişikliği yap düzgünce test et emin ol").
Bağlam: `docs/tasks/04b-body-start-markers.md` (parser 6, `refresh_text`), `docs/tasks/09-review-api.md`, `services/app/app/review.py` (`get_decision`, `list_decisions`, `act`), `services/app/app/kb.py` (`newest_extractions`, `queue`, `publish_decision`, `approve_extraction`, `reopen_extraction`), `services/app/app/loaders/refresh_text.py`.
Skill'ler: `task-pr-hygiene`, `db-migration` (migration gerekmiyorsa yazma).

## Sorun

Ortak (2026-10-26, WP) Yargıtay 21. HD E.2012/1941 kararında karar no'yu 2011/2624 → 2012/2624 düzeltmişti (24.10, `review.decision = edit`, `edits = {"karar_no": "2012/2624"}`). PR #75 (parser 6) canlıya alındıktan sonra panelde yine 2011/2624 görüyor.

Canlı ölçüm (Themis, 2026-10-26):
- Canlı `decision` satırı doğru: `karar_no = 2012/2624`. Veri kaybı yok.
- Ama ayrıntı ekranı `fields = extraction.fields` döndürüyor (kaynağın en yeni extraction'ı, ham parser çıktısı); `review.edits` üstüne bindirilmiyor. Liste de en yeni extraction'ın üretilmiş sütunlarını (`esas_no`, `karar_no`, `decision_date`, `chamber`, `court`...) gösteriyor. Düzenleme formu da ham değerle açılıyor; ortak "düzelttim ama geri gelmiş" görüyor.
- Etki: düzenlemesi olan 45 kaynağın (hepsi onaylı) **24'ünde** en yeni extraction'ın alanları düzenlenen değerden farklı; yani ekranda yanlış değer görünüyor. Düzenlenen alanlar: outcome 35, text_completeness 11, karar_no 9, esas_no 6, decision_date 5, court 3, court_level 3, jurisdiction 2, keywords 2, chamber 2, source_chamber 1, related_articles 1.

İkinci, gizli risk: düzenlemeler yalnız düzenlemenin yazıldığı review'da duruyor. Bir karar "Geri al" (reopen) ile incelemeye döner ve düz "Onayla" ile tekrar onaylanırsa `publish_decision` yalnız o son review'un `edits`'ini (boş) uygular; önceki düzeltmeler canlı satırdan da düşer. `refresh_text` de yalnız `live.review_id`'nin edits'ine bakıyor, aynı durumda düzeltilmiş `outcome`/`text_completeness`'i ezebilir. Canlıda 3 kaynakta reopen var.

## Hedef

Bir kaynağın **geçerli düzenlemeleri** tek bir yerden hesaplansın ve her yerde aynı uygulansın: ekranda (ayrıntı + liste + form), yayımlamada ve metin yenilemede. Ortak bir alanı bir kez düzelttiyse o alan, yeni parser sürümü ya da geri al / yeniden onayla sonrasında da düzeltilmiş kalır, ta ki ortak onu tekrar değiştirene kadar.

## Kapsam

1. **Tek kaynak fonksiyon** (`app.kb` içinde, ör. `source_edits(session, source_id) -> dict`): kaynağın tüm extraction'larına ait `edit` review'larının `edits`'i, `reviewed_at, id` sırasıyla birleştirilmiş hâli (sonraki aynı alanı ezer). Reddetme düzenleme taşımaz. Liste için aynı kuralın SQL karşılığı (aşağıda 3).
2. **Ayrıntı ekranı** (`GET /review/decisions/{id}`): `fields = {**extraction.fields, **source_edits}`. Yanıta ham değerleri kaybetmemek için `edited_fields: list[str]` (düzenlenmiş alan adları) ekle; `ReviewDetail` modeli, OpenAPI ve `services/dashboard-web/src/lib/api/schema.d.ts` güncellenir. Form artık düzeltilmiş değerle açılır; aynı değeri tekrar göndermek boş düzenleme olur (mevcut davranış).
3. **Liste** (`GET /review/decisions` ve arama `q`): gösterilen `court`, `chamber`, `esas_no`, `karar_no`, `decision_date`, `decision_kind`, `journal_issue` düzenleme varsa düzenlenen değer olsun. `q` araması düzeltilmiş `esas_no`/`karar_no` ile de bulsun (ortak 2012/2624 diye arayınca bulmalı). Uygulama: `newest_extractions`/`queue`'ya kaynak başına birleştirilmiş edits alt sorgusu (`jsonb_object_agg` ya da `jsonb` birleştirme, sonraki review kazanır) ve `coalesce(edits->>'alan', extraction.alan)`. Tarih tipi dönüşümüne dikkat (`decision_date` extraction'da `date`). Toplu onay sırası ve imleci (`sha256`) değişmez.
4. **Yayımlama** (`publish_decision`): `merged = {**extraction.fields, **source_edits(<bu review dahil>)}`; yani geri al → düz onay, önceki düzeltmeleri korur. Çakışma kontrolü (`act` içindeki `_live_conflict`) aynı birleşimi kullanır.
5. **Metin yenileme** (`refresh_text`): korunacak alanlar `live.review_id`'nin edits'i değil, `source_edits`'in anahtarları.
6. **Geri al** davranışı değişmez (canlı satırı kapatır); yalnız sonraki onay düzeltmeleri taşır.

## Kapsam dışı

- Canlı veride toplu düzeltme betiği: canlı `decision` satırları zaten doğru (ölçüldü). Reopen olan 3 kaynakta canlı satırın düzeltmeleri taşıyıp taşımadığını Themis merge sonrası kontrol eder; gerekirse ayrı iş.
- Ekranda "düzenlendi" rozeti gibi yeni UI öğeleri: `edited_fields` yalnız API'de; UI'da kullanmak ayrı karar (Orhan). Mevcut UI bileşenlerinde değişiklik gerekmiyorsa yapma; tipler güncellenir.
- Mevzuat inceleme (`review_statutes.py`): orada düzenleme yok.

## Kabul kriterleri

Testler modül adıyla (`test_review.py`, `test_kb.py`, `test_loaders_refresh_text.py`), Postgres'li:
- Düzenlenmiş (karar_no) ve onaylı kaynağa yeni parser sürümünde ham değerli yeni extraction eklenince: ayrıntı `fields.karar_no` düzeltilmiş değer, `edited_fields` içinde `karar_no`; liste satırı düzeltilmiş değer; `q=<düzeltilmiş karar no>` kaydı buluyor, ham değerle arama da (ham değer extraction'da kaldığı için) bulabilir ya da bulmaz: hangisi seçildiyse testte sabitlenir ve PR'da yazılır.
- İki ayrı edit review'u (farklı alanlar + aynı alan iki kez): birleşim doğru, son yazan kazanır.
- Düzenle → onay, geri al, düz onay: yeni canlı `decision` satırı önceki düzeltmeyi taşıyor.
- `refresh_text`: düzeltme önceki review'da (canlı satırın review'u değil) olsa bile o alana dokunmuyor.
- Reddedilen ve hiç düzenlenmemiş kayıtların ayrıntı/liste çıktısı değişmiyor (mevcut testler yeşil).
- `make lint`, `make typecheck`, `make test`; dashboard-web `pnpm typecheck`/`lint` (schema değiştiği için); CI yeşil.

## Canlıya alma (merge sonrası, Themis)

1. Deploy sonrası canlıda E.2012/1941 ayrıntısı ve listesi 2012/2624 gösteriyor.
2. Ölçüm sorgusu tekrar: "düzenlenmiş alanı ekranda farklı görünen kaynak" sayısı 24 → 0.
3. Reopen olan 3 kaynağın canlı satırını edits ile karşılaştır.
