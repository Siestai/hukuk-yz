# e2e (Playwright)

Canlı bir yığına karşı koşan uçtan uca testler. **CI'da koşmaz** (orada yığın yok); Vitest de
bu klasörü taramaz. Kurulum ve video: [docs/local-dev.md](../../../docs/local-dev.md).

```bash
make dev && make demo-data       # yığın + sentetik demo verisi
make user email=e2e@example.test name='E2E' role=reviewer
E2E_EMAIL=e2e@example.test E2E_PASSWORD='...' pnpm e2e   # services/dashboard-web içinde
```

Ortam değişkenleri: `E2E_EMAIL`, `E2E_PASSWORD` (gerekli, repoya yazılmaz), `BASE_URL`
(varsayılan `http://localhost:3000`), `E2E_VIDEO=1` (video), `E2E_CHANNEL=chromium` (tam
Chromium; PDF görüntüleyicisi için), `E2E_RETRIES` (varsayılan 0; trace ilk yeniden denemede
alınır). Çıktı: `.output/` (gitignore'lu). Tarayıcı `pnpm exec playwright install chromium` ile iner.

## Dosyalar

| Dosya             | Ne dener                                                                                | Veriyi                       |
| ----------------- | --------------------------------------------------------------------------------------- | ---------------------------- |
| `login.spec.ts`   | oturumsuz yönlendirme, yanlış parola (Türkçe hata), giriş, boş alan, çıkış              | değiştirmez                  |
| `queue.spec.ts`   | özet, bant / mahkeme / sebep filtresi, arama, mükerrer işareti, sıralama, sayfalama     | değiştirmez                  |
| `detail.spec.ts`  | alanlar, PDF sekmesi (iframe ve PDF yanıtı), metin sekmesi, J/K                         | değiştirmez                  |
| `actions.spec.ts` | R ile ret (not zorunlu), E ile anahtar kelime düzeltip onay, A ile onay, "kuyruk bitti" | **tüketir**: Demo 12, 05, 04 |
| `bulk.spec.ts`    | yüksek bant + dar arama, onay kutusu, çalıştırma, rapor                                 | **tüketir**: Demo 01-03      |

İki Playwright projesi var (ikisi de Chromium): `chromium` (salt okunur dosyalar) önce, sonra
`chromium-mutating` (veri değiştirenler) koşar; böylece okuyan testler dokunulmamış demo verisini
görür. Testler tek worker'la, sırayla koşar. Oturum bir kez `global-setup.ts` ile açılır
(`.output/state.json`); `login.spec.ts` kendi girişini yapar.

## Tekrar koşmak

Mutating testler demo kayıtlarını onaylar veya reddeder; ikinci koşuda kayıt kalmaz ve testler
"Demo data is used up" ipucuyla düşer. Başa dönmek için:

```bash
make e2e-reset        # db-reset + demo-data; siler, kullanıcılar da gider
make user email=e2e@example.test name='E2E' role=reviewer   # sıra önemli: önce sıfırla, sonra kullanıcı
```

Demo kayıtlarının içeriği ve bantları: [infra/demo/README.md](../../../infra/demo/README.md). Testler
sayıları (12 kayıt: 6 yüksek, 4 orta, 2 düşük) bu fixture'dan bekler.

Not: `login.spec.ts` yanlış parola denemesini var olmayan bir e-postayla yapar; giriş sınırı
e-posta başına sayar, tekrarlı koşular gerçek hesabı kilitlemesin diye.
