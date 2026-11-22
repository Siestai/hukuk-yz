# Görev 19 devri: Themis (2026-11-22)

Görev 19'un (dayanaklı cevap, Paket B) bundan sonrası Themis ile yürür. Bu belge ne yapıldığını,
nerede durulduğunu ve açık konuları toplar. Önce şunları oku:

- Spec: `docs/tasks/19-grounded-answer.md`
- Eval özeti: `eval/results/2026-11-22-ozet.md`
- İlk devir paketi: `docs/handoff/2026-11-22-chat-fix/` (`00-README.md`, `PROMPT-B.md`)
- Karar günlüğü: `docs/decisions.md` (2026-11-22 kayıtları)

## Kurallar (değişmedi)

- **Ücretli çağrı:** LLM ve embedding çağrılarında önce maliyeti tahmin et, sonra Orhan'dan onay al. Anahtarları okuma, yazdırma, loglama.
- **Canlı sistem:** Canlıda kendi başına hiçbir şey çalıştırma.
- **Canlı veritabanı:** Kullanıcı kayıtlarına ve inceleme (onay/ret) kayıtlarına dokunma.
- **Kapılar ve md.25:** Eşiği geçirmek için kapı gevşetilmez. Uydurma künye, tarih ya da madde metni yazılmaz. Karararama'da teyit edilmemiş Yargıtay künyesi vaka dosyasına girmez.
- **Belirsizlik:** Tahmin etme, Orhan'a sor; soruları tek tek sor. Orhan hukukçu değil, hukuk terimlerini gündelik dille aç.
- **Repo public:** Kişi adı, sunucu adresi ya da anahtar yazma.

## Ne yapıldı

Tüm iş PR'larla ana dala girdi.

| PR | içerik |
|---|---|
| #92 | Devir paketi ve alt ajan tanımları |
| #93 | Test kaynak politikası (bant), incelenmemiş okuma yolu (A1, A4) |
| #94 | Kanun kaydı (6356, 7036, 1475 m.14), genelge yükleyici (A2, A3, A5) |
| #95 | Görev 19 spec'i ve 20 vakalık eval |
| #96 | Dayanaklı cevap: konu şablonları, kapı, kaynak yetersiz cevabı, eval koşucusu, 3 tur düzeltme |

#96'nın içeriği:

- **Vakalar ve şablonlar:** 20 eval vakası (`eval/cases/SB-*.yaml`) ve 13 konu şablonu (`services/agent/agent/topics/`).
- **Netleştirme:**
  - Şablona bağlı sorular sorulur (`asked_when`) ve tek bir takip turu yapılır.
  - Seçmeli bir soruya serbest metinle verilen cevap "bilinmiyor" sayılır.
- **Okuma:** Okunacak kaynaklar şablona göre belirlenir (`must_read`, `when` koşulu). Adı geçen kaynaklar 20.000 karaktere kadar okunur.
- **Dayanak kapısı** (`holding.py`, `gate.py`):
  - Okunmamış, yürürlükte olmayan ya da birebir alıntısı bulunmayan satır düşer.
  - Düşen satırlar için tek bir düzeltme denemesi yapılır.
  - Kaynak, kimliğiyle ya da tekil künyesiyle bağlanır.
  - Alıntılarda tipografik tırnak işaretleri düz biçimleriyle eşleşir.
- **Kaynak yetersizse:** Doğrulanmış satır kalmazsa sistem dürüst bir "cevaplanamadı" cevabı verir (`source_gap`); web bunu gösterir.
- **Eval koşucusu** (`python -m agent.eval`): Tahmin, bütçe tavanı, `--case` seçimi, intake kaydı ve sonuç tablosu.

## Eval durumu

Üç tur koşuldu, toplam 4,81 USD (Paket B tavanı 5 USD). **Kabul eşikleri geçilmedi.**

| | 1. tur | şimdi (karışık turlar) |
|---|---|---|
| Sistem hatası | 5 vaka | yok |
| Esaslı cevap | 10 vaka | 16 vaka |
| "-iyor" kipi, md.25 ihlali | 0 | 0 |

**Son kodla (1e2f827) 20 vakalık tam koşu yapılmadı.** Vaka başına son durum `eval/results/2026-11-22-ozet.md` dosyasında.

### Eval'i koşma notları

- **Dizin:** Komutlar `services/agent` içinden çalışır:
  `uv run python -m agent.eval ../../eval/cases [--case SB-NNN ...] --estimate`, ardından
  `... --kb http --tag rN --budget-usd X --record-intake ../../eval/fixtures/intake`.
