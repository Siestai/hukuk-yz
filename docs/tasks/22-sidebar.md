# Görev 22: Sidebar: kısa ve doğru başlık, sabitleme (en fazla 3)

## Hedef
Konuşma listesinde (chat web, glarus.siestai.com) her konuşmanın başlığı kısa ve konuyu doğru anlatır olsun; kullanıcı en fazla 3 konuşmayı listenin üstüne sabitleyebilsin.

## Kapsam
### 1. Başlık
- Bugün: başlık `facts.title` (agent intake LLM'i) ve her turda yeniden yazılıyor; uzun çıkabiliyor (ör. "Kamu görevlisinin ölüm toptan ödemesi, 01.09.2026 tarihinden ...").
- Yeni kural:
  - Agent prompt'u (`services/agent/agent/prompts.py`, `title`): 2-5 kelime, en fazla 40 karakter, isim öbeği; konu + ayırt edici olgu (ör. "İşe iade, 5 ay kıdem", "4/c ölüm toptan ödemesi", "Devamsızlık nedeniyle fesih"); tarih, tutar, kişi adı yok; nokta yok.
  - Agent tarafında deterministik sınır: başlık 48 karakteri aşarsa kelime sınırında kısaltılır (üç nokta yok); boşsa konu şablonunun başlığı.
  - App: başlık konuşmanın İLK anlaşılan olayından bir kez yazılır, sonraki turlar (düzeltme, cevap) başlığı değiştirmez.
  - Mevcut uzun başlıklar: Alembic veri migration'ı ile aynı 48 karakter kuralına göre kısaltılır (geri alınabilir değil; yalnız uzunları etkiler).
- UI: başlık tek satır, taşarsa kesilir, tam metin `title` özelliğinde.

### 2. Sabitleme
- `chat_conversation.pinned_at` (nullable timestamptz) + migration.
- API: `PUT /conversations/{id}/pin` ve `DELETE /conversations/{id}/pin` (yalnız konuşmanın sahibi; admin başkasının konuşmasını sabitleyemez). Bir kullanıcının en fazla 3 sabit konuşması olur; dördüncüde `409` + yeni hata kodu `pin_limit`. İdempotent: zaten sabitse 200.
- `GET /conversations`: önce sabitler (`pinned_at` artan; ilk sabitlenen üstte), sonra diğerleri `updated_at` azalan. `Conversation` modeline `pinned: bool` alanı.
- OpenAPI tipleri yeniden üretilir (web tipleri).
- UI: listede "Sabitlenenler" ve "Konuşmalar" bölümleri (sabit yoksa yalnız "Konuşmalar"); her satırda sabitle / sabitlemeyi kaldır düğmesi (ikon, aria-label, 44 px hedef; masaüstünde hover/focus'ta, telefonda her zaman görünür). Limit dolunca: dördüncü sabitleme denemesinde Türkçe kısa uyarı ("En fazla 3 konuşma sabitlenebilir."), mevcut sabitler değişmez. İyimser güncelleme + hata olursa geri alma.
- Metinler `services/web/messages/tr.json`'da.

## Kapsam dışı
- Konuşma silme/yeniden adlandırma, arama, klasör.
- Dashboard.

## Kabul kriterleri
- [ ] Agent: başlık kısaltma ve boş başlık testleri; prompt kuralı.
- [ ] App: başlığın ilk olaydan bir kez yazıldığı, sonraki turda değişmediği test; pin/unpin, limit 409 `pin_limit`, sahiplik, sıralama testleri (DB testleri).
- [ ] Migration up/down; veri migration'ı yalnız 48+ karakterlik başlıkları kısaltır.
- [ ] Web: sabitle/kaldır, bölümler, limit uyarısı, uzun başlığın kesilmesi testleri; 360 px'te yatay kaydırma yok, dokunma hedefi ≥ 44 px.
- [ ] e2e (fixture) yeşil; fixture arka uç da sabitlemeyi destekler ya da e2e etkilenmez.
- [ ] Canlıda: yeni soruda kısa başlık, 3 sabit + dördüncüde uyarı.
