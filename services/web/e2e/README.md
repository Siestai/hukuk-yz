# e2e (Playwright)

Canlı bir yığına karşı koşan uçtan uca testler. **CI'da koşmaz** (orada yığın yok); Vitest bu
klasörü taramaz.

```bash
# app: sahte (fixture) chat arka ucu, http için çerez Secure olmasın
CHAT_BACKEND=fixture COOKIE_SECURE=false uv run uvicorn app.main:app --port 8000
# giriş yapacak bir kullanıcı (rolü önemsiz): make user email=e2e@example.test name='E2E' role=user
APP_API_URL=http://localhost:8000 pnpm build && APP_API_URL=http://localhost:8000 pnpm start
E2E_EMAIL=e2e@example.test E2E_PASSWORD='...' BASE_URL=http://localhost:3000 pnpm e2e   # services/web içinde
```

Ortam değişkenleri: `E2E_EMAIL`, `E2E_PASSWORD` (gerekli, repoya yazılmaz), `BASE_URL`
(varsayılan `http://localhost:3000`, `pnpm start`'ın portu; dashboard da 3000'de açıldığı için ikisi birlikte koşarken bunu `PORT` ile başka porta alıp `BASE_URL`'i ayarla), `E2E_VIDEO=1`, `E2E_CHANNEL=chromium`, `E2E_RETRIES`.
Çıktı: `.output/` (gitignore'lu). Tarayıcı `pnpm exec playwright install chromium` ile iner.

| Dosya           | Ne dener                                                                                                                                                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `login.spec.ts` | oturumsuz yönlendirme, yanlış parola (Türkçe hata), giriş, çıkış                                                                                                                                                                     |
| `chat.spec.ts`  | giriş → yeni soru (SB-001) → olay kartı + 1/6 soru → iki cevap, gerisi atlanır → koşullu cevap, "Tamamlanması gereken bilgiler" açık → Gerekçeli → tablo → dayanak → vurgulu metin → 👎 geri bildirim; her adımda yatay kaydırma yok |

İki proje koşar: `chromium` (masaüstü) ve `chromium-mobile` (telefon: yatay kaydırma, dokunma). Fixture arka ucun
durumu bellektedir; her koşu kendi konuşmasını açar, sıfırlama gerekmez.

## Gerçek ajan köprüsü (çevrimdışı model)

`E2E_BACKEND=agent` yalnız `agent.spec.ts` çalıştırır; fixture senaryolarının
assertion'ları değiştirilmez. App `CHAT_BACKEND=agent`, agent ise
`PYTHONPATH=services/agent/tests TEST_STATUTE_VERSION_ID=<sentetik-sürüm-uuid> TEST_STATUTE_QUOTE=<test-metnindeki-alıntı>` ile
`uv run uvicorn serve:app --port 8182` üzerinden açılır. Bu yardımcı gerçek grafı,
Postgres checkpoint'lerini ve HTTP KB istemcisini kullanır; yalnız model scripted'dir.
Veritabanı yalnız sentetik test verisi içermelidir. Servis anahtarları ortamdan gelir.
`APP_BASE_URL=http://localhost:8181`, app tarafında
`AGENT_BASE_URL=http://localhost:8182` kullanılır. Web `PORT=3318` ile açılır.

`E2E_BACKEND=agent BASE_URL=http://localhost:3318 E2E_EMAIL=... E2E_PASSWORD=... pnpm e2e`

Bu koşu hukuki doğruluk veya gerçek model kabulü değildir; ücretli model koşusu
ayrı maliyet korumalı orkestrasyonla yapılmalıdır.
