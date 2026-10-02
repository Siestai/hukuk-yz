# Hukuk-YZ Pazar Araştırması: Türkiye'de Hukuk Odaklı Yapay Zekâ Ürünleri

Tarih: 2 Ekim 2026
Kapsam: İş hukuku ve sosyal güvenlik (SGK) odaklı, kaynaklı cevap veren ve hesaplama yapan YZ asistanı fikrine benzer ürünlerin taranması. 41 web araması, 25 site içeriği okuması yapıldı. Fiyatlar sitelerde yazdığı şekliyle alındı, teyit edilemeyenler "bulunamadı" olarak işaretlendi.

## Özet (yönetici için)

1. Türkiye'de "iş hukuku + SGK" odaklı, kaynak atıflı ve deterministik hesaplama yapan bir YZ asistanı bulunamadı. Pazar iki kümeye ayrılmış: (a) avukatlara yönelik genel içtihat/dilekçe asistanları, (b) mali müşavirlere yönelik mevzuat özetleme/radar araçları. İkisinin kesişimi boş.
2. En yakın iki ürün: mesnet.ai (deterministik süre hesabı ilkesi, ama sadece usul süreleri, avukat odaklı) ve Müşavir AI / MALİİK Mevzuat Radarı (mali müşavir odaklı, SGK genelgelerini takip ediyor ama Yargıtay içtihadı ve hesaplama motoru yok).
3. Kaynak gösterme artık standart vaat; emsal.ai, hukuk.chat, Kazancı AI, Jupytr, HukukOS hepsi "halüsinasyonsuz, kaynaklı" diyor. Farklılaşma "kaynak var mı" değil, "kaynak doğrulanmış mı, olay tarihindeki sürüm mü, hesap tekrar üretilebilir mi" sorularında olacak.
4. Olay tarihindeki mevzuat sürümü: sadece Lexpera "Sürüm ve Madde Karşılaştırma" özelliğiyle madde geçmişi sunuyor; hiçbir YZ asistanı "olay tarihine göre cevap ver" modu sunmuyor (sitelerde böyle bir özellik bulunamadı).
5. Uzman eskalasyonu (YZ cevabı yetmezse ücretli insan uzmana yönlendirme) hiçbir hukuk YZ ürününde yok; sadece Muhasebecin (beta) "müşavir marketplace" fikrini duyurmuş.

## (a) Doğrudan rakipler: iş hukuku / SGK / bordro / mali müşavir odaklı YZ

