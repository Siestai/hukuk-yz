# Yol Haritası v0.1

Durum: taslak, 2026-10-02. Haftalar yaklaşık; ekip Orhan + Claude Code + Themis (+ ortaklar veri incelemesinde).

## Faz 0: Tasarım (toplantıya kadar)

- [x] Veri envanteri (AGENTS.md)
- [x] Mimari, veri modeli, yol haritası (bu PR)
- [ ] Toplantı: isim, telif, KVKK/LLM bölgesi, kaynak listesi, üst mahkeme kriterleri, eskalasyon kapsamı
- [ ] Hesap motoru / atıf kapısı yeri kararı (Orhan)

## Faz 1: Knowledge base + dashboard (6-8 hafta)

Agent yok. Çıktı: ortakların arama yapıp veriyi doğrulayabildiği, veri yükleyip onaylayabildiği bir sistem.

**Hafta 1-2: iskelet + şema + parser çekirdeği**
- Monorepo, uv/pnpm workspace, compose, CI (ruff/mypy/pytest/eslint)
- Alembic ilk şema (`data-model.md` §10)
- `packages/ingest`: tip tespiti, metin çıkarma (pdf/docx/doc/udf), temizleme
- Karar parser'ı, 4 düzen; test seti her düzenden 20 dosya, elle doğrulanmış
- `packages/citation`: ref ayrıştırma (mevzuat + karar + genelge)

**Hafta 3-4: worker + toplu yükleme**
- `services/app` iskeleti, auth (basit, org/kullanıcı), `worker` giriş noktası, Postgres kuyruğu
- 6.342 karar toplu işleme, QA raporu (alan doluluk, çözümlenemeyen atıflar, düzen tespiti hataları)
- Kanun madde bölme; 4857 + 5510 madde düzeyi; `Eskiler/` ile sürüm diff denemesi

**Hafta 5-6: dashboard v0**
- `app` admin API: upload, job durumu, inceleme/onay, KB arama, kullanıcı/org
- `dashboard-web`: yükle → analiz → incele/onayla → yayınla; arama ekranı; job listesi
- `packages/ui` + design token'lar (nötr tema, marka sonra)
- Ortaklar kullanmaya başlar; geri bildirim

**Hafta 7-8: tampon**
- Mevzuat sürümleme borcu
- Genelge parser'ı (e-imzalı PDF stratejisi)
- `/citation/resolve` + `/kb/search` (hibrit) tamam
- Kaynak crawler v0 (liste gelirse)
- Embedding model eval

## Faz 2: Agent çekirdeği (6-8 hafta)

- `services/agent`: LangGraph, md. 33 düğümleri (önce 8-12 düğümlük sade sürüm, sonra genişler)
- LLM gateway + maliyet log
- Atıf kapısı canlı (md. 25)
- `packages/calc` v0: kıdem, ihbar, yıllık izin; Excel'ler test oracle
- `services/memory` v0: store/recall/forget, bitemporal, scope
- **Eval seti**: Baran/İbrahim'in soruları + beklenen atıflar + beklenen eksik-bilgi soruları; CI'da
- `interrupt`: eksik bilgi sorusu, eskalasyon işareti
- Kanal: web chat (basit) + Telegram adaptörü (`app` içinde)
- NATS (ingest/escalation event'leri)
- Dashboard: AI tüketim ve maliyet ekranı

## Faz 3: Ürünleşme

- Marka ve tasarım (toplantı kararından sonra başlar, Faz 2 ile paralel)
- `services/web`: atıf chip'leri, kesinlik rozeti, gerekçe zinciri, eksik bilgi bloğu
- `proxy`: Traefik + ForwardAuth
- Eskalasyon akışı (uzman kuyruğu, ücretli görüş)
- Ödeme (iyzico/PayTR), abonelik, e-fatura araştırması
- Helm chart, k8s deploy
- KVKK: aydınlatma, açık rıza, silme akışı

## Riskler

| Risk | Etki | Azaltma |
|---|---|---|
| Çalışma ve Toplum telif | Arşivin editoryal kısmı kullanılamaz | Özetler `internal_only`; tam metinler kamu kararı; izin iste; B planı: resmi kaynaklardan yeniden toplama |
| Mevzuat sürümleme zorluğu | md. 4 karşılanamaz | 4857 + 5510 ile başla; `valid_from` bulunamayınca insan sorar; mevzuat.gov.tr crawler Faz 1 sonunda |
| LLM yurt dışı aktarım (KVKK) | Gerçek dosya verisiyle çalışılamaz | EU region; toplantıda karar; o zamana kadar anonim/sentetik test verisi |
| Üst mahkeme kapsamı zayıf | md. 15-17 eksik | Ayrı toplayıcı; Baran'ın kriterleri |
| Parser %5 hata | Yanlış atıf = kritik hata | İnsan onayı zorunlu; güven eşiği; QA raporu; eval |
