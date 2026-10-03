# Görev 09: Karar inceleme ve onay API'si

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/data-model.md` §3 (`extraction`, `review`), §4 (durum makinesi, toplu onay), §5.2 (`decision`); `docs/tasks/05-decision-load.md` (güven skoru, mükerrer gruplar, `publish_decision`); `docs/tasks/08-auth.md` (`current_user`, `require_role`); `docs/decisions.md` 2026-10-03 (reviewer da toplu onay yapabilir).
Üstüne oturduğu iş: Görev 05 (6.317 karar `analyzed` + `extraction` + güven bandı), Görev 08 (kullanıcı ve oturum).

## Hedef

Dashboard'un ilk ekranı (Görev 10) için `app`'te HTTP API: onay bekleyen karar extraction'larını listelemek, birini ayrıntılı göstermek, onaylamak / düzelterek onaylamak / reddetmek ve yüksek güven bandını toplu onaylamak. Her işlem giriş yapmış kullanıcının adıyla `review` satırı yazar. Onay, Görev 05'teki `app.kb.publish_decision` ile `decision` satırına dönüşür (`verification = unverified`; atıfa açılma teyitten sonra).

## Kapsam

1. **Yer:** `services/app/app/review.py` (router + sorgular). Paylaşılan istek/yanıt şemaları `packages/models`'e (Görev 10 TypeScript tiplerini OpenAPI'den üretecek; her endpoint `response_model`'li). Router `main.py`'ye `include_router` ile eklenir.
2. **Yetki:** tüm endpoint'ler `require_role("reviewer")` (admin de geçer). Toplu onay dahil (Orhan, 2026-10-03).
3. **Kuyruk tanımı:** kategori `decision`, `source.status = analyzed`, kaynak başına **en yeni** extraction (`parser_name = decisions`). Bu sorgu bugün `app.loaders.decisions.approve_band` içinde; `review.py`'ye taşınır, `approve_band` ve API aynı fonksiyonu kullanır (tekrar yok).
4. **Endpoint'ler** (prefix `/review/decisions`):
   - `GET /review/decisions` → sayfalı liste. Filtreler: `band` (`high`/`medium`/`low`), `court`, `reason` (güven sebebi kodu), `journal_issue`, `q` (E/K no veya başlıkta basit `ILIKE`; tam metin arama bu görevde yok). Sıralama `score_asc` (varsayılan; en şüpheli önce) / `score_desc`, eşitlikte sha256. `limit` (varsayılan 50, en çok 200) + `offset`; yanıtta `total`. Öğe: extraction_id, source_id, başlık, court, chamber, esas_no, karar_no, decision_date, journal_issue, band, score, reasons, duplicate_group (varsa). Metin gövdesi listede yok.
   - `GET /review/decisions/summary` → bekleyen kayıt sayıları: banda göre, mahkemeye göre, en sık 15 sebep; ayrıca toplam onaylanan / reddedilen (`review` tablosundan, karar kategorisi).
   - `GET /review/decisions/{extraction_id}` → tek kayıt: tüm `fields` (full_text ve editorial_summary dahil), warnings, confidence, `raw_text_ref`, aynı mükerrer gruptaki diğer extraction'ların kısa özeti (id, band, score, metin uzunluğu), bu extraction'a yazılmış önceki review'lar. Kuyrukta değilse de (onaylı/reddedilmiş) gösterilir; yanıtta `source_status`.
   - `POST /review/decisions/{extraction_id}` gövde `{action: approve|edit|reject, edits?, note?}`:
     - `approve`: `review` (decision `approve`) + `publish_decision`.
     - `edit`: `edits` zorunlu; `review` (decision `edit`, `edits`) + `publish_decision` (fields + edits).
     - `reject`: `note` zorunlu (neden reddedildiği eval ve parser düzeltmesi için değerli); `review` (decision `reject`), `source.status = rejected`; `decision` yazılmaz.
     - Yanıt: review_id, (varsa) decision_id, yeni source_status.
     - Hatalar: extraction yok → 404; kaynak artık `analyzed` değil (başkası önce davrandı) veya extraction kaynağın en yenisi değil → 409; canlı (court, bam_region, chamber, esas_no, karar_no) çakışması → 409 + çakışan `decision.id`; geçersiz `edits` → 422. Her durumda yarım iş kalmaz (tek transaction).
   - `POST /review/decisions/bulk-approve` gövde `{band: "high", filters (listedekilerle aynı, band hariç), expected_count, limit?}`:
     - Yalnızca `band = high` kabul edilir; başka bant 422 (Görev 05: düşük/orta bant tek tek incelenir).
     - `expected_count`: ekranda görülen sayı. Sorgu anındaki eşleşen sayı farklıysa 409, hiçbir şey yazılmaz (kullanıcının görmediği kayıt onaylanmasın).
     - Bir çağrıda en çok `limit` kayıt (varsayılan ve tavan 500); yanıtta `published`, `conflicts` (extraction id listesi), `failed` (id + sebep), `remaining`. Her kayıt kendi savepoint'inde (bugünkü `approve_band` davranışı); bir çakışma koşuyu durdurmaz.
5. **`edits` doğrulaması:** Pydantic modeli; yalnızca şu alanlar düzenlenebilir: court, court_level, chamber, source_chamber, bam_region, decision_kind, esas_no, karar_no, decision_date (ISO), jurisdiction, related_articles, keywords, outcome, text_completeness. Enum alanları şema enum'larıyla, `outcome` Görev 05'teki ASCII listesiyle doğrulanır. `full_text` ve `editorial_summary` düzenlenemez. Bilinmeyen anahtar → 422.
6. **`review.reviewer_id` → `app_user.id` FK** (Alembic 0006): `NOT VALID` olarak eklenir; yeni satırlar zorunlu olarak gerçek kullanıcıya bağlanır, Görev 05'te CLI ile yazılmış eski satırlar doğrulanmaz. `--approve-band` CLI'ı da artık var olan bir kullanıcı ister: `--reviewer` UUID yerine `--reviewer-email`; bulunamazsa hata. Alembic NOT VALID'i ifade edemiyorsa `op.execute` ile; `alembic check` temiz kalmalı.
7. **Testler** (`test_review.py`; taşınan sorgu için `test_loaders_decisions.py` güncellenir): DB gerektirenler `DATABASE_URL` yoksa skip. En az:
   - Liste: yalnızca kaynak başına en yeni extraction; filtreler (band, court, reason, q) ve sıralama; `total` doğru; limit tavanı.
   - Approve → `decision` satırı, `review.reviewer_id` = giriş yapan kullanıcı, source `approved`.
   - Edit → `decision` alanları edits'i yansıtır; geçersiz enum / bilinmeyen anahtar / `full_text` düzenleme → 422.
   - Reject `note`'suz → 422; notlu → source `rejected`, `decision` yok.
   - Aynı kayda ikinci işlem → 409. Eski extraction'a işlem → 409. Canlı anahtar çakışması → 409 + çakışan id, hiçbir satır yazılmamış.
   - Bulk: `band=medium` → 422; `expected_count` uyuşmazlığı → 409 ve hiçbir şey yazılmaz; `limit` ve `remaining`; bir çakışma diğerlerini durdurmaz.
   - Giriş yok → 401 (cookie'li POST'ta JSON değilse 415 zaten Görev 08'de test edildi, tekrar etme).
   - FK: var olmayan reviewer ile `review` yazılamaz; 0006 migration'ı eski (FK'siz) satırları olan bir DB'de çalışır.

## Kapsam dışı

- Dashboard UI (Görev 10).
- `published` durumu, embedding, tsvector, chunk.
- Onay geri alma / `withdrawn` akışı (sonraki görev; şimdilik admin DB'den).
- Mevzuat ve diğer kaynak türlerinin incelemesi (tasarım genel kalsın ama yalnızca karar uygulanır).
- Tam metin arama (`/kb/search`), resmî kaynak teyidini API'den tetikleme.
- Org bazında görünürlük.

## Kabul kriterleri (Themis koşar)

- [ ] `make lint`, `make typecheck`, `make test` temiz; CI yeşil (DB testleri CI'da Postgres ile).
- [ ] Madde 7'deki her test maddesi bir testle karşılanır; PR'da madde → test eşlemesi.
- [ ] `/openapi.json` tüm yeni endpoint'leri tipli yanıt şemalarıyla içerir (CI'da bir test ile).
- [ ] `approve_band` CLI'ı ve API toplu onayı aynı sorgu + yayın fonksiyonunu kullanır (kod okunarak teyit).
- [ ] Liste endpoint'i 6.317 kayıtlık DB'de (Orhan'ın Mac'i) < 300 ms; ölçüm PR'da Orhan'dan ya da `EXPLAIN` çıktısıyla. Gerekirse indeks eklenir (Alembic 0006 içinde).

## Açık sorular (Orhan)

- Ret için not zorunlu olsun mu? Öneri: evet, kısa bir cümle bile yeter; parser hatalarını bulmamızı sağlar.
- Toplu onay tavanı 500 kayıt/çağrı uygun mu? (Ekran gerekirse arka arkaya çağırır.)

## Notlar Claude Code için

- Önce `app/kb.py`, `app/loaders/decisions.py` (`approve_band`), `app/loaders/confidence.py`, `app/auth.py`, `app/models/` ve `tests/conftest.py` oku; enum ve tablo adlarını tahmin etme.
- `publish_decision`'ın sözleşmesini değiştirme; gerekiyorsa çağıran tarafta sar.
- Spec dışı ekleme yapma. Testler modül adına göre dosyalanır (`test_review.py`). Ölü kod bırakma.
- Commit et; push'u Themis yapar.
