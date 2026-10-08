# Görev 11c: mevzuat madde inceleme ekranı

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/tasks/11-statute-versioning.md` (11a çizelgesi, 11b yükleme / yayın / `as_of`), `docs/tasks/09-review-api.md` ve `10c-review-detail.md` (karar inceleme kalıbı), `docs/data-model.md` §5.1.
Skill'ler: `task-pr-hygiene`, `db-migration` (gerekirse), `frontend-ui` (bağlayıcı).
Önce: 11b merge edilmiş olmalı (#48).

## Hedef

Reviewer (Baran, İbrahim, Orhan) 4857 ve 5510'un her maddesini **zaman çizgisi** olarak görür: hangi tarihten hangi tarihe hangi metin geçerliydi, değişikliği hangi kanun yaptı ve yürürlük tarihi nereden geldi, metni elde olmayan aralıklar nerede. Maddeyi onaylar (yayına girer, `as_of` sorgusunda görünür) ya da notla reddeder. Yüksek bandı toplu onaylar. Yayına giren madde sistemin "olay tarihindeki metin" cevabının tek kaynağıdır (md. 4, md. 25).

Görev iki PR: **11c-1 API** (`services/app`, `packages/models`), **11c-2 ekran** (`services/dashboard-web`).

## 11c-1: inceleme API'si

Karar inceleme API'sinin (`/review/decisions`) kalıbı birebir izlenir; yetki aynı (`reviewer`/`admin` rolü), hata kodları `errors.py`'de, metin yok.

1. `GET /review/statutes`: madde kuyruğu. Filtreler: `statute` (4857/5510), `band`, `status` (`pending` = yayına girmemiş ve reddedilmemiş en yeni extraction, `approved`, `rejected`, `all`), `q` (madde no ya da kenar başlığında arama, Türkçe büyük/küçük harf duyarsız), sıralama kanun + `ordinal`. Sayfalama karar kuyruğuyla aynı. Satır: extraction id, kanun, madde no, kenar başlığı, band + sebepler, sürüm sayısı, gap sayısı, son snapshot tarihi, durum.
2. `GET /review/statutes/summary`: kanun × band × durum sayıları (karar özetinin karşılığı).
3. `GET /review/statutes/{extraction_id}`: detay. Başlık (kanun no + adı, madde no, kenar başlığı), band + sebepler + uyarılar, **çizelge** (sürümler ve gap'ler tarih sırasıyla tek listede: sürümde `text`, `heading`, `valid_from`, `valid_to`, `change_kind`, `amending_ref`, `evidence`, `footnotes`, `warnings`; gap'te `from`, `to`, `reason`, `known_amendments`, metin yok), snapshot listesi (dosya adı, tarih), son snapshot tarihi, önceki incelemeler, yayın durumu, aynı maddenin yayındaki eski extraction'ı varsa ona bağlantı. Karar kuyruğundaki bir extraction id'si 404 döner (ve tersi).
4. `POST /review/statutes/{extraction_id}`: `{action: approve | reject, note?}`. Ret notu zorunlu. Onay `kb.approve_statute_article`; ret yeni `kb.reject_statute_article` (review satırı, yayın yok; reddedilen extraction kuyrukta `rejected`). Düzelterek onay **yok** (çizelge elle düzenlenmez; hatalı çizelge reddedilir, düzeltme 11a koduna / kayda gider). Çakışma: aynı extraction'ı iki reviewer işlerse ikincisi 409 `review_conflict`; eski extraction 409 `review_conflict`.
5. `POST /review/statutes/bulk-approve`: yalnız `band = high`, karar toplu onayıyla aynı sözleşme (`expected_count`, `limit` en çok 100, `next_cursor`, `bulk_count_changed`). İç mantık `kb.unpublished_statute_articles` ile tek yerde (CLI `--approve-band` ile paylaşılır).
6. Kaynak durumu (`source.status`): ilk madde yayına girince `approved`. Reddedilen madde kaynağı reddetmez (kanun tek kaynak, madde ayrı inceleme birimi).
7. **Demo verisi:** `infra/demo/`'ya küçük bir mevzuat fixture'ı (ör. 4857'den 6-8 madde: high/medium/low, gap'li, mülga, ek/geçici; kamu metni) ve demo sıfırlama betiğinin onu da yüklemesi. Ekran testleri ve ekran görüntüleri buna dayanır.
8. Testler (`test_review_statutes.py`, `test_kb.py`): kuyruk filtreleri, detay şekli (gap'te metin yok), onay → `as_of` artık `found`, ret → kuyrukta `rejected`, `as_of` hâlâ `not_published`, toplu onay döngüsü, karar/mevzuat id ayrımı, yetki.

## 11c-2: ekran

`frontend-ui` skill'i bağlayıcı: UI'da DB yok, OpenAPI tipleri, design token, `messages/tr.json`, responsive (360 / 768 / 1440, 360 px'te yatay kaydırma yok, dokunma hedefi 44 px).

1. **Navigasyon:** yan menüye ve mobil menüye "Mevzuat" (kararların yanında). Kuyruk `/mevzuat`, detay `/mevzuat/[extractionId]`. Kararlar ekranı değişmez.
2. **Kuyruk** `/mevzuat`: kanun sekmeleri (4857 İş Kanunu / 5510 SGK Kanunu), durum sekmeleri, band filtresi, arama; masaüstünde tablo, mobilde kart. Özet kartı (band dağılımı, bekleyen / yayında / reddedilen). Kart / satır: "m. 18 · Feshin geçerli sebebe dayandırılması", band rozeti, "3 sürüm · 1 boşluk". `band = high` seçiliyken toplu onay düğmesi; diyalog ve döngü kararlardaki bileşenlerle **ortak** (genelleştir, kopyalama).
3. **Detay** `/mevzuat/[extractionId]`:
   - Üst: "4857 · m. 18 · Feshin geçerli sebebe dayandırılması", band + sebepler (gündelik dille: ör. "iki kopya arasında birden fazla değişiklik var, aradaki metin bilinmiyor"), uyarılar, "Metin {tarih} tarihli kopyaya kadar güncel" notu.
   - **Zaman çizgisi:** dikey (mobilde de dikey), her parça bir satır: tarih aralığı ("10.06.2003 → 15.09.2014", son sürümde "→ bugün"), tür rozeti (ilk metin / değişik / ek / mülga), değiştiren kanun ("6552 sayılı Kanun, yürürlük 11.09.2014"). **Boşluk** parçası görsel olarak farklı (kesikli çerçeve, "Bu aralıkta metin elde yok" + bilinen değişiklikler listesi), metin göstermez.
   - Seçili sürüm paneli: tam metin, kenar başlığı, dipnotlar (ayrı kutu, "dipnot" etiketi), dayanak (`evidence`: hangi kopyalar, hangi not, yürürlük tarihinin kaynağı: kayıt / istisna / tablo). **Önceki sürümle fark**: kelime düzeyinde, eklenen / silinen işaretli (masaüstünde yan yana, mobilde alt alta). Fark hesabı istemcide, küçük bir saf fonksiyon (`lib/word-diff.ts`, testli); yeni bağımlılık gerekiyorsa gerekçesi PR'da.
   - **Tarih sorgusu kutusu:** "Bu madde şu tarihte nasıldı?" tarih seçici; çizelgeden (detay cevabındaki liste) aynı `as_of` kuralıyla ilgili parçayı seçer ve vurgular (yarı açık aralık, `gap` / yürürlükte değil / bulunamadı durumları). Kural tek yerde: `lib/statute-as-of.ts`, 11a'daki saf `as_of` ile aynı davranış; testleri 11a altın setinden birkaç sorgu.
   - Aksiyonlar (yalnız `pending`): Onayla, Reddet (not zorunlu, diyalog). Başarıda bildirim + aynı filtrelerde sıradaki bekleyen maddeye geçiş. Hatalar koddan (`review_conflict`). Klavye kısayolları karar ekranındaki gibi.
   - Önceki incelemeler ve yayın durumu.
4. Testler (Vitest + Testing Library): kuyruk (filtreler URL'de, mobil kart), zaman çizgisi (gap metin göstermez), fark fonksiyonu, `statute-as-of` (sınır günleri), aksiyon gövdeleri, ret notu zorunluluğu, toplu onay ortak bileşenin iki ekranda çalışması.

## Kapsam dışı

- Çizelgeyi ekrandan düzeltme (sürüm tarihi / metin elle değiştirme). Hatalı madde reddedilir; düzeltme 11a koduna ya da `amending_acts.toml`'a gider.
- Snapshot PDF'ini ekranda gösterme (mevzuat PDF'leri yayın sunucusunun arşivinde yok; metin zaten çizelgede).
- Dipnot kanıtından sürüm tarihleme (11a raporunda ölçüldü, ayrı iş).
- Agent'ın `as_of` kullanımı (Faz 2).

## Kabul kriterleri (Themis koşar)

11c-1:
1. Lint / typecheck / test yeşil; DB testleri yerel Postgres'te ve CI'da koşar.
2. Gerçek `statutes.jsonl` yerel DB'ye yüklenir; kuyruk 378 madde, özet sayıları yükleyici raporuyla tutar; bir madde onay → `GET /statutes/...?as_of=` `found`; bir madde ret → `not_published`.

11c-2:
1. CI yeşil (Python + pnpm).
2. Demo yığınında uçtan uca: kuyruk → detay → zaman çizgisi → tarih sorgusu (found / gap) → onay → sıradaki madde; ret; yüksek bantta toplu onay. 360 / 768 / 1440 ekran görüntüleri PR'da, yatay taşma 0.
3. `frontend-ui` grep kontrolleri (DB yok, sabit renk yok, sabit metin yok) geçer.

## Yayına alma (Themis, 11c-2 merge'ünden sonra)

1. Dokploy otomatik deploy (main'e merge); sağlık kontrolü.
2. Gerçek `statutes.jsonl` yayın DB'sine yüklenir (onaysız; `--approve-band` kullanılmaz). Bütün maddeler `pending` olarak kuyruğa düşer; onayı ortaklar verir.
3. Smoke: geçici kullanıcıyla `/mevzuat` açılır, bir detay ekranı yüklenir; kullanıcı silinir.
