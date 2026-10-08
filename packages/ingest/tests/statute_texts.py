"""Synthetic statute snapshot texts in the three layouts of the real files (rule-style footnotes,
numbered footnotes at the page bottom, marker-line footnotes). No real corpus text."""

HEADER_A = """DENEME KANUNU

\t\tKanun Numarası\t\t: 9001
\t\tKabul Tarihi\t\t: 22/5/2003
\t\tYayımlandığı R.Gazete\t: Tarih :  10/6/2003   Sayı : 25134
"""

RULE = "––––––––––––––––"


def rule_style() -> str:
    """Docx/doc layout: tab-led paragraphs, a rule + `(n)` footnotes, a bare page number."""
    return (
        HEADER_A
        + """
BİRİNCİ BÖLÜM
Genel Hükümler

\tAmaç ve kapsam
\tMadde 1 - Bu Kanunun amacı işçilerin hak ve sorumluluklarını düzenlemektir.(1)
\tİkinci fıkra metni burada biter.
"""
        + RULE
        + """
(1) 15/5/2008 tarihli ve 5763 sayılı Kanunun 38 nci maddesiyle bu fıkranın 1/7/2008
tarihinde yürürlüğe gireceği hüküm altına alınmıştır.
8424

\tTanımlar
\tMadde 2 - (Değişik: 12/10/2017-7036/11 md.) İşçi, iş sözleşmesiyle çalışan kişidir.
\tİşveren işçi çalıştıran kişidir.
\tMadde 3 - (Mülga: 20/6/2012-6331/37 md.)
\tEngelli çalıştırma zorunluluğu(2)
\tMadde 5 - Engelli işçi çalıştırılır.
"""
        + RULE
        + """
(2) 20/6/2012 tarihli ve 6331 sayılı Kanunun 37 nci maddesiyle bu madde başlığı değiştirilmiştir.

\tGeçici Madde 1 - Bu madde geçicidir.
\tEk Madde 1 – (Ek: 6/2/2014-6518/59 md.) Ek madde metni.
"""
    )


def numbered_style() -> str:
    """PDF layout: form-feed pages, `47 text` footnotes at the page bottom, glued markers."""
    page1 = """DENEME KANUNU
Kanun Numarası : 9002
Kabul Tarihi : 31/5/2006
Yayımlandığı Resmî Gazete : Tarih: 16/6/2006 Sayı: 26200
BİRİNCİ KISIM
Amaç ve Tanımlar
Amaç
MADDE 1- Bu Kanunun amacı, sosyal sigortaları düzenlemek ve
işleyişe ilişkin usûl ve esasları belirlemektir.
Kapsam
MADDE 2- Bu Kanun, sigortalıları kapsar. Ancak 15 gün
süreyle çalışanlar bu hükmün dışındadır.1
1 13/2/2011 tarihli ve 6111 sayılı Kanunun 25 inci maddesiyle bu fıkra
değiştirilmiştir."""
    page2 = """Yaşlılık aylığının başlangıcı ve kesilmesi2
MADDE 3- (Değişik: 17/4/2008-5754/18 md.) Yaşlılık aylığı
istek tarihinden sonraki ay başından itibaren bağlanır.
Engelli ve eski hükümlü çalıştırma zorunluluğu34
MADDE 4- İşveren engelli çalıştırır.
2 Bu madde başlığı "Yaşlılık aylığı" iken, 29/1/2016 tarihli ve 6663 sayılı
Kanunun 24 üncü maddesiyle metne işlendiği biçimde değiştirilmiştir.
3 2/1/2017 tarihli ve 680 sayılı KHK’nin 73 üncü maddesiyle başlık değiştirilmiştir.
4 4/4/2015 tarihli ve 6645 sayılı Kanunun 44 üncü maddesiyle ibare çıkarılmıştır."""
    page3 = """Sosyal güvenlik hakkı
MADDE 5- Herkes sosyal güvenlik hakkına sahiptir.
Yürütme
MADDE 6- Bu Kanun hükümlerini Bakanlar Kurulu yürütür."""
    page3 += """31/5/2006 TARİHLİ VE 9002 SAYILI KANUNA İŞLENEMEYEN
GEÇİCİ MADDELER
GEÇİCİ MADDE 1 – Bu madde kanuna işlenmemiştir."""
    return "\f".join([page1, page2, page3])


def marker_line_style() -> str:
    """PDF layout of the 4857 file: the footnote number stands on its own line."""
    page1 = """İŞ KANUNU
Kanun Numarası : 9003
Kabul Tarihi : 22/5/2003
Yayımlandığı Resmî Gazete : Tarih: 10/6/2003 Sayı: 25134
Amaç ve kapsam
Madde 1 - Bu Kanunun amacı işçilerin haklarını düzenlemektir.
Kanunun verdiği yetkiye dayanarak;1
a) Birinci bent,
b) İkinci bent.
1
 2/7/2018 tarihli ve 700 sayılı KHK’nin 145 inci maddesiyle, bu fıkrada yer alan “kanunun verdiği
yetkiye” ibaresi “Cumhurbaşkanlığı kararnamesine” şeklinde değiştirilmiştir."""
    page2 = """Madde 87 (Mülga: 20/6/2012-6331/37 md.)
Tanımlar
Madde 88 - İşçi, çalışan kişidir."""
    return "\f".join([page1, page2])
