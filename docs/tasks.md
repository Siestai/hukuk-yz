# Görevler

## Themis
- [ ] İsim adayı listesi (15-20 aday, anlam + gerekçe + domain kontrolü) → Orhan'a, sonra gruba
- [ ] Kaynak site listesi ortaklardan gelince: her site için çekme/doğrulama yöntemi + otorite seviyesi eşlemesi
- [ ] Eskalasyon tetikleme kriterleri taslağı (konu sınıfı, süre, belirsizlik) → architecture.md
- [ ] 2018/38 sayılı Emeklilik İşlemleri Genelgesi tam metnini resmî kaynaktan al, arşive ekle (grupta kaynak gösteremedim)
- [ ] 5434 sayılı Emekli Sandığı Kanunu metnini arşive ekle (4/c eski iştirakçiler için gerekli)
- [ ] gh + claude CLI kurulumu, test PR (GH_TOKEN + ANTHROPIC_API_KEY bekleniyor)
- [ ] architecture.md ilk taslak (gereksinim m.4, 25, 28, 29, 33 çapaları)
- [x] Görev 12c: mevcut Drive arşivinin içeri alınması + PDF sunumunun saklama katmanına geçişi (uygulandı, PR Orhan'ın onayında; ayrıntı `docs/tasks/12-file-management.md`)
- [x] Görev 12d: arşiv satırlarının belge türü Drive klasöründen (`gorus` türü, içe aktarma düzeltmesi, `backfill_doc_type` CLI; uygulandı, PR Orhan'ın onayında; ayrıntı `docs/tasks/12-file-management.md`)
- [x] Görev 13a: yüklemede otomatik tespit, eşleşme, onay ve silme (backend; PR #62 birleşti; ayrıntı `docs/tasks/13-upload-detect-approve.md`)
- [ ] Görev 13b: dashboard yükleme + onay ekranı (uygulandı, PR Orhan'ın onayında; canlıda `hukuk-yz-live-verify` ile video çekilecek)
- [ ] Görev 13c: arşiv kararları "benzer dosya" eşleşmesinde (hata düzeltmesi; uygulandı, PR Orhan'ın onayında; ayrıntı `docs/tasks/13c-similar-archive-text.md`)
- [ ] Görev 10i: karar detayında PDF penceresi ve hep görünür "Düzelt" (uygulandı, PR Orhan'ın onayında; ayrıntı `docs/tasks/10i-detail-pdf-sticky-edit.md`)
- [ ] Görev 10j: statuses e2e "Onaydan çıkar" testi sabit inceleyen adı yüzünden düşüyordu (uygulandı, PR Orhan'ın onayında; ayrıntı `docs/tasks/10j-e2e-statuses-fix.md`)
- [ ] Görev 10l: AYM bireysel başvuru kararları Başvuru No + tarihle gösterilir, Karar no yüzünden düşük banda düşmez (uygulandı, PR Orhan'ın onayında; ayrıntı `docs/tasks/10l-aym-application-no.md`). Canlıda mevcut kayıtlar için: migrasyon sonrası `python -m app.loaders.rescore`
- [ ] Görev 10k: telefonda PDF görüntüleyici, PDF.js ile sayfalar canvas'a çizilir (uygulandı, PR Orhan'ın onayında; merge sonrası gerçek Android Chrome'da doğrulanacak; ayrıntı `docs/tasks/10k-mobile-pdf-viewer.md`)
- [ ] 13a canlıya çıkmadan: LLM sağlayıcısı + bölge + anahtar kararı (Orhan), `FILE_DETECT_LLM_*` ayarları (deploy.md); o zamana kadar tespit yalnız kurallarla çalışır
- [ ] Görev 12e (öneri, 12c'nin hemen ardından): `filestore` volume'ünün zamanlanmış yedeği; o zamana kadar tek kopya sunucu diskinde (deploy.md)
- [ ] 12c sonrası: tam Drive aktarımında 43 `Eskiler/` dosyası güncel dosyayla eşleşmedi; İbrahim'le elle bağlama ya da ad kuralı (decisions.md)

## Orhan
- [ ] `.env`'e GH_TOKEN ve ANTHROPIC_API_KEY (Claude Code ile)
- [ ] GitHub profil: Name "Themis"
- [ ] Yargı kararları arşivi telif sorusu (Çalışma ve Toplum özetleri) gruba sorulacak mı?

## Ortaklar (Baran / İbrahim)
- [ ] Kaynak site listesi (otorite seviyesiyle)
- [ ] Eskalasyon modeli: fiyatlandırma, SLA, kapsam
- [ ] AYM / İBK / HGK / Danıştay toplama kriterleri (konu, tarih aralığı, öncelik)
- [ ] Gereksinim m.10 "kapalı ve sınırlı liste" yazım hatası mı?
