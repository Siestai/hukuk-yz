# Demo verisi (sentetik)

**Bu dizindeki her şey kurgusaldır / SYNTHETIC (tek istisna: kamu metni olan `statutes.jsonl`, aşağıya bakın).** Gerçek karar, dava numarası, taraf veya kişi
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
- `statutes.jsonl`: `hukuk-ingest statutes` çıktısıyla aynı biçimde tek kayıt: 4857 sayılı İş
  Kanunu'nun 7 maddesi (1, 9, 18, 20, 33, Geçici 1, Ek 2). **Bu dosya kurgusal değildir:** gerçek
  çıktıdan olduğu gibi seçilmiş kamu metnidir (kişisel veri yok), mevzuat ekranını denemek
  içindir. Bantlar: 2 yüksek (1, 9), 4 orta (18, 20, 33, Geçici 1), 1 düşük (Ek 2); 18, 20, 33, Geçici 1
  ve Ek 2'de zaman çizelgesinde boşluk, 33 mülga, 20 ve Ek 2 iki sürümlü. Yükleyici
  (`python -m app.loaders.statutes`) onaysız yükler: yedisi de bekleyen kuyruğa düşer, yayına
  (`as_of`) hiçbiri girmez.
- `generate.py`: hepsini baştan üretir (`python infra/demo/generate.py`; çıktı deterministiktir).
  `statutes.jsonl`, gerçek bir çıktıdan yeniden seçmek için `--statutes <statutes.jsonl>` ister;
  verilmezse dokunulmaz.

Karar yükleyicisi güven bandını kendisi hesaplar: 6 yüksek, 4 orta, 2 düşük. İki mahkeme (Yargıtay,
BAM), bir mükerrer çift (Demo 10 ve 11: aynı mahkeme, daire, E/K ve metin; uzun olan orta, diğeri
düşük) ve birkaç sebep (`date_from_closing`, `header_closing_date_mismatch`,
`statute_inferred_from_date`, `missing_karar_no`, `body_not_found`) vardır.

## Kullanım

```bash
make dev          # yığını başlat (docs/local-dev.md)
make demo-data    # bu kayıtları (kararlar ve mevzuat) yükle ve app'in arşiv bağını demo arşive çevir
```

Demo ile gerçek arşiv arasında geçiş: `.env` içindeki `ARCHIVE_HOST_DIR` app konteynerine salt
okunur `/archive` olarak bağlanır. `make demo-data` onu `../../infra/demo/archive` yapar,
`make load-archive` `../../data/drive`'a döndürür; sonra app yeniden oluşturulur. Veritabanı
ayrıdır: demo kayıtlarını silmek için `make db-reset`.

Uçtan uca testler (`pnpm e2e`) bu kayıtları **tüketir** (onaylar, reddeder): tekrar çalıştırmadan
önce `make db-reset demo-data` ile başa dönün.