| Ürün | Ne yapıyor | Hedef kitle | Fiyat | Kaynak/atıf yaklaşımı | İş hukuku / SGK kapsamı | Yapmadığı |
|---|---|---|---|---|---|---|
| Müşavir AI (musavirai.com.tr) | Mevzuat kütüphanesi, AI soru-cevap, 7/24 Resmi Gazete radarı, Paraşüt entegrasyonu, mobil uygulama | Mali müşavir, denetim firması | Bulunamadı | "Güncel kanunlara dayalı, referanslı yanıt"; doğrulama yöntemi açıklanmamış | Vergi + SGK mevzuatı + ticaret hukuku (genel) | Yargıtay içtihadı yok, hesaplama motoru yok, tarihsel sürüm yok, uzman eskalasyonu yok |
| MALİİK Mevzuat Radarı (maliikdernegi.com) | Resmi Gazete, GİB, SGK, ÇSGB, TÜRMOB tebliğlerini takip; "AI 360° etki analizi", bordro yansımaları, simülatörler | Mali müşavir, bordro uzmanı | Bulunamadı | Düzenleme bazlı özet; birincil kaynak linki görünüyor | Kıdem tavanı, SPEK sınırları, yıllık izin gibi bordro parametreleri | Soru-cevap asistanı değil, içtihat yok, olay bazlı hesaplama yok |
| Mükellef.im | Büro yönetimi (mükellef kartı, beyanname, SGK bildirgesi takibi) + "mevzuat sorularına kaynak göstererek yanıt veren" yerleşik asistan | Mali müşavir bürosu | Bulunamadı | Kaynak gösterme vaadi var, detay yok | SGK giriş/çıkış bildirgesi takibi (operasyonel) | İçtihat, hesaplama, hukuki muhakeme yok |
| Muhasebecin (muhasebecin.com.tr) | AI muhasebe asistanı, vergi/SGK ödemeleri, SGK giriş-çıkış API, müşavir marketplace | KOBİ ve şahıs şirketi (müşavir değil) | Kapalı beta, fiyat yok | Belirtilmemiş | SGK operasyon | Hukuki soru-cevap değil; ürün henüz çıkmamış |
| SMMM Asistan (smmmasistan.com) | WhatsApp üzerinden evrak paylaşımı | Mali müşavir | Bulunamadı | Yok (belge yönetimi) | Yok | Hukuk içeriği yok |
| Otto HR (ottohr.com) | "Agentic payroll": brütten nete, SGK primi, damga, asgari ücret istisnası otomatik; onay insanda | İK'sız küçük ekipler, yabancı yatırımcı | Bulunamadı | Parametreler programda gömülü; mevzuat atfı yok | Bordro hesabı (operasyonel) | Hukuki soru-cevap, içtihat, uyuşmazlık analizi yok |
| Kolay İK | SaaS İK/bordro; 2021'de MindBehind ile "Kolay Sor" chatbot duyurdu | KOBİ İK | Bulunamadı | Yok | Bordro/izin operasyonu | Mevzuat/içtihat asistanı yok; 2026 sitesinde YZ asistanı öne çıkmıyor |
| Logo Bordro Plus / Logo AI | Bordro yazılımı; Logo Edge T'de "AI rapor asistanı ve dijital danışman" | Kurumsal İK, muhasebe | Lisans bazlı | Yok | Bordro operasyonu | Hukuki asistan yok |
| Mikro, Luca, Zirve | Muhasebe yazılımları; Mikro "yapay zeka raporu" yayımlamış, ürün içi hukuk asistanı bulunamadı; Luca ve Zirve için YZ hukuk asistanı bulunamadı | Mali müşavir | Lisans bazlı | Yok | Yok | Hukuki asistan yok |
| GİBİ (GİB dijital vergi asistanı) | Kamu chatbot'u, genel vergi soruları | Vatandaş/mükellef | Ücretsiz | Kurum kaynaklı | Vergi; SGK yok | İş hukuku yok, atıf yok |
| SGK kurumsal chatbot | Bulunamadı (sadece denetim amaçlı YZ haberleri var) | | | | | |

Doğrudan rakip sayısı (iş hukuku + SGK + kaynaklı cevap kesişiminde): 0. Kısmi örtüşen ürün sayısı: 4 (Müşavir AI, MALİİK Radar, Mükellef.im, Otto HR).

## (b) Genel hukuk YZ'leri

