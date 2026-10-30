# Görev 16: Chat web arayüzü v1 (`services/web`, Alternatif B)

Durum: uygulandı; PR inceleme düzeltmeleri tamamlandı, DB'li entegrasyon doğrulaması bekliyor. PR Orhan'ın onayında. Sahip: Themis (Claude Code çalıştırır). Onay: Orhan.
Bağlam: `docs/decisions.md` 2026-10-27 (Alternatif B, kapalı beta), `docs/design/chat-ui/alt-B.png` (mobil), `alt-D.png` (masaüstü üç sütun), `docs/tasks/15-chat-contract-eval.md` (sözleşme, fixture backend), `services/dashboard-web` (auth, i18n, token, responsive kalıpları), `packages/ui`.
Skill'ler: `task-pr-hygiene`, `frontend-ui` (bağlayıcı).

## Hedef

Kapalı beta kullanıcısının giriş yapıp ajana soru sorduğu, netleştirme sorularını cevapladığı ve yapılandırılmış cevabı üç modda okuduğu mobil öncelikli chat arayüzü. Görev 15'in fixture backend'iyle uçtan uca çalışır; gerçek ajan Görev 17-18'de aynı sözleşmeyle bağlanır, UI değişmez.

## Kapsam

1. **Servis:** `services/web` (Next.js, dashboard-web ile aynı sürüm ve kurulum: next-intl `tr`, `packages/ui` token'ları ve bileşenleri, vendored font, güvenlik başlıkları, `/healthz`, Dockerfile, CI'da lint/typecheck/test/build). Ortak kod kopyalanmaz: dashboard-web'de olup iki uygulamanın da ihtiyaç duyduğu şey (API istemcisi, oturum, hata kodu çevirisi) `packages/ui` veya yeni ortak pakete taşınır.
2. **Giriş:** mevcut `app` auth'u (aynı oturum çerezi kuralı). `/giris`, `/oturum-sonu`. Kayıt yok. Tüm roller (`user`, `reviewer`, `admin`) girer.
3. **Konuşma listesi:** masaüstünde sol sütun, mobilde çekmece (dashboard drawer kalıbı). "Yeni soru" düğmesi. Başlık + tarih.
4. **Ekran 1, Netleştirme (B-1):**
   - Kullanıcı balonu (soru).
   - "Anladığım olay" kartı (`CaseFacts`): bilinen değerler, bilinmeyenler vurgulu "Bilinmiyor"; kullanıcı bir değere dokunup düzeltebilir (düzeltme yeni mesaj olarak gider).
   - Soru kartı: ilerleme çubuğu "Soru 1 / 5", soru metni, seçenek düğmeleri (tek seçim), tarih / sayı / metin girişi `input.kind`'a göre, her zaman "Bilmiyorum", altında "Neden soruyorum: ..." (atıflar tıklanabilir).
   - Alt yapışkan bağlantı: "Soruları atla, koşullu cevabı göster".
5. **Ekran 2, Cevap (B-2):**
   - Üstte sabit mod seçici (Kısa / Ayrıntılı / Gerekçeli); mod değişimi istek atmaz, aynı `Answer`'ı farklı gösterir.
   - Durum bandı: "Net cevap" / "Koşullu cevap" + not; koşullu ise en üstte ve "Tamamlanması gereken bilgiler" bölümü varsayılan açık (tasarım kararı), ekranda "müşteri" kelimesi yok.
   - Başlık cümlesi, olgu çipleri (+ "Düzenle"), maddeler: her madde ve altında ayrı satırda kalın dayanak bağlantısı (tasarım kararı); onaylı/teyitli rozetleri ("teyitli", "onaylanmadı").
   - Kapalı başlıklar (mobilde, tasarım kararı): "Hesap" (v1: neye ihtiyaç var), "Okunanlar" (sayılar + liste). Alt bilgi: uygulanan mevzuat tarihi + "Hukuki görüş değildir."
