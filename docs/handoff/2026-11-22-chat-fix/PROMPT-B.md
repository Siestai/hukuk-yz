Sen bu işin orkestratörüsün. Kod yazmazsın; işi subagent'lara böler, sonucu kendin doğrular, PR açarsın.

Ön koşul: Paket A main'de, yerel KB dolu (chunk sayısını kontrol et; boşsa dur, bana söyle).

Oku: `docs/handoff/2026-11-22-chat-fix/00-README.md`, `B-task19.md`, `B-cases-new10.md`, `AGENTS.md`, `docs/tasks/17-agent-v1.md`, `18-chat-wiring.md`, `eval/cases/*.yaml`, `services/agent/agent/topics/*.yaml`.
Subagent'lar `.claude/agents/` altında: implementer, reviewer, legal-case-analyst, eval-runner.

İş: Paket B (Görev 19). İlk PR `docs/tasks/19-grounded-answer.md` (B-task19.md'den, kabul eşiği dahil): bana göster, onayımla devam.

Akış:
1. B1: 20 vakanın her biri için bir `legal-case-analyst` çağrısı (4-5 paralel). Mevcut 10 vaka gözden geçirilir, yeni 10 vaka yazılır. Sonuç: 20 YAML + konu → şablon tablosu + `missing_in_kb` listesi. Bunları bana göster. Hukuki şüphe varsa toplayıp tek seferde sor (ortaklara ben ileteceğim).
2. B2 (şablonlar) ile B3 (kapı) ve B4 (kaynak-yetersiz cevabı) ayrı worktree'lerde paralel. Her biri: implementer → kendin test → reviewer → düzeltme → test.
3. B5: eval koşucusu ve tablo. `eval-runner` 20 vakayı koşar: önce tahmin, onayım, sonra koşu. Paket B tavanı toplam 5 USD (tüm turlar).
4. B6: en fazla 3 tur. Başarısızları kök nedene göre grupla (şablon / kaynak eksik / kapı / model), grup başına düzeltme, yeniden eval. Eşiği geçirmek için kapı gevşetme yok.
5. PR('lar): tur tablosu, toplam maliyet, kalan başarısızların kök nedeni, doğrulanamayanlar. CI yeşil olunca bana "hazır" de. Merge'i ben yaparım.

Kurallar:
- md.4 (olay tarihindeki hüküm), md.25 (okunmamış kaynağa atıf yok), md.29 (hesap LLM'de değil), K1 (yalnız high / medium onaysız, işaretli), "-iyor" kip yasağı blocker'dır.
- Uydurma künye, tarih ya da madde metni yok. Teyitsiz Yargıtay künyesi vaka dosyasına girmez.
- Ücretli çağrı önce tahmin, sonra onayım. Anahtarları okuma, yazdırma, loglama. Repo public.
- Hukuk terimlerini raporda gündelik dille aç; ben hukukçu değilim.
- Belirsizlikte bana sor. Bana Türkçe ve kısa raporla.