| Ürün | Ne yapıyor | Hedef kitle | Fiyat | Kaynak/atıf yaklaşımı | İş hukuku / SGK kapsamı |
|---|---|---|---|---|---|
| emsal.ai | 11M+ içtihat ve mevzuat; doğal dil arama, sohbet, dilekçe asistanı, MCP bağlantısı (Claude/Codex); Google for Startups destekli | Avukat | Ücretsiz plan + Plus 1.250 TL + KDV/ay (tek kullanıcı) | "Yanıtlar kaynaklarıyla sunulur, kaynak dışı yanıt riski azaltılır"; mevzuat maddesine göre filtre | Genel; iş hukuku özel modülü yok, SGK genelgesi yok |
| mesnet.ai | Kural tabanlı hukuki süre hesabı (sürümlenmiş kurallar, YZ sonucu değiştiremez), yetkili onayı, takvim; koşullu kaynaklı araştırma ve belge araçları; işlem geçmişi | Avukat, hukuk bürosu | Başvuru ile erişim; fiyat bulunamadı | "Süreleri YZ değil kural motoru hesaplar", hesap adımları açıklanabilir, dayanak gösterilir (ör. HMK m.345) | Usul süreleri (istinaf, zamanaşımı); kıdem/ihbar/İPC hesabı yok, SGK yok |
| hukuk.chat (VeriUs, Marmara Ü. Teknopark) | 11M+ karar, 800K+ mevzuat maddesi, kaynaklı sohbet, sözleşme risk analizi, uzman avukat onaylı şablonlar | Avukat, şirket | Bulunamadı | "Her yanıt kanun maddesi, Yargıtay/Danıştay atfıyla"; günde 2 güncelleme | Genel |
| Lexpera + LEXI AI | Klasik bilgi bankası; LEXI 2.0 sohbet ve doküman asistanı (beta); belge yükleme; "Sürüm ve Madde Karşılaştırma", "Zaman Çizelgesi" | Avukat, akademi, kurum | Yıllık 34.200 - 48.000 TL (İçtihat Pro karşılaştırması, Mart 2026); LEXI fiyatı bulunamadı | Lexpera içeriğinden besleniyor; literatür de var | Genel; madde sürüm geçmişi var |
| Kazancı AI | "Halüsinasyonsuz, kaynak temelli yanıt, tıklanabilir referans"; 7M+ içerik; büro/dava otomasyonu ve hesaplamalar | Avukat | Yıllık 22.800 TL (İçtihat Pro karşılaştırması) | Tıklanabilir atıf | Genel |
| Jupytr (jupy.tr) | 10M+ karar, günlük mevzuat; metin içi atıf; sözleşme revizyonu (track changes), due diligence, hâkim/daire eğilim analizi; kurumsal hafıza | Büyük hukuk bürosu, şirket hukuk ekibi | Bulunamadı (kurumsal) | "Her yanıtı metin içi atıflarla gerçek kaynaklara dayandırır" | Genel; demoda iş davası örnekleri yok |
| Hammurabi (hammurabi.tr) | Çalışma alanı, müvekkil/dava yönetimi, UYAP eşitleme, çok açılı içtihat tarama, dilekçe UDF çıktı | Avukat | 3 gün ücretsiz deneme; fiyat bulunamadı | Taranan kararları listeliyor | Genel; demo senaryosu iş hukuku (ihbar, fazla mesai zamanaşımı, ibraname) |
| HukukOS | 10,9M karar, sesli asistan, UYAP eklentisi, UDF çıktı, risk analizi | Avukat (1.000+) | Kredi bazlı paketler; fiyat bulunamadı | "Halüsinasyon üretmeyen gerçek içtihat" | Genel |
| LexChat (lexchat.ai) | Agentic platform: alt ajanlar, sandbox'ta hesaplama ve XLSX üretimi, 10M+ karar, 14K+ mevzuat, süre hesabı | Avukat | 7 gün ücretsiz Professional Plus | Hibrit arama; atıf detayı belirsiz | Genel; "süre hesabı" sandbox'ta LLM kodla yapılıyor (deterministik motor değil) |
| De Jure AI | İçtihat arama, dilekçe, UYAP/UETS entegrasyonu; baro anlaşmaları | Avukat | Bulunamadı | Belirtilmemiş | Genel |
| Consülto AI | Sohbet, Yargıtay arama, dilekçe editörü (udf) | Avukat | 6 aylık sınırsız 4.750 TL | Kararın "yararlanılan kısmı" gösteriliyor | Genel |
| İçtihat Pro | 10,8M karar, AI dilekçe, "hukuki hesaplama araçları" | Avukat, öğrenci | 199 TL/ay, 2.866 TL/yıl | Arama odaklı | Genel; hesaplama araçlarının içeriği bulunamadı |
| Son Karar, KararVar, Lexpanel, Fullegal | YZ destekli karar arama ve dilekçe | Avukat | Bulunamadı | Arama | Genel |
| turk-hukuku.com (açık kaynak) | mevzuat.gov.tr ve UYAP Emsal'den canlı çeken MCP sunucuları + 1000+ "skill"; "MCP aktifken model karar numarası uyduramaz" | Claude Code/Codex kullanan avukat | Ücretsiz | Resmi kaynaktan canlı çekim | Genel (iş hukuku skill'i var) |
| HukukAI (App Store), Yapay Zeka Avukatı, AiDA Hukuk, OveK, LawChat | Mobil/tüketici veya küçük büro asistanları | Öğrenci, vatandaş, avukat | Uygulama içi satın alma | Belirsiz | Genel |
| Legalstart, "Avukat GPT" | Türkiye'de bu adlarla ürün bulunamadı (AvGPT bir GitHub prompt aracı) | | | | |
| Jurix | Hukuk makale/dergi veritabanı; YZ ürünü değil | Akademi | | | |

Ortak örüntü: hepsi avukat/hukuk bürosu için tasarlanmış, "dilekçe yaz + karar bul" ekseninde. Mali müşavir veya İK uzmanı persona'sı hiçbirinde yok.

## (c) Klasik kaynaklar ve YZ özellikleri

