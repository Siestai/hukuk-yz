# Görev 13c: arşiv kararları "benzer dosya" eşleşmesinde

- **Durum:** uygulandı (PR Orhan'ın onayında)
- **Sahip:** Claude Code
- **Onay:** Orhan
- **Bağlam:** `docs/tasks/13-upload-detect-approve.md` ("Benzer dosya"), görev 12 (dosya deposu), `services/app/app/loaders/decisions.py`

## Hedef

Canlı testte (2026-10-12) arşivdeki kararın aynı metni yüklendiğinde (`AYRIMCILIK TAZMİNATI.txt`) `previous_version` bulundu ama `similar` boş kaldı. Aynı karar başka bir dosyayla yüklenirse "benzer" olarak görünmelidir.

Neden: `similar_files` yalnız `scan_result["text_key"]` olan adayların metnini karşılaştırıyor. Bu alan yalnız worker'ın taradığı dosyalarda var (6.598 dosyadan 263'ü). Karar yükleyicisinin (`loaders/decisions.py`) yazdığı 6.319 arşiv kararında `scan_result` boş, bu yüzden hepsi sessizce atlanıyor. Metinler aslında aynı (örtüşme 1,0).

## Kapsam

- Eşleşmede deponun metni olmayan aday için karar metni kullanılır: `extraction.file_id` → `extraction.source_id` → `decision` (`superseded_at IS NULL`) → `full_text`. İnceleme onayı henüz verilmemiş kararda `decision` satırı yoktur; yalnız o durumda `extraction.fields["full_text"]` okunur (`coalesce` ile, kararın metni varsa `fields`'a dokunulmaz).
- Metinler tek sorguda, yalnız karşılaştırılacak adaylar için (en çok `MAX_COMPARED`) çekilir. Deponun metni her zaman önce gelir.
- İki metni de olmayan aday eskisi gibi atlanır.

## Kapsam dışı

- Şema, migrasyon, yeni uzantı veya bağımlılık; API/OpenAPI değişikliği (web tarafında iş yok).
- Arşiv dosyalarının metnini depoya yazmak veya `scan_result`'ı doldurmak.

## Kabul kriterleri

- `uv run pytest services/app/tests/test_files_matching.py`: taraması olmayan arşiv dosyası aynı metinli yüklemeye benzer bulunur; farklı metinli bulunmaz; inceleme bekleyen karar `extraction.fields`'dan okunur; deponun metni karar metninden önce gelir.
- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy services packages`, `uv run pytest` temiz.
