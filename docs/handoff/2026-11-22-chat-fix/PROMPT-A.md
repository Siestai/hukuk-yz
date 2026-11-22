Sen bu işin orkestratörüsün. Kod yazmazsın; işi subagent'lara böler, sonucu kendin doğrular, PR açarsın.

Oku: `docs/handoff/2026-11-22-chat-fix/00-README.md`, `A-kb-test-sources.md`, `AGENTS.md`, `docs/tasks/11-statute-versioning.md`, `14-kb-search.md`, `17-agent-v1.md`.
Subagent'lar `.claude/agents/` altında: implementer, reviewer, legal-case-analyst, eval-runner.

İş: Paket A (A1-A6).

Akış:
1. Planı çıkar: alt görevler, dosya sahipliği (hangi dosyayı hangi alt görev değiştirir), worktree / branch adları, paralel gruplar (A1 | A2 | A3, sonra A4). Planı bana göster, onayımı bekle.
2. Onaydan sonra A1, A2, A3 için üç ayrı worktree aç ve üç `implementer`'ı paralel başlat. Bitenleri sırayla: kendin lint / mypy / pytest (Postgres'li) koş → `reviewer` → should-fix'ler için aynı implementer'a düzeltme turu → tekrar test.
3. A4'ü A1'in üzerine kur, aynı döngü.
4. A5: yerel yığında yükle ve `python -m app.loaders.chunks --dry-run` çalıştır. Maliyet tahminini bana göster, onayımla gerçek indeksi kur. Sonra `eval-runner` ile SB-001 ve SB-024 duman testi (önce tahmin, onay). Paket A tavanı 2 USD.
5. PR('lar): açıklamada ne yapıldı, kabul kriterlerinin her biri için kanıt (komut çıktısı özeti), ölçüm tablosu, harcanan tutar, doğrulanamayanlar. CI yeşil olunca bana "hazır" de. Merge'i ben yaparım.
6. Merge sonrası A6 canlı runbook'unu adım adım bana ver; canlıda kendi başına hiçbir şey çalıştırma.

Kurallar:
- Hukuki güvenlik kuralları (md.4 tarih, md.25 okunmamış kaynağa atıf yok, K1 bant kuralı) blocker'dır; testle kanıtlanır.
- Ücretli çağrı (LLM, embedding) önce tahmin, sonra benim onayım. Anahtarları okuma, yazdırma, loglama.
- Repo public: kişi adı, sunucu adresi, anahtar yazma.
- Belirsizlikte tahmin etme, bana sor. Kapsam dışına taşma.
- Bana Türkçe, kısa raporla. Subagent prompt'ları İngilizce olabilir.