- Lexpera: Mevzuat, içtihat, literatür. "Sürüm ve Madde Karşılaştırma", "Etkilediği/Etkilendiği Mevzuat", "Zaman Çizelgesi" özellikleriyle madde düzeyinde geçmiş tutuyor; LEXI AI beta. Bu, "olay tarihindeki mevzuat" vaadi için en yakın altyapı, ama YZ cevabı tarih parametresi almıyor (sitede bulunamadı). https://www.lexpera.com.tr/
- Kazancı: 1953'ten beri; Kazancı AI (Ekim 2025'te "Yeni" etiketli) kaynak temelli yanıt. https://kazanci.com.tr/
- Legalbank: Boolean arama; YZ özelliği sitede bulunamadı. https://legalbank.net/arama
- Kanunum: Uzman üyelik yıllık 13.000 TL (İçtihat Pro karşılaştırması); YZ özelliği bulunamadı.
- mevzuat.gov.tr: Resmi mevzuat; YZ yok. turk-hukuku MCP sunucusu buradan canlı çekiyor.
- UYAP Mevzuat ve İçtihat (mevzuat.adalet.gov.tr): 14.950 mevzuat, 6,9M Yargıtay kararı, 7,7M toplam içtihat; YZ yok. Birçok ticari ürünün "10M+ karar" iddiasının kaynağı bu havuz.
- Çalışma ve Toplum arşivi (elimizdeki 6.342 karar): Hiçbir rakip bu dergiyi ayrı bir kaynak olarak sunmuyor; derginin editöryal seçilmiş iş hukuku kararları niş avantaj.

## (d) Yurt dışı referanslar

- Harvey: BigLaw ve Fortune 500 hukuk ekipleri için; 200M$ ARR, Sequoia/GIC turu. Türkçe hukuk içeriği veya Türkiye ofisi bulunamadı. https://lanturkey.com/en/blog/hukuk-teknolojisi-harvey
- CoCounsel (Thomson Reuters): Westlaw içeriğiyle "Fiduciary-Grade AI"; Türk hukuku kapsamı bulunamadı. https://www.thomsonreuters.com/en/cocounsel
- Lexis+ AI: Lexis içeriğine dayalı; Türkiye'de ürün bulunamadı.
- Bağımsız benchmark (haqq.ai, 2026): genel amaçlı modellerin özel hukuk ürünlerini geçtiğini iddia ediyor; farkın modelde değil veri ve doğrulama katmanında olduğunu destekliyor. https://haqq.ai/blog/best-legal-ai-tools-2026
- Düzenleyici bağlam: TBB, Şubat 2026 çalıştayı sonrası "Avukatlar İçin Yapay Zekâ Kullanımı Tavsiye Rehberi" yayımladı: YZ avukatın mesleki sorumluluğunu devralamaz, anonimleştirme ve veri minimizasyonu şart. https://www.mondaq.com/turkey/new-technology/1847956/

## (e) Boşluk analizi: Hukuk-YZ'nin farklılaşabileceği noktalar

