# Görev 18: Chat uçtan uca bağlama (app ↔ agent, kalıcılık, geri bildirim)

Durum: taslak. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/tasks/15-chat-contract-eval.md` (endpoint'ler fixture ile), `docs/tasks/16-chat-web.md`, `docs/tasks/17-agent-v1.md`, `docs/architecture.md` §2 (app tek yazar, agent kanal bilmez).
Skill'ler: `task-pr-hygiene`, `db-migration`.

## Hedef

Web'deki chat'in gerçek ajanla çalışması; konuşmalar, cevaplar ve geri bildirimler kalıcı; her cevap iz kaydına bağlı.

## Kapsam

1. **Şema (migration):** `chat_conversation` (user_id, title, timestamps), `chat_turn` (conversation_id, role, payload JSONB = sözleşmedeki `Turn`, mode, trace_id, model, tokens, cost, latency_ms), `chat_feedback` (turn_id, user_id, rating, point_index, kind, comment, correction, created_at). Kullanıcı yalnız kendi konuşmalarını görür (admin hepsini, API'de).
2. **`app` chat endpoint'leri** (Görev 15'teki yollar): `CHAT_BACKEND=agent` iken `agent` `/run`'a köprü (SSE geçişi), olayları kaydeder; `fixture` modu testler için kalır. Agent'a servis anahtarıyla gidilir; agent `app`'in `/kb/search` ve okuma endpoint'lerini servis anahtarıyla çağırır.
3. **Kota:** kullanıcı başına günlük soru sınırı (`CHAT_DAILY_LIMIT`, varsayılan 50), aşılınca hata kodu.
4. **Geri bildirim dışa aktarımı:** `GET /chat/feedback?since=` (admin) JSON; Themis bunu soru bankasına / eval vakalarına çevirir.
5. **Compose / deploy:** `agent` servisi compose'da; env örnekleri (`.env.example`), `docs/deploy.md`'ye web + agent bölümleri (alan adı ve sırlar repoda değil).
6. **E2E:** yerel yığın (app + agent sahte LLM + web) üzerinde Görev 16 e2e senaryosunun `agent` modunda koşması.

## Kapsam dışı

- Admin iz ekranı (Langfuse kendi arayüzü kullanılır), ödeme, kayıt.

## Kabul kriterleri

- Lint/type/test yeşil (Python + web). Migration ileri/geri testli.
- Yetki testleri: başka kullanıcının konuşması 404; `user` dashboard API'lerine 403.
- Uçtan uca: gerçek LLM ile yerel yığında SB-001 soru → netleştirme → cevap → geri bildirim kaydı; DB'de turn + feedback satırları (çıktı PR'da).
