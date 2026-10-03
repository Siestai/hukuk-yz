# Demo verisi (sentetik)

**Bu dizindeki her şey kurgusaldır / SYNTHETIC.** Gerçek karar, dava numarası, taraf veya kişi
yok; esas ve karar numaraları 2031–2032 aralığındadır (henüz var olmayan yıllar), metinler ve
özetler baştan sona uydurmadır ve hiçbir hukuki değeri yoktur. Amaç: özel arşive (`data/drive`,
telif ve KVKK nedeniyle repoda yok) ihtiyaç duymadan inceleme arayüzünü ve uçtan uca testleri
çalıştırmak.

## İçerik

- `decisions.jsonl`: `hukuk-ingest decisions parse` çıktısıyla aynı biçimde 12 kayıt. Yükleyici
  (`python -m app.loaders.decisions`) bunları olduğu gibi okur.
- `files.jsonl`: `hukuk-ingest scan` çıktısı biçiminde dosya kayıtları (yol, sha256, boyut, tür).
- `archive/Yargi_Kararlari_Arsivi/…`: her kayıt için 1 sayfalık, 1 KB'den küçük geçerli PDF.
  `ARCHIVE_ROOT` buraya işaret ettiğinde karar ekranının PDF sekmesi çalışır.
- `generate.py`: hepsini baştan üretir (`python infra/demo/generate.py`; çıktı deterministiktir).

Yükleyici güven bandını kendisi hesaplar: 6 yüksek, 4 orta, 2 düşük. İki mahkeme (Yargıtay,
BAM), bir mükerrer çift (Demo 10 ve 11: aynı mahkeme, daire, E/K ve metin; uzun olan orta, diğeri
düşük) ve birkaç sebep (`date_from_closing`, `header_closing_date_mismatch`,
`statute_inferred_from_date`, `missing_karar_no`, `body_not_found`) vardır.

## Kullanım

```bash
make dev          # yığını başlat (docs/local-dev.md)
make demo-data    # bu kayıtları yükle ve app'in arşiv bağını demo arşive çevir
```

Demo ile gerçek arşiv arasında geçiş: `.env` içindeki `ARCHIVE_HOST_DIR` app konteynerine salt
okunur `/archive` olarak bağlanır. `make demo-data` onu `../../infra/demo/archive` yapar,
`make load-archive` `../../data/drive`'a döndürür; sonra app yeniden oluşturulur. Veritabanı
ayrıdır: demo kayıtlarını silmek için `make db-reset`.

Uçtan uca testler (`pnpm e2e`) bu kayıtları **tüketir** (onaylar, reddeder): tekrar çalıştırmadan
önce `make db-reset demo-data` ile başa dönün.
