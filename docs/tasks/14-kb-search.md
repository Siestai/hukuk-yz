# Görev 14: KB arama indeksi ve `/kb/search` (kararlar + mevzuat)

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/data-model.md` §7 (arama), §8 (embedding, `chunk` bölme kuralları), `docs/architecture.md` §4.1, §5.1, `docs/tasks/05-decision-load.md` (karar kaydı), `docs/tasks/11-statute-versioning.md` (madde çizelgesi, `extraction.fields`), `docs/decisions.md` 2026-10-27 (v1 kapalı beta, onaysız kaynak, OpenAI embedding).
Skill'ler: `task-pr-hygiene`, `db-migration` (indeks/kolon eklenirse).

## Hedef

Ajanın ilk bağımlılığı: "işe iade altı ay kıdem" gibi bir sorgu için doğru kararları ve mevzuat maddelerini, **olay tarihinde geçerli** sürümüyle, kategori etiketli ve onay durumu belli olarak döndüren hibrit arama.

Bugün canlıda `chunk` tablosu boş, arama API'si yok. Onaylı karar 90, analiz edilmiş (onay bekleyen) karar ~6.140; 4857 ve 5510 madde çizelgeleri `extraction` olarak duruyor, `statute_article` boş.

## Karar: kapalı betada onaysız kaynak (Orhan, 2026-10-27)

Beta süresince `analyzed` durumdaki kaynaklar da indekslenir ve aranabilir. Her sonuç `review_status` (`approved` / `analyzed`) taşır; ajan ve UI onaysızı "onaylanmadı" etiketiyle gösterir. `rejected` hiçbir zaman indekslenmez. Açık yayından önce bu davranış bir ayarla (`KB_SEARCH_INCLUDE_UNREVIEWED`, varsayılan `false`) kapatılır; beta ortamında `true`.

## Kapsam

1. **Chunk üretimi** (`packages/` altında saf modül, DB'siz test edilebilir; app'te ince yükleyici):
   - **Kararlar:** onaylı ise `decision` kaydından; analiz edilmiş ise kaynağın en güncel `extraction.fields`'ından. Bölme kuralları `data-model.md` §8 (bölüm başlığı varsa bölüm, yoksa paragraf / ~300-500 token pencere, hafif örtüşme; kısa karar tek chunk). Editoryal özet ayrı chunk, `kind=editorial_summary`, `license=internal_only` (metni sonuçta dönmez, yalnız eşleşme sinyali).
   - **Mevzuat:** madde sürümü başına bir chunk (çok uzun madde fıkra bazlı). Onaylı ise `statute_article_version`, değilse çizelgedeki sürümler; her chunk `valid_from` / `valid_to` taşır. `gap` aralığı chunk üretmez.
   - `header` künye satırı (`data-model.md` §8 örneği) embedding'e girer, gösterilmez.
   - `parent_kind`: `decision` | `statute_article` | `extraction` (onaysız kayıt). Chunk her zaman `source_id` ile kaynağa bağlanır (gerekirse kolon eklenir, migration).
2. **Embedding:** OpenAI `text-embedding-3-large`, `dimensions=1024` (mevcut `EMBEDDING_DIM`, migration gerekmez). Toplu çağrı (batch), yeniden denemeli, hız sınırına uyar. `embedding_model` alanına model + boyut yazılır. Anahtar `OPENAI_API_KEY` env'den; yoksa komut açık hata verir. Yeniden çalıştırma idempotent: metni ve modeli değişmemiş chunk tekrar gömülmez (metin hash'i).
3. **Tam metin:** `tsv` Türkçe config + unaccent (yoksa migration ile).
4. **İndeks komutu:** `python -m app.loaders.chunks [--category decision|statute] [--dry-run] [--limit N]`: üretir, gömer, yazar; sonunda rapor (kategori ve onay durumuna göre chunk sayısı, gömülen token, tahmini maliyet, atlanan, hata). Onay / ret / metin yenileme (04b) sonrası ilgili kaynağın chunk'ları yenilenir (aynı fonksiyon, kaynak bazında).
5. **`GET /kb/search`** (`app`, oturum gerekli, tüm roller):
   - Parametreler: `q` (zorunlu), `category` (çoklu), `as_of` (tarih; mevzuatta o tarihte geçerli sürüm, kararlarda karar tarihi ≤ as_of), `court_level`, `date_from`/`date_to`, `limit` (varsayılan 10, en çok 50).
   - Hibrit: tsvector + pgvector (HNSW, cosine), RRF ile birleştirme. Sıralamada `court_level` ve `source_rank` hafif ağırlık (`data-model.md` §7).
   - Sonuç **kayıt** bazında gruplanır: `{source_id, category, title, ref (künye), review_status, verification (kararlarda), valid_from/valid_to (mevzuatta), score, matches: [{chunk_id, text, char_start, char_end}]}`. `internal_only` chunk'ın metni dönmez.
   - OpenAPI'ye girer, dashboard tipleri yeniden üretilir.
6. **Arama eval'i (ön ölçüm):** `eval/retrieval/` altında küçük bir set: soru bankasından ~15 soru + her biri için beklenen kaynak künyeleri (konu kartlarındaki "Hüküm haritası"ndan, ör. SB-001 → 4857 m.18, 9. HD 2016/28920). `python -m app.eval.retrieval` recall@5 / recall@10 raporlar. Set Themis tarafından hazırlanır ve PR'a girer (repo public: soru metninde kişi adı yok).

## Kapsam dışı

- Genelge, yönetmelik, tebliğ, genel yazı, görüş (`admin_act`): ayrı Görev 14b (bölüm bazlı ayrıştırma + yükleme).
- Yeniden sıralama modeli (reranker), sorgu genişletme: eval sonucuna göre sonra.
- Dashboard'da arama ekranı.
- Ajan, chat API.

## Kabul kriterleri

- `make lint`, `make typecheck`, `make test` yeşil. Chunk bölme ve RRF birleştirme birim testli (DB'siz); `/kb/search` entegrasyon testi CI Postgres'inde (pgvector), embedding sahte istemciyle.
- `--dry-run` tam korpusta çalışır, chunk sayısı ve tahmini token/maliyet raporlanır (PR açıklamasında çıktı).
- Testte: `as_of=2015-01-01` ile 4857 m.18 araması 2015'te geçerli sürümü döner; `gap` aralığına düşen tarih için o madde sonuç vermez.
- `rejected` kaynak hiçbir aramada çıkmaz; `KB_SEARCH_INCLUDE_UNREVIEWED=false` iken `analyzed` kaynak çıkmaz (test).
- `internal_only` chunk metni yanıtta yok (test).
- Retrieval eval komutu çalışır ve raporu PR'da (gerçek embedding ile koşu canlı indeksten sonra Themis tarafından yapılır, sonuç PR yorumuna).

## Notlar Claude Code için

- Bölme ve birleştirme saf fonksiyon; DB ve OpenAI istemcisi kenarda, enjekte edilebilir.
- OpenAI çağrısını testte gerçek ağa çıkarma.
- Tam korpus gömme işi bu PR'da koşulmaz; merge sonrası Themis canlıda çalıştırır (tahmin: ~8 M kelime ≈ 15-20 M token, birkaç dolar).
