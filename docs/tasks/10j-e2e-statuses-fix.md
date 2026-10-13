# Görev 10j: statuses e2e "Onaydan çıkar" testini onar

- **Durum:** uygulandı (PR Orhan'ın onayında)
- **Sahip:** Claude Code
- **Onay:** Orhan
- **Bağlam:** `services/dashboard-web/e2e/statuses.spec.ts`, `services/dashboard-web/e2e/README.md`, görev 10h (yeniden incelemeye alma)

## Hedef

`statuses.spec.ts` içindeki "an approved record is taken back with 'Onaydan çıkar' and can then be rejected" testi, e2e README'sindeki varsayılan kurulumla (`make user ... name='E2E'`) düşüyordu. Kök neden uygulama değil testti: geçmiş satırında inceleyen adı `"E2E Test"` diye sabit yazılmıştı, oysa belgelenen ad `E2E` (`E2E_NAME`) ve dosyadaki diğer testler `REVIEWER` sabitini kullanıyor. Yalnızca görünen adı `E2E Test` olan bir kullanıcıyla geçiyordu.

## Kapsam

- `statuses.spec.ts`: sabit `"E2E Test"` yerine `REVIEWER`.

## Kapsam dışı

- Uygulama, arayüz ya da başka e2e dosyaları. Testin amacı (geçmişte tek "Yeniden incelemeye aldı" satırı, inceleyen ve not) aynen kalır; skip, yeniden deneme ya da süre artırma yok.

## Kabul kriterleri

- Kullanıcı görünen adı `E2E` iken (README varsayılanı), `make e2e-reset` sonrası tam `pnpm e2e` koşusu: hata yok. Düzeltmeden önce aynı koşuda yalnız bu test `Expected substring: "E2E Test"` / `Received: "E2E · Yeniden incelemeye aldı..."` ile düşüyordu.
- `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, kökte format denetimi temiz.