1. Mali müşavir ve İK persona'sı boş. Tüm hukuk YZ'leri avukat için "dilekçe + içtihat" kurgulu; mali müşavir araçları ise "Resmi Gazete özeti + büro yönetimi". İş hukuku sorusunu mali müşavirin diliyle (bordro, SGK bildirge, teşvik, İPC) soran kimse için ürün yok. (Kaynak: a ve b tabloları)
2. Olay tarihindeki mevzuat sürümü. Lexpera madde geçmişi tutuyor ama hiçbir YZ asistanı "fesih tarihi 2019 ise 2019 metnini uygula" demiyor. Bitemporal KB (m.4) burada tek olurdu.
3. Deterministik hesaplama motoru. mesnet.ai bu ilkeyi sadece usul süreleri için uyguluyor; LexChat hesabı LLM sandbox'ta kodla yapıyor (tekrar üretilebilirlik garantisi yok); Otto HR bordro hesabı yapıyor ama hukuki dayanak göstermiyor. Kıdem, ihbar, İPC, PEK hesabını mevzuat maddesi + Yargıtay içtihadı + açıklanabilir adımlarla üreten ürün yok (m.29).
4. SGK genelge katmanı. MALİİK Radar ve Müşavir AI genelgeleri takip ediyor ama içtihatla birleştirmiyor; hukuk YZ'leri genelgeleri hiç kaynak türü olarak saymıyor. 8 ayrı kaynak türü (m.28) ve genelge/özelge/Yargıtay çaprazlaması benzersiz.
5. Doğrulanmış kaynak nesnesi. Rakipler "kaynaklı cevap" diyor, ancak kaynak metnin veritabanında var olup olmadığını zorunlu kılan (m.25) ve doğrulanamayan atıfı kritik hata sayan tasarım hiçbirinde açıklanmıyor. turk-hukuku MCP yaklaşımı (model canlı resmi kaynaktan çeker) en yakın örnek, ama kurumsal ürün değil.
6. İçtihat otoritesi ağırlıklandırma (İBK > HGK > Daire > BAM, m.15-18). Rakipler karar sayısıyla (10M+) rekabet ediyor; Jupytr daire eğilimi analizi sunuyor. Otorite hiyerarşisine göre cevap üreten ürün bulunamadı. 6.342 editöryal seçilmiş karar, 10M ham karardan daha değerli konumlanabilir.
7. Uzman eskalasyonu. Hiçbir hukuk YZ'si "bu soru riskli, ücretli uzman görüşü al" akışı sunmuyor; Muhasebecin'in marketplace'i KOBİ'ye müşavir buluyor, hukuki görüş değil. TBB rehberinin "YZ sorumluluğu devralamaz" vurgusu bu akışı meşrulaştırıyor.
8. Fiyat pozisyonu. Avukat araçları 1.250 TL/ay (emsal.ai) ile 48.000 TL/yıl (Lexpera) arasında; mali müşavir araçlarının fiyatı bile ilan edilmemiş. Mali müşavir için 500-1.500 TL/ay bandı boş görünüyor (teyit gerekir).
9. Dağıtım kanalı. Rakipler web + UYAP eklentisi; emsal.ai ve turk-hukuku MCP sunuyor. Mali müşavirin yaşadığı yer Luca/Mikro/Logo ve WhatsApp; buralara entegrasyon (SMMM Asistan'ın WhatsApp örneği) rakiplerde yok.

Riskler: emsal.ai ve hukuk.chat 11M karar + mevzuatla "iş hukuku modülü" eklerse araştırma tarafında hızla yetişebilir; savunulabilir alan hesaplama motoru, bitemporal mevzuat ve SGK genelge katmanı. Lexpera'nın sürüm altyapısı + LEXI, 2 numaralı boşluğu kapatabilecek tek oyuncu.

## (f) Kaynak listesi

- https://emsal.ai/ (özellikler, "Plus 1.250 TL + KDV/ay" arama özeti), https://emsal.ai/blog/emsal-ai-mcp-karar-arama
- https://www.mesnet.ai/ , https://www.mesnet.ai/kayit
- https://www.musavirai.com.tr/ , https://www.musavirai.com.tr/hakkimizda , https://www.musavirai.com.tr/urunler/mobil
- https://www.maliikdernegi.com/mevzuat-radar
- https://mukellef.im/mali-musavir-programi
- https://www.muhasebecin.com.tr/
- https://smmmasistan.com/
- https://ottohr.com/bordro-programi
- https://kolayik.com/ , https://webrazzi.com/2021/02/02/kolay-ik-dan-yapay-zeka-destekli-insan-kaynaklari-dijital-asistani-kolay-sor/
- https://www.logo.com.tr/urun/logo-bordro-plus , https://www.furkanpezek.com.tr/2026/09/logo-edge-t-series-yapay-zeka-destekli-rapor-asistani-ve-dijital-danisman-kullanimi/
- https://www.mikro.com.tr/gelecegin-profesyonelleri-raporu/
- https://www.memurlar.net/haber/1075619/vergiyle-ilgili-sorulara-yapay-zekasiyla-calisan-gibi-yanit-veriyor.html
- https://hukuk.chat/
- https://www.lexpera.com.tr/ , https://www.lexpera.com.tr/lexi-yapay-zeka , https://www.lexpera.com.tr/musteri-hizmetleri/sikca-sorulan-sorular
- https://kazanci.com.tr/
- https://ictihatpro.com/fiyatlar (rakip fiyat tablosu, Mart 2026)
- https://jupy.tr/ , https://webrazzi.com/2026/06/26/yerli-akilli-hukuk-asistani-jupytr/
- https://hammurabi.tr/
- https://hukukos.com/
- https://lexchat.ai/
- https://www.dejure.ai/
- https://consultohukuk.com/
- https://www.sonkarar.com/
- https://turk-hukuku.com/en
- https://legalbank.net/arama
- https://mevzuat.adalet.gov.tr/
- https://www.mondaq.com/turkey/new-technology/1847956/the-use-of-artificial-intelligence-in-legal-practice-key-takeaways-from-the-union-of-turkish-bar-associations-guide
- https://lanturkey.com/en/blog/hukuk-teknolojisi-harvey
- https://www.thomsonreuters.com/en/cocounsel
- https://haqq.ai/blog/best-legal-ai-tools-2026
- https://apps.apple.com/in/app/hukukai/id6761995890 , https://producthunt.com/products/aida-hukuk
