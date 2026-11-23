# Görev 21: Glarus "Liman" arayüzü (chat web)

## Hedef
Chat uygulamasının (services/web, glarus.siestai.com) görünümünü seçilen "Liman" tasarımına taşımak. Fonksiyon değişmez: aynı akış, aynı API, aynı metinler (marka hariç).

Referans mockup (tek dosya, gerçek eval akışlarıyla): `design/glarus-ui/liman.html` (bu PR'da repoya eklenir, ürün kodu değildir).

## Kapsam
- **Tokenlar:** Liman paleti, yazı ve boşluk değerleri yalnız chat uygulaması için tanımlanır (services/web teması). Dashboard görünümü değişmez. Renkler sadece CSS değişkeni + Tailwind theme üzerinden; bileşende sabit renk yok.
  - Lacivert #14233F, kâğıt #F6F1E6, yüzey #FCFAF4, çukur #EDE6D4, çizgi #DDD3BC, turkuaz #0E7C73 (ana etkileşim), mat altın #B38A2E yalnız küçük vurgu (koşullu rozeti, onaysız etiketi, alıntı fosforu).
  - Yazı: Newsreader (wordmark, soru, cevap başlığı ve maddeler, dayanak metni) + Figtree (arayüz). Fontlar self-host (OFL), mevcut IBM Plex düzeni gibi.
  - Boşluk 4/8/12/16/24/32/48; köşe 10 px (kontroller) ve 16 px (kartlar). Dokunsal 2 px "dudak" gölgesi yalnız buton, seçenek ve atıf çiplerinde.
- **Marka:** "Glarus" wordmark + altında küçük "by siestai", telefonda ve masaüstünde. Libria izleri UI'dan kalkar.
- **Ekranlar:** boş durum, konuşma listesi (masaüstünde lacivert yan panel, telefonda çekmece), soru kartı (Soru N / M + ilerleme, "Neden soruyorum" katlanır, büyük seçenekler, tarih girişi + GG.AA.YYYY ipucu, Bilmiyorum, Soruları atla), cevaplanan soruların tek satıra inmesi, "Anladığım olay", cevap (rozet, başlık, Kısa/Ayrıntılı/Gerekçeli, numaralı maddeler + atıf çipleri, tamamlanması gereken bilgiler, okunanlar, geri bildirim), dayanak paneli (masaüstünde sağ sütun, telefonda alt sayfa; alıntı vurgulu; "Onaysız metin (test)"), giriş ekranının markası.

## Kapsam dışı
- Agent, app, API, veri modeli, metin içerikleri (marka dışı).
- Dashboard-web görünümü.
- Yeni özellik.

## Kabul kriterleri
- [ ] Mevcut web testleri yeşil (gerekirse yalnız görünümle ilgili seçiciler güncellenir); lint + typecheck yeşil; dashboard-web testleri yeşil.
- [ ] 360 px'te yatay kaydırma yok, dokunma hedefi ≥ 44 px, input ≥ 16 px, klavye odağı görünür, prefers-reduced-motion.
- [ ] Bileşenlerde sabit renk yok (grep ile kontrol).
- [ ] "by siestai" telefonda ve masaüstünde görünür.
- [ ] Canlıda telefon ve masaüstünde akış uçtan uca çalışır (deploy sonrası Themis doğrular, Orhan telefondan dener).
