# Görev 10l: AYM bireysel başvuru: Başvuru No + tarih

Durum: uygulandı, PR Orhan'ın onayında (Themis, 2026-10-15). Issue: #71. Onay: Orhan (2026-10-15, Telegram: "fix e başla").
Bağlam: `services/app/app/loaders/confidence.py`, `services/dashboard-web/src/components/review-detail/fields-card.tsx` (`esasDisplay`), `src/components/review-queue/queue-table.tsx`, `messages/tr.json` (`missing_esas_no`, `missing_karar_no`, `esas`, `karar`), `services/app/app/models/decision.py` (`decision_kind`).
Skill'ler: `frontend-ui` (bağlayıcı), `task-pr-hygiene`.

## Sorun

AYM (Anayasa Mahkemesi) bireysel başvuru kararlarında Esas no ve Karar no yoktur. Bu kararlar Başvuru No + karar tarihi ile anılır (ör. "B. No: 2014/19081, 1/2/2017"). Parser bunları doğru ayırıyor (`fields.decision_kind = "bireysel_basvuru"`, başvuru no `esas_no`'da, `karar_no` boş). Ama:
- Panel başvuru numarasını E/K alanlarında gösteriyor ve boş Karar no için "okunamadı" uyarısı çıkarıyor.
- Güven kuralı `missing_karar_no` (düşük bant) tetikliyor. Bireysel başvurular sırf numara "eksik" diye düşük banda düşüyor ve toplu onaya giremiyor.

Canlı (2026-10-15): AYM 34 kayıt; 28 bireysel başvuru (hepsinde tarih dolu, karar_no boş), 6 norm denetimi (E/K/tarih dolu).

## Kapsam

1. **Güven kuralı** (`confidence.py`): `court == "aym"` ve `decision_kind == "bireysel_basvuru"` ise
   - `missing_karar_no` tetiklenmez,
   - `missing_esas_no` yerine başvuru no (`esas_no` alanı) yoksa tetiklenir (kod adı aynı kalabilir ya da `missing_application_no` eklenir; hangisi seçildiyse gerekçesi özette),
   - karar tarihi zorunlu kalır.
   - Docstring'deki "AYM individual applications ... low" cümlesi güncellenir.
   - Kuralın nerede uygulandığı (`qa.CRITICAL_FIELDS` / `qa.applies`) mevcut kalıba uygun olsun; ingest paketinde değişiklik gerekiyorsa en küçük değişiklik.
2. **Mevcut kayıtlar:** canlıdaki extraction'ların `confidence`'ı yeni kurala göre yeniden hesaplanabilmeli. Mevcut bir yeniden hesaplama komutu/yolu varsa onu kullan; yoksa idempotent bir CLI/komut ekle (yalnız `confidence` kolonunu yazar, `review` tablosuna ve onaylı kayıtların alanlarına dokunmaz). Nasıl çalıştırılacağı özette ve görev dosyasında.
3. **Panel, detay** (`fields-card.tsx`): `court === "aym"` ve `decisionKind === "bireysel_basvuru"` ise Esas no ve Karar no satırları yerine tek satır "Başvuru No" (mono). Karar tarihi aynen. Düzenleme formunda da (varsa) aynı etiket. Diğer kararlar değişmez.
4. **Panel, kuyruk** (`queue-table.tsx`): aynı durumda "E. …" / "K. …" yerine "B. No: …". Kuyruk API'si `decision_kind`'ı döndürmüyorsa en küçük ek (API şeması + tip).
5. **Metinler** `messages/tr.json`: "Başvuru No", "B. No: {value}"; `missing_esas_no` / `missing_karar_no` açıklamalarındaki "AYM bireysel başvuru kararlarında numara olmayabilir ... Düşük bantta kalır" cümlesi artık doğru değil, düzelt.
6. **Testler** modül adıyla: confidence (bireysel başvuru karar_no'suz yüksek/orta bant alabiliyor; başvuru no yoksa düşük; norm denetimi değişmedi), detay/kuyruk bileşen testleri, varsa API testi.
7. 360 ve 1440 ekran görüntüsü: bireysel başvuru kararının detayı ve kuyruk satırı; bir norm denetimi kararının detayı (değişmediğini göstermek için).

## Kapsam dışı
- Parser'ın başvuru numarasını ayrı bir alana taşıması (veri modeli değişikliği).
- `2019/19836` / `2020/19836` mükerrer kontrolü (issue'da ayrı madde, veri incelemesi).

## Kabul kriterleri
- Bireysel başvuru detayında "Başvuru No 2014/19081" + tarih; E/K satırı yok, "karar no okunamadı" uyarısı yok.
- Kuyrukta "B. No: 2014/19081".
- Norm denetimi kararında E/K/tarih aynen.
- Bireysel başvuru yalnız numara eksik diye düşük banda düşmez; yeniden hesaplama yolu var ve onaylı kayıtların review'ına dokunmaz.
- Backend testleri + pnpm lint/typecheck/test/build/format:check yeşil.

## Notlar Claude Code için (uygulama)

- **Güven kuralı:** kod adları aynı kaldı. `court == "aym"` ve `decision_kind == "bireysel_basvuru"` kararında `missing_karar_no` hiç tetiklenmez; başvuru no `esas_no`'da durduğundan `missing_esas_no` "başvuru no yok" anlamına gelir (açıklaması `tr.json`'da). Norm denetimi ve yabancı mahkemeler değişmedi. `qa.CRITICAL_FIELDS` / `qa.applies` ve ingest paketi dokunulmadı: kural `confidence.reasons_of` içinde.
- **API:** `ReviewListItem.decision_kind` eklendi. Kuyruk `fields`'a dokunmadığı için `extraction.decision_kind` üretilmiş kolonu (migrasyon `0013`, `fields ->> 'decision_kind'`, STORED; tabloyu bir kez yeniden yazar) eklendi. `openapi.json` ve `schema.d.ts` güncel.
- **Mevcut kayıtların yeniden hesaplanması:** `python -m app.loaders.rescore [--dry-run]`. Her karar extraction'ının `fields` + `warnings`'inden güveni yeniden hesaplar, yalnız `extraction.confidence` kolonunu ve yalnız değişenler için yazar (ikinci çalıştırma 0 değişiklik); `review`, `fields` ve yayımlı `decision` satırlarına dokunmaz, onaylı kayıtlar onaylı kalır. Canlıda: migrasyondan (`alembic upgrade head`) sonra `app` konteynerinde önce `--dry-run`, sonra komutun kendisi.
- **Panel:** detay ve düzenleme formunda tek "Başvuru No" satırı (formda Karar no satırı yok); kuyruk tablosu, kart listesi ve toplu onay örnek listesinde "B. No: …".
