# Paket A: Test kaynakları ve arama indeksi

Durum: onaylı (Orhan, 2026-11-22). Önce bu paket, sonra Paket B.
Bağlam: `docs/tasks/11-statute-versioning.md`, `14-kb-search.md`, `17-agent-v1.md`, `18-chat-wiring.md`,
`docs/architecture.md`, `docs/decisions.md`, `00-README.md` (K1).
Skill'ler: `task-pr-hygiene`, `db-migration`.

## Hedef

Ajan TEST aşamasında gerçek kaynak okuyabilsin: 4857, 5510, 6356, 1475 m.14, 7036 maddeleri ve iki SGK genelgesi
(2018/38, 2020/8) KB'de; `high` + `medium` bantlı onaysız maddeler K1 kuralıyla okunur; canlıda arama indeksi kurulu.

## Mevcut durum (koddan, 22.11)

- `hukuk-ingest statutes` yalnız 4857 / 5510'u tanır (`packages/ingest/hukuk_ingest/statutes/run.py`, `_NUMBER_RE`).
  Ham dosyalar `data/drive/Mevzuat/Kanunlar/` (6356, 7036, `1475 sayılı (mülga) İş Kanunu’nun 14. maddesi.pdf` var),
  genelgeler `data/drive/Mevzuat/Genelge/` (`2018_38 ...pdf`, `2020-08 Genelge İdari Para Cezaları.pdf`).
- `app.loaders.statutes` maddeleri `extraction` olarak kuyruğa yükler; `statute` satırı yalnız onayda yazılır.
- `/kb/search`: `KB_SEARCH_INCLUDE_UNREVIEWED` açıksa onaysızları `analyzed` etiketle döner, ama **bant ayrımı yok** (low da gelir).
- `/statutes/{number}/articles/{no}?as_of=` yalnız yayımlanmış maddeyi okur; onaysız madde 404.
- Ajan `read_article` sonucuna sabit `review_status="approved"` yazıyor (`services/agent/agent/kb.py`): onaysız okuma
  gelince bu yanlış etiket olur, düzeltilmeli.
- `admin_act` / `admin_act_version` tabloları var, genelge yükleyicisi yok.
- `app.loaders.chunks` indeksi kurar (embedding OpenAI `text-embedding-3-large`, 1024; `OPENAI_API_KEY`).

## Kapsam ve alt görevler

| # | Alt görev | Subagent | Bağımlılık | Paralel |
|---|---|---|---|---|
| A1 | Test kaynak politikası (K1) | implementer | - | A2, A3 ile |
| A2 | Statute parser'ı genelleştir + 6356, 1475 m.14, 7036 | implementer | - | A1, A3 ile |
| A3 | Genelge (admin_act) yükleyicisi: 2018/38, 2020/8 | implementer | - | A1, A2 ile |
| A4 | Ajan okuma yolu: onaysız okuma, doğru etiket, künye eşleme | implementer | A1 | - |
| A5 | Yerel uçtan uca: yükle + indeks + SB-001 duman testi | orkestratör + eval-runner | A1-A4 | - |
| A6 | Canlı runbook (Orhan onayıyla) | orkestratör | A5 merge | - |

Her alt görev ayrı commit; A1-A4 tek PR ya da iki PR (A1+A4, A2+A3) olabilir, orkestratör karar verir.

### A1: Test kaynak politikası

