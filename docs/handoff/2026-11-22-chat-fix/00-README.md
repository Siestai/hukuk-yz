# Handoff: Glarus chat fonksiyonel düzeltmeleri (Paket A → Paket B)

Tarih: 2026-11-22. Sahip: Orhan (yerel Claude Code). Hazırlayan: Themis.
Bu klasör repoya `docs/handoff/2026-11-22-chat-fix/` olarak girer (Paket A'nın ilk PR'ı). Repo public: kişi adı, sunucu adresi, anahtar yok.

## Neden

Glarus (chat v1, Görev 16-18) canlıda çalışıyor: giriş, akış, netleştirme, kalıcılık. Ama her soru
`answer_not_verified` ("Kaynaklar doğrulanmış bir yanıt oluşturmak için yetersiz") ile bitiyor.
Canlı ölçüm (22.11): `chunk` 0 satır, yayımlanmış `statute` 0 (Görev 11'in 378 maddesi onaysız kuyrukta),
6356 / 1475 / 7036 ve genelgeler hiç yüklü değil, canlı env'de embedding anahtarı yok.
Ayrıca ajanın 6 konu şablonu var; eval vakalarının yarısı şablonsuz kalıp "genel" şablona düşüyor.

## Sıra (zorunlu)

1. **Paket A: test kaynakları ve indeks** (`A-kb-test-sources.md`). Bitmeden B'nin eval adımı başlamaz.
2. **Paket B: Görev 19, esaslı cevap + 20 vakalık eval** (`B-task19.md`, vakalar `B-cases-new10.md`).
   B'nin vaka analizi (B1) A ile paralel başlayabilir: kod değil, yalnız `eval/cases/` taslakları.

UI / yeni marka bu handoff'un dışında (ayrı iş). Yalnız zorunlu metin: kullanıcıya görünen "Libria" → "Glarus" B'de değil, sonraki UI işinde.

## Bağlayıcı kararlar (2026-11-22, Orhan)

- **K1, test kaynak kuralı:** otomatik onay mekanizması gelene kadar TEST / kapalı betada inceleme kuyruğunda onaysız
  duran ama güven bandı `high` veya `medium` olan mevzuat maddeleri okunabilir kaynaktır. `low` okunmaz.
  Bu kaynaklar cevapta ve izde "onaysız (test)" diye işaretlenir; md.25 kapısı aynen çalışır (okunmamış kaynağa
  atıf yok). Açık yayından önce yeniden karar gerekir: davranış tek bir ayarla kapanabilmeli.
- **K2:** Görev 19 ilk tur eval kapsamı 20 vaka (mevcut 10 + yeni 10).
- **K3:** marka Glarus. Yeni UI fonksiyonel düzeltmelerden sonra, ayrı iş.

## Çalışma düzeni: orkestratör + subagent'lar

Ana Claude Code oturumu **orkestratör**dür: kod yazmaz, işi böler, subagent'lara verir, sonucu doğrular, PR açar.
Subagent tanımları `agents/` altında; işe başlamadan `.claude/agents/`'a kopyalanır.

| Subagent | Yetki | Ne yapar |
|---|---|---|
| `implementer` | yazma, yalnız kendisine verilen worktree | Bir alt görevi RED → GREEN → refactor ile yapar, commit atar |
| `reviewer` | salt okuma | Diff'i blocker / should-fix / nit ile raporlar, dosya değiştirmez |
| `legal-case-analyst` | yalnız `eval/cases/` ve `services/agent/agent/topics/` taslakları | Vakayı resmi metinden analiz eder, vaka ve şablon YAML'ı yazar |
| `eval-runner` | salt okuma + eval komutu | Gerçek LLM eval'ini bütçe kapısıyla koşar, tablo üretir |

Kurallar:
- Paralel `implementer`'lar **ayrı git worktree**'lerinde çalışır (`git worktree add ../hy-<tag> -b <branch>`), aynı dosyaya iki yazar yok.
  Hangi alt görevlerin paralel olabileceği paket dosyalarındaki tabloda yazılı.
- Her alt görev: implementer → orkestratör kendisi lint/type/test koşar (subagent'ın "geçti" demesi kanıt değil) →
  reviewer → should-fix'lerin hepsi + ucuz nit'ler için implementer düzeltme turu → tekrar test → PR.
- Repo skill'leri: `task-pr-hygiene`, `db-migration`, `frontend-ui`. Prompt'lara kuralları kopyalama, skill'i adıyla an.
- Test dosyaları modüle göre (`test_search.py`, `test_topics.py`); süreç adlı test dosyası yok.
- Merge Orhan'da. PR açıklamasında: ne yapıldı, kabul kriteri kanıtı, doğrulanamayan.

## Para ve dış sistemler

- Gerçek LLM / embedding çağrısı yapan her adım önce `--dry-run` maliyet tahmini basar, sonra Orhan'a sorar.
  Tavan: Paket A ≤ 2 USD (embedding), Paket B ≤ 5 USD (eval, tüm turlar dahil). Tavana yaklaşınca dur, sor.
- Canlı (Dokploy) üzerinde çalışan adımlar `A-kb-test-sources.md` §Canlı'daki sırayla, Orhan onayıyla. Canlı DB'de
  kullanıcı ve inceleme kayıtlarına (onay / ret) dokunulmaz.
- Anahtarlar `.env`'de ya da Dokploy env'inde; prompt'a, loga, PR'a yazılmaz.

## Başlatma (Orhan)

```bash
cd hukuk-yz && git checkout main && git pull --ff-only
mkdir -p docs/handoff/2026-11-22-chat-fix .claude/agents
cp <bu klasör>/*.md docs/handoff/2026-11-22-chat-fix/
cp <bu klasör>/agents/*.md .claude/agents/
claude
```

Claude Code'a ilk mesaj: `docs/handoff/2026-11-22-chat-fix/PROMPT-A.md` dosyasının içeriği.
A merge edilip canlıda indeks kurulunca: `PROMPT-B.md`.
