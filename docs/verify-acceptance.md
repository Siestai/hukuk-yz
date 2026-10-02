# Canlı kabul kontrolü: resmî kaynak teyidi (Görev 06)

Bu kontrol Orhan'ın Mac'inde (Türkiye çıkışlı IP) elle koşulur. Veritabanı gerekmez; hiçbir şey saklanmaz, yalnızca "karar → sonuç" yazılır. Toplam en çok 48 istek, kaynak başına 12 sn aralık (kod bunun altına inmeyi reddeder). Süre: yaklaşık 10 dakika. Karar metni veya taraf adı çıktıda yer almaz.

## Hazırlık

```sh
git checkout feat/task-06-decision-verification && uv sync
export LIVE=1                         # olmadan hiç istek atılmaz
export VERIFY_CONTACT=<e-posta>       # User-Agent'a girer, zorunlu
# Yargıtay Mac'ten de açılmazsa: export VERIFY_PROXY_YARGITAY=http://<proxy>:<port>
```

## Kontrol edilecek kararlar

Hepsi herkese açık E/K (Görev 06 probe'u, Görev 04 örneklemi ve spike dokümanı); metin yok.

```sh
cat > /tmp/verify-keys.jsonl <<'JSON'
{"court":"aym","esas_no":"2024/157","karar_no":"2025/121","decision_date":"2025-06-03","decision_kind":"norm_denetimi"}
{"court":"aym","esas_no":"2023/158","karar_no":"2024/187","decision_kind":"norm_denetimi"}
{"court":"aym","esas_no":"2015/105","karar_no":"2016/133","decision_kind":"norm_denetimi"}
{"court":"aym","esas_no":"2024/41763","decision_date":"2025-07-08","decision_kind":"bireysel_basvuru"}
{"court":"bam","chamber":"9. HD","bam_region":"Gaziantep","esas_no":"2022/1258","karar_no":"2022/1822","decision_date":"2022-12-29"}
{"court":"bam","chamber":"9. HD","bam_region":"Gaziantep","esas_no":"2022/1258","karar_no":"2022/1822","decision_date":"2022-12-01"}
{"court":"bam","chamber":"7. HD","bam_region":"İstanbul","esas_no":"2021/2221","karar_no":"2023/300","decision_date":"2023-05-04"}
{"court":"danistay","chamber":"10. D","esas_no":"2026/940","karar_no":"2026/402","decision_date":"2026-02-05"}
{"court":"danistay","chamber":"10. D","esas_no":"2004/6075","karar_no":"2006/2159"}
{"court":"danistay","chamber":"3. D","esas_no":"2006/3799","karar_no":"2007/414"}
{"court":"yargitay","chamber":"9. HD","esas_no":"2023/9892","karar_no":"2023/8738","decision_date":"2023-06-07"}
{"court":"yargitay","chamber":"9. HD","esas_no":"2016/24818","karar_no":"2016/16859","decision_date":"2016-09-29"}
{"court":"yargitay","chamber":"7. HD","esas_no":"2013/22557","karar_no":"2014/3546","decision_date":"2014-02-11"}
{"court":"yargitay","court_level":"hgk_iddk","esas_no":"2018/389","karar_no":"2021/191","decision_date":"2021-03-02"}
{"court":"yargitay","chamber":"9. HD","esas_no":"2008/298872","karar_no":"2008/25202","decision_date":"2008-10-06"}
JSON
```

## Koşu (kaynak başına ayrı, istek sınırıyla)

```sh
run() { uv run python -m app.verification --keys /tmp/verify-keys.jsonl --court "$1" --limit "$2" --report "/tmp/verify-$1"; }
run aym 14
run bam 8
run danistay 8
run yargitay 18
```

`--limit` kaynak başına istek sayısıdır (robots.txt ve oturum sayfası dahil); 14 + 8 + 8 + 18 = 48 ≤ 50. `--i-have-permission` kullanılmaz. Bir kaynakta "stopped" yazarsa (429, captcha, robots, bütçe) o kaynak orada kesilir; yeniden denemeden önce en az 5 dakika bekle.

## PR'a yapıştırılacak çıktı

Konsol çıktısının tamamı (her karar için bir satır `<mahkeme> <daire> E. … K. … -> <sonuç>` ve kaynak başına bir özet satırı), ardından `cat /tmp/verify-*/verify-summary.md`.

Beklenen (probe ve spike ile uyum):

| Kaynak | Beklenen |
|---|---|
| aym | ilk üçü `verified_official`; bireysel başvuru satırı elle yorumlanır (probe'da denenmedi, `basvuruNo` eşlemesi varsayım) |
| bam | Gaziantep 29.12.2022 `verified_uyap`; aynı karar 01.12.2022 ile `mismatch` (`decision_date`); İstanbul 7. HD sonucu not edilir (Emsal kapsamı belirsiz) |
| danistay | 2026 kararı `verified_official`; 2004/2006 kararları probe'daki gibi `not_in_source` |
| yargitay | 2023 ve 2016 `verified_official`; 2014 ve HGK sonuç not edilir; 2008 `not_in_source` (2009 öncesi örneklem sorgusu olarak gerçekten sorulur, bulunursa bu bir bulgudur) |

Yargıtay satırları `error (SourceUnavailable: …)` çıkarsa site bu ağdan da açılmıyordur: proxy ile yeniden dene ve PR'a bunu yaz.