- Tek ayar: `KB_TEST_SOURCE_BANDS` (varsayılan boş = yalnız onaylı; TEST'te `high,medium`). Eski
  `KB_SEARCH_INCLUDE_UNREVIEWED` bununla birleşir ya da ona eşlenir; iki ayrı anahtar kalmaz (geri uyumu PR'da yaz).
- `/kb/search`: onaysız sonuç yalnız bandı listedeyse; `low` hiçbir zaman. Sonuçta `review_status="analyzed"` + `band`.
- `/statutes/{number}/articles/{no}?as_of=`: yayımlanmış madde yoksa ve ayar açıksa, en yeni `extraction`'ın zaman
  çizelgesinden `as_of` sürümünü döner; yanıtta `review_status` ve `band`. Komşu fıkra davranışı yayımlanmışla aynı.
- `rejected` kaynak asla dönmez.
- `.env.example` ve `docs/deploy.md`'ye ayar ve K1 açıklaması.
- `docs/decisions.md`'ye K1 (tarih, Orhan, "açık yayından önce yeniden karar").

### A2: Statute parser'ı genelleştir

- Kanun numarası sabit regex yerine kayıttan (registry): her kanun için dosya kalıbı, ad, `amending_acts.toml` girdisi.
- 6356 ve 7036: tek anlık görüntü (snapshot) varsa zaman çizelgesi tek sürüm; `valid_from` bilinmiyorsa
  bilinmiyor olarak kalır ve güven bandı buna göre düşer (uydurma tarih yok, md.4). Mevzuat.gov.tr konsolide metninin
  sonundaki "yürürlüğe giriş tarihlerini gösterir liste" varsa önce o okunur (Görev 11 dersi).
- 1475: yalnız m.14 (mülga kanunun yürürlükte kalan maddesi); kayıtta bu açıkça işaretli.
- Altın test: her yeni kanun için 3-5 madde metni resmi kaynakla birebir (golden), madde sayısı ve numaralar.
- 4857 / 5510 çıktısı değişmez (mevcut golden testler yeşil; `PARSER_VERSION` değişirse nedenini PR'da yaz).

### A3: Genelge yükleyicisi

- `python -m app.loaders.admin_acts <jsonl>`: genelge → `source` (category `admin_act`) + bölüm/madde düzeyinde
  `extraction`; idempotent (sha256 + içerik hash), onaysız kuyruğa düşer, güven bandı hesaplanır.
- Bölme: genelgenin numaralı başlıkları (ör. 2020/8 "2.6.2.5"). Ajan künyesi `2020/8 m.2.6.2.5` biçiminde okunabilmeli.
- Taranmış (metin katmanı olmayan) sayfa varsa OCR yolu (Görev 07) ya da açıkça `needs_ocr` raporu; metin tahminle doldurulmaz.
- Okuma ucu: `/admin-acts/{ref}/sections/{no}?as_of=` ya da `/kb/search` içinden; hangisi seçilirse ajan A4'te ona bağlanır.

### A4: Ajan okuma yolu

- `read_article` / genelge okuma: yanıttaki `review_status` ve `band` taşınır (sabit "approved" kalkar).
- Prompt ve `read_sources`'ta onaysız kaynak "onaysız (test)" etiketli; kapı (gate) onaylı / onaysız ayrımını izde tutar.
- Şablon `must_read` künyeleri ("4857 m.18", "2020/8", "9. HD E.2016/28920 K.2017/17860") KB kaydına eşlenir;
  eşlenemeyen künye izde `missing_source` olarak görünür (sessizce düşmez).
- Cevapta (Answer) onaysız kaynağa dayanan her nokta için kullanıcıya görünür işaret alanı (UI işlemesi sonraki iş,
  ama sözleşmede alan bu pakette).

### A5: Yerel uçtan uca

- Yerel yığın (`make dev`), gerçek `data/drive` ile: kanunları ve genelgeleri yükle, `KB_TEST_SOURCE_BANDS=high,medium`,
  `python -m app.loaders.chunks --dry-run` (maliyet tahmini Orhan'a), onayla gerçek indeks.
- Ölçüm tablosu (PR'a): kanun / genelge başına madde sayısı ve bant dağılımı; indekslenen chunk sayısı (kategori, onay durumu).
- Duman testi: SB-001 ve SB-024 gerçek LLM ile birer kez (eval-runner, bütçe kapısı). Beklenen: `read_sources` boş değil,
  4857 m.18 / 5510 m.8 okunmuş; cevabın kalitesi bu paketin kabulü değil (Paket B).

## Kapsam dışı

- Cevap kalitesi, yeni konu şablonları, 20 vaka (Paket B).
- Otomatik onay mekanizması (ayrı görev; K1 onun yerini geçici tutar).
- UI değişikliği, marka.
- Diğer genelgeler / yönetmelikler (yalnız 2018/38 ve 2020/8).

## Kabul kriterleri

- [ ] `ruff`, `mypy`, `pytest` (Postgres'li) yeşil; web etkilenmediyse web testleri gerekmez.
- [ ] A1: ayar boşken onaysız hiçbir kaynak arama ve madde okumada dönmez (test); `high,medium` iken low dönmez (test);
      rejected hiç dönmez (test).
- [ ] A2: 6356, 7036, 1475 m.14 golden testleri; 4857 / 5510 mevcut golden testleri değişmeden yeşil.
- [ ] A3: 2020/8 ve 2018/38 bölüm sayısı + 3 bölüm metni golden; ikinci yükleme hiçbir şey eklemez.
- [ ] A4: sahte KB ile: onaysız okunan kaynak `read_sources`'ta "analyzed" + band; eşlenemeyen must_read izde görünür.
- [ ] A5: yerelde ölçüm tablosu ve iki duman koşusunun izi PR'da; harcanan tutar yazılı.
- [ ] `docs/decisions.md` (K1), `.env.example`, `docs/deploy.md` güncel.

## Canlı (A6, merge sonrası, Orhan onayıyla)

Canlıda hiçbir adım onaysız yapılmaz. Sıra:
1. Dokploy env: `OPENAI_API_KEY` (Orhan ekler), `KB_TEST_SOURCE_BANDS=high,medium`. Deploy.
2. Kaynak dosyalar sunucuya: yalnız gereken kanun / genelge dosyaları ve üretilen jsonl'ler (Görev 11 düzenindeki
   arşiv klasörü). Kopyalamayı Orhan'ın Mac'i yapar.
3. `app` konteynerinde: statutes + admin_acts yükleyicileri, ardından `python -m app.loaders.chunks --dry-run`,
   tahmin Orhan'a, onayla gerçek koşu.
4. Ölçüm: `chunk` sayısı kategori ve onay durumuna göre; glarus.siestai.com'da SB-001 bir kez (izde okunan kaynaklar).
5. Mevcut onaylı / reddedilmiş kayıtlar ve kullanıcılar değişmedi (sayım öncesi / sonrası).