- **KB adresi:** Ajan host'ta koşuyorsa `APP_BASE_URL` app'in host adresine ayarlanmalı. Varsayılan `http://app:8000` yalnız Docker içinde çalışır. r2'nin ilk denemesi bu yüzden boşa gitti (0,13 USD).
- **Ücretsiz bağlantı denemesi:** Koşudan önce ücretsiz bir `/kb/search` isteğiyle bağlantıyı dene.
- **Sıra ve bütçe:** Koşucu vakaları `--case` sırasıyla değil, kimlik sırasıyla koşar. Kalan bütçe vaka başına tahminin altına düşerse kalan vakaları atlar.
- **Test veritabanı:** Testler tek kullanımlık bir `pgvector/pgvector:pg16` kapsayıcısında koşar. Geliştirme veritabanı kullanılmaz.
- **Bilinen test düşüşü:** SB-032 ve SB-035'in intake kaydı eski olduğu için repoya alınmadı; ilgili test bu vakalarda atlanır. Yeniden kaydedince ekle.

## Açık konular (öncelik sırasıyla)

### 1. Teyitsiz Yargıtay künyeleri: Orhan'ın kararı bekleniyor

Şu üç vakada Karararama'da teyit edilmemiş künyeler var. Hepsi `missing_in_kb` ve `must_cite` alanlarında, SB-013'te ayrıca bir `must_say` notunda geçiyor:

- **SB-003:**
  - 9. HD E.2021/4643 K.2021/8989
  - 9. HD E.2016/9412 K.2019/16512
  - 9. HD E.2012/6260 K.2014/11165
- **SB-005:**
  - 9. HD E.2008/26536 K.2008/25713 (dergi arşivinde var, sayı 20)
  - 22. HD E.2012/12745 K.2013/2608
- **SB-013:**
  - 22. HD E.2017/20988 K.2019/6513
  - 9. HD E.2023/3247 K.2023/3581

Önerilen yol: künyeleri vaka dosyalarından ayrı bir aday listesine taşımak. Karararama'da teyit edilenler sonra dosyalara geri döner. Seçenekler:

- aday listesine taşı,
- tamamen sil,
- olduğu gibi bırak.

Orhan konuyu sordu, açıklandı, ama henüz karar vermedi. Teyit edilemeyen künyeyi düzeltmeye ya da "bulmaya" çalışma; sadece raporla.

### 2. Ortaklara sorular (B1'den, 19 soru)

Liste #96'nın açıklamasında ve aşağıda. Cevaplar vaka dosyalarını ve şablonları değiştirebilir.

**SGK ve emeklilik**

1. **SB-042:** Yaşlılık şartlarında ayrım tarihi 1.10.2008 değil 30.4.2008 görünüyor (2018/38, 5510 Geçici m.7). Doğru mu?
2. **SB-042:** 30.4.2008 sonrası girişlide kıdem tazminatı yazısının dayanağı, m.104/1'deki atıf kuralıyla 5510 m.28 mi? SGK uygulaması böyle mi?
3. **SB-042:** "08 kodu = yaş dışındaki şartları tamamlama" doğru mu? Ayrılış kod listesi KB'de yok.
4. **SB-002:** Ölüm toptan ödemesi m.36'da. Notlardaki m.37 atfı m.36 mı olmalı? 2008 öncesi memurların hak sahipleri için hangi kaynak geçerli?
5. **SB-012:** Haftada tam 30 saat çalışan kısmi süreli sayılır mı? Kaynaklar farklı söylüyor: SSİY "daha az", Çalışma Süreleri Yönetmeliği "oranına kadar", 2020/20 "30 saat ve altı".
6. **SB-024:** Yeni işyerinde bir aylık süre ilk sigortalının başladığı tarihten mi (kanun), tescil tarihinden mi (yönetmelik, 2013/11) başlar? Yeni inşaat işyerinde de uygulanır mı?
7. **SB-010:** 4857 m.49/4'te "46, 47 ve 48 inci maddenin birinci fıkrası uygulanmaz" deniyor. "Birinci fıkra" üç maddeye de mi bağlı, yalnız m.48'e mi?
8. **SB-026:** "SGK yazısı zamanaşımı der" tuzağı hangi SGK yazısına dayanıyor?

**İdari para cezası**

