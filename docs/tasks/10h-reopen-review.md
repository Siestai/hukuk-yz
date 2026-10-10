# Görev 10h: onayı ya da reddi geri alıp kararı yeniden incelemeye açma

Durum: taslak (Orhan, 2026-10-10: "onaylanan karar detail sayfası açılınca tekrar onaydan çıkarma gibi bir buton. onaydan çıkarıp sonra tekrar gözden geçirebilirim ve sonra red edebilirim. red için de öyle. reddi iptal edip tekrar gözden geçirebilirim"). Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `services/app/app/kb.py` (`publish_decision`, `reject_extraction`, `_reviewed`, `lock_pending`, `approve_band`, `STATUS_GROUPS`), `services/app/app/review.py` (`act`), `services/app/app/models/common.py` (`ReviewDecision`, `RecordStatus`, `Review`), `services/app/app/models/decision.py` (`Decision`, canlı anahtar indeksi `superseded_at IS NULL`), `docs/tasks/09-review-api.md`, `docs/tasks/10c-review-detail.md`, `docs/tasks/10g-all-statuses.md` (kapsam dışı bıraktığı madde bu görev).
Skill'ler: `frontend-ui` (bağlayıcı), `db-migration` (enum değeri), `task-pr-hygiene`.

## Sorun

Bir karar onaylanınca ya da reddedilince geri dönüş yok: detay sayfası durum şeridini gösterir, aksiyon çubuğu kapanır. Yanlış onaylanan bir kararı reddetmenin ya da yanlış reddedileni onaylamanın yolu yok; tek çare veritabanına elle müdahale.

## Hedef

İnceleyici, onaylanan ya da reddedilen bir kararı detay sayfasından tek düğmeyle "yeniden incelemeye" alır. Karar bekleyen duruma döner, aksiyon çubuğu açılır ve normal akışla (onayla / düzelt / reddet) yeniden karara bağlanır. Hiçbir şey silinmez: eski karar kaydı ve eski inceleme satırları iz olarak kalır.

## Kapsam

1. **Şema: yeni inceleme türü.** `ReviewDecision`'a `reopen` değeri (Alembic `0009`: `ALTER TYPE review_decision ADD VALUE 'reopen'`; ORM ile tutarlılık testi `db-migration` skill'indeki gibi). Başka tablo / kolon yok.
2. **Servis: `reopen_extraction` (`kb.py`).**
    - Kaynağı kilitler (`publish_decision` ile aynı satır kilidi). Kaynak durumu `approved`, `published` ya da `rejected` değilse ve inceleme kaynağın en yeni extraction'ına ait değilse `StaleExtraction` (API'de 409 `review_conflict`).
    - `review` satırı yazar: `decision=reopen`, `note` isteğe bağlı (en fazla mevcut not sınırı), `reviewer_id` işlemi yapan.
    - Onaylıysa: canlı `decision` satırını **silmez**, `superseded_at = now()` ile emekliye ayırır (bitemporal kural). Böylece canlı anahtar indeksi boşalır, yeniden onayda yeni satır yazılabilir. `decision_verification` geçmişi eski satırda kalır; yeniden onaylanan karar `unverified` başlar (mevcut `publish_decision` davranışı, değişmez).
    - Kaynak durumu `analyzed`'a döner. Sonraki onay / ret mevcut `_reviewed` → `lock_pending` yolundan geçer, ek kod gerekmez.
    - Hepsi tek savepoint'te; hata olursa iz kalmaz (`_reviewed` ile aynı desen).
3. **Toplu onay yeniden açılanı almaz.** Yeniden incelemeye alınmış (son incelemesi `reopen` olan) bir karar, bandı yüksek olsa da `bulk-approve`'a ve CLI `approve_band`'e girmez: insan bilerek geri aldı, yine tek tek bakılmalı. Kuyrukta bu öğeler bir rozetle ("Yeniden incelemede") görünür ve `summary`'de bekleyen sayısına dahildir.
4. **API.** `POST /review/decisions/{extraction_id}` aksiyonlarına `reopen` eklenir (`ReviewActionRequest`, `packages/models`; OpenAPI tipleri yeniden üretilir). Yanıt: `source_status: "analyzed"`, `decision_id: null`. Yetki: `reviewer` ve `admin` (onay / ret yapan herkes geri alabilir; Görev 08 rol modeli). Hata kodları: 404 bilinmeyen, 409 zaten bekleyen ya da eski extraction, 403 rolsüz.
    - `GET /review/decisions/{id}` inceleme geçmişinde `reopen` satırları görünür; liste öğesinin son inceleme alanları (`review_decision`) `reopen` değerini taşıyabilir.
5. **Dashboard: detay sayfası.**
    - Onaylanan kararın durum şeridinde **"Onaydan çıkar"**, reddedilende **"Reddi geri al"** düğmesi.
    - Tıklanınca onay penceresi: ne olacağını tek cümleyle söyler ("Karar bekleyen duruma döner; onaylı kayıt geçmişte saklanır, silinmez.") + isteğe bağlı not alanı + "Yeniden incelemeye al" / "Vazgeç". Erişilebilir dialog (odak tuzağı, Escape, odak düğmeye geri döner).
    - Başarıda sayfa yenilenir: durum şeridi gider, aksiyon çubuğu (onayla / düzelt / reddet) açılır, inceleme geçmişinde "Yeniden incelemeye alındı · tarih · kişi · not" satırı. 409'da sayfa yenilenir ve "Bu karar başka biri tarafından değiştirildi" mesajı.
    - Liste sekmeleri (10g): öğe Onaylanan / Reddedilen'den Bekleyen'e geçer; Tümü'nde rozeti "Yeniden incelemede".
    - Mobil kurallar aynen (360 px taşma yok, dokunma hedefi 44 px).
6. **Metinler** `messages/tr.json`'da; bileşende sabit metin yok.

## Kapsam dışı

- Mevzuat (Görev 11c) madde onayını geri alma. Aynı desen uygulanabilir; Orhan isterse ayrı görev.
- Yetkiyi yalnız admin'e kısıtlama ya da not zorunluluğu (Orhan aksini söylerse spec güncellenir).
- Teyit geçmişini (`decision_verification`) yeni karar satırına taşıma.
- Toplu geri alma.

## Kabul kriterleri

- `pnpm lint typecheck test build format:check` ve backend `ruff`, `mypy`, `pytest` yeşil; OpenAPI tipleri güncel (CI kontrolü). Migration ileri / geri test edilir.
- Testler modüle göre (`test_kb.py`, `test_review.py`, ilgili `*.test.tsx`); mevcut testler gevşetilmez. En az şunlar:
    - onaylı → geri al → `decision.superseded_at` dolu, kaynak `analyzed`, `review(reopen)` satırı; sonra reddet → kaynak `rejected`;
    - reddedilen → geri al → onayla → yeni canlı `decision` satırı, eski satır duruyor, canlı anahtar çakışması yok;
    - zaten bekleyen kararda geri al → 409; iki eşzamanlı geri alma → biri 409;
    - yeniden açılan yüksek bantlı karar `bulk-approve` sonucuna girmiyor;
    - yetkisiz kullanıcı 401 / 403.
- e2e: bir kararı onayla, detayda "Onaydan çıkar", reddet; başka bir kararı reddet, "Reddi geri al", onayla; sekmelerde doğru yerde görünüyor, geçmişte reopen satırı var.
- Themis tarayıcıda doğrular (360 / 768 / 1440): düğme ve dialog taşmıyor, dokunma hedefi 44 px.