6. **Ekran 3, Gerekçeli (B-3):** "Koşullar olaya uyuyor mu?" tablosu (kanundaki koşul + dayanak / olayda / sonuç simgesi ✓ ✗ –), mobilde satırlar kart olur; altında gerekçe özeti + dayanak.
7. **Dayanak görüntüleyici:** bir atfa dokununca alt sayfa (mobil) / sağ panel (masaüstü, `lg`): kaynağın tam metni `GET` ile (mevcut KB okuma endpoint'leri; yoksa Görev 15'in fixture'ındaki metin), ilgili kısım vurgulu ve oraya kaydırılmış açılır (tasarım kararı). Onay ve teyit durumu görünür.
8. **Akış:** SSE `ChatEvent`'leri; `step` olayları "Kaynaklar okunuyor..." gibi canlı durum satırı; hata kodları çevrili; bağlantı koparsa tekrar dene.
9. **Geri bildirim:** her cevabın altında 👍/👎; 👎 veya "Hata bildir" → madde seç, tür seç, yorum + doğrusu (isteğe bağlı) → `POST /chat/turns/{id}/feedback`.
10. **Kopyala:** cevabı düz metin olarak kopyala (WhatsApp'a yapıştırılabilir: başlık, maddeler, dayanaklar, sonda "Hukuki görüş değildir").
11. **Responsive** 360 / 768 / 1440, frontend-ui kuralları (44 px, 16 px input, yatay kaydırma yok). Masaüstünde üç sütun: konuşmalar | sohbet | dayanak paneli (alt-D).

## Kapsam dışı

- Gerçek ajan, kalıcı konuşmalar (Görev 17/18), admin iz ekranı (Langfuse, Görev 18).
- PDF dışa aktarma, logo/marka, ödeme, kayıt, KVKK metinleri.

## Kabul kriterleri

- `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, `pnpm format:check` yeşil; birim testleri bileşen adına göre.
- Playwright e2e (fixture backend, yerel yığın): giriş → yeni soru (SB-001) → olay kartı + 1/N soru → iki soru cevapla, gerisini atla → koşullu cevap, "Tamamlanması gereken bilgiler" açık → mod Gerekçeli → tablo → dayanağa dokun → vurgulu metin → 👎 geri bildirim gönderildi. Telefon projesinde yatay kaydırma yok.
- 360/768/1440 ekran görüntüleri (üç ekran + dayanak paneli) PR açıklamasında; Themis B tasarımıyla karşılaştırır.
- Kod tabanında hardcode renk / metin yok (mevcut lint kuralları web'e de uygulanır).

## İnceleme düzeltmeleri (2026-10-29)

- Production derlemesi test dosyalarını ve servis dışındaki fixture importlarını dışlar; ayrı `tsconfig.typecheck.json` testleri de kontrol eder.
- Yeni soru, yeni istek ve unmount önceki SSE isteğini iptal eder; geç gelen olaylar ve konuşma listesi yanıtları yeni ekranı değiştirmez.
- Her gönderim hatasında tekrar deneme sunulur; gelen kısmi olgular/netleştirme korunur. Metin sorusunun tekrar denemesi son gövdeyi yeniden gönderir, arayüzde ikinci kullanıcı balonu oluşturmaz. Fixture API idempotent değildir: kabul edilmiş netleştirmeyi tekrar göndermek `clarification_not_pending` döndürebilir. Bu nedenle başarısız netleştirmede açık bir “Netleştirmeyi yeniden başlat” eylemi son metin sorusunu aynı konuşmada yeniden gönderir; kullanıcı bilgileri tekrar girer. Son turu kullanıcı olan konuşma yeniden açıldığında da kurtarma eylemi görünür. İstek kimliğiyle idempotency sözleşmesi bu görevin kapsamında değildir.
- Dayanak tarihi ilgili cevaptan (netleştirmede olay tarihinden) taşınır; tarih yoksa Türkiye günü kullanılır. Kaynak yüklemesi tarihi de izler.
- Mod seçici `aria-pressed` düğme grubudur; Tab ve Enter ile çalışır. Soru başlığı odaklanır, ilerleme canlı duyurulur.
- Kopyalama hatası çevrilir, başarı etiketi sıfırlanır; gönderilmiş/bekleyen geri bildirim düğmeleri kilitlenir. Alıntı sınırları ve metin eşleşmesi doğrulanır; Next sıkıştırması kapalıdır.
- Gerçek PostgreSQL oturumu ve KB entegrasyonu yerel DB yokluğu nedeniyle ayrıca doğrulanmalıdır. DB'siz görsel harness gerçek fixture chat router'ını kullanır; giriş ve KB taklitleri bu entegrasyon kabulünün yerine geçmez.