9. **SB-014:** Tekrar hâlinde bir yıllık süre en son tespitten mi sayılır (2020/8 Örnek 4 yorumu)? Geç de olsa kendiliğinden verilen bildirge ya da SGK'nın kendi kayıtlarından tespit süreyi başlatır mı?
10. **SB-019:** Muhtasar ve prim hizmet beyannamesi dönemi hangi tarihten başlar? 2020/8'de bulunamadı.
11. **SB-016:** "SSİY m.102 hüküm içermez" tuzağı doğrulanmalı. 2020/8 m.3.2 must_cite listesine eklenmeli mi?

**İş hukuku**

12. **SB-027:** Devamsızlık feshinde savunma kanunda zorunlu değil (m.19/2 son cümle). "Uygulamada savunma istenir, makul süre beklenir" görüşü için teyit edilebilir bir karar künyesi var mı?
13. **SB-027, SB-035:** m.26'daki 6 iş günü, devamsızlık sürerken ya da ücret hâlâ ödenmezken hangi günden başlar? Dayanak karar hangisi?
14. **SB-035:** Bir günlük izin, m.56'daki "bir bölüm on günden az olamaz" kuralıyla nasıl bağdaşır? Peşin ödeme yükümlülüğü sürer mi?
15. **SB-035:** İşçi fesih yaptığında fesih sebebini açıkça yazma yükümlülüğü içtihatta aranıyor mu?
16. **SB-032:** 4857 m.32'deki "kupon" yasağının yemek kartının giydirilmiş ücrete girmesiyle ilgisi olmadığı (yasağın ödeme aracıyla ilgili olduğu) varsayımı doğru mu?
17. **SB-003:** "Bordro imzası kabul değildir" ve "aynî ikame esaslı değişiklik sayılmayabilir" tuzaklarının dayanak kararları hangileri?

**Sendika ve TİS**

18. **SB-005:** "Süresi biten TİS'te faiz türü değişir (yasal faiz)" cümlesinin dayanağı ne?
19. **SB-039:** AYM'nin 6356 m.39/4'te iptal ettiği cümle bugünkü cevabı etkiler mi? "Talep tarihi" yazılı başvuru mu, ilk aidat ödemesi mi?

### 3. KB eksikleri

KB'ye eklenmesi önerilenler:

- SSİY, Çalışma Süreleri Yönetmeliği, Yıllık Ücretli İzin Yönetmeliği
- 2013/11 ve 2020/20 genelgeleri
- HMK m.92-93, 6772 sayılı Kanun, 506 sayılı Kanun (geçici m.81, m.60)
- SGK işten ayrılış kod listesi

Low banttaki (okunamayan) maddeler yeniden çıkarılmalı ya da incelenmeli: 5510 m.102, m.80, m.28, Geçici 4/7/9 ve 4857 m.63. Ayrıca `decision` tablosu boş; doldurulmalı ve kayıtlar Karararama'da teyit edilmeli.

Kaynak gösterme puanının düşük kalmasının asıl nedeni bu eksikler.

### 4. Kod: koşul bağlı takip soruları (SB-008)

SB-008'de konu artık doğru seçiliyor (`kidem_ihbar`). Ama `fesih_nedeni = askerlik` iken şu takip soruları sorulmadı:

- `sevk_tarihi`
- `sevk_tehiri`
- `sonraki_calisma`
- `ayrilis_gerekcesi`

Takip turunun bu dala neden girmediği incelenmedi. Bakılacak yerler:

- `facts.follow_up`
- `asked_when` koşulları
- `kidem_ihbar.yaml`
- SB-008'in r3 izi

SB-021'de de r1'de aynı belirti (must_ask %0) görüldü; bu da incelenmedi.

### 5. Son kodla sınanmayanlar

- **SB-014:** tipografik alıntı düzeltmesi
- **SB-032, SB-035:** konu seçimi düzeltmesi
- **SB-042:** hiç koşulmadı
- **SB-039:** r1'de bütçe dolduğu için yarıda kaldı

Son kodla 20 vakalık tam koşu yaklaşık 3–4 USD tutar ve Orhan'ın onayını ister.

### 6. İz eksikliği

Sonuç dosyası, düşen satırın `source_id` değerini ve alıntı metnini tutmuyor. Bu ayrıntılar yalnız Langfuse'ta görülebiliyor, Langfuse de yerelde ayarlı değildi. Bu yüzden SB-002 ve SB-014'ün düşüş nedenleri kanıtlanamadı, yalnız tahmin edildi.

Küçük bir ekleme önerisi: çözülemeyen `source_id` ve alıntı metni `holding_map` iz çıktısına ve `CaseResult`'a yazılsın. Bu spec dışında kaldı.
