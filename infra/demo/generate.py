"""Regenerate the synthetic demo fixture (decisions.jsonl, files.jsonl, archive/*.pdf) and,
given the real output of `hukuk-ingest statutes`, the statute fixture (statutes.jsonl).

    python infra/demo/generate.py
    python infra/demo/generate.py --statutes path/to/statutes.jsonl

Standard library only; the output is deterministic, so a regenerated fixture shows no diff. Every
case number, date and text here is invented (see README.md): the numbers are in the 2031-2032
range, which no real decision has yet.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ARCHIVE = HERE / "archive"
PARSER_VERSION = "5"

# The text of every demo decision: three paragraphs, so the text tab has something to scroll.
BODY = (
    "[KURGUSAL DEMO METNİ] Davacı, {topic} talebiyle açtığı davada, davalı işverenin iddiaya "
    "karşı savunma yaptığını ileri sürmüştür. Mahkeme, tarafların delillerini toplamış ve "
    "dosyadaki bilgi ve belgeleri değerlendirmiştir.\n\n"
    "Gerekçe: Dosya içeriğine göre uyuşmazlık, olayın gerçekleştiği tarihte yürürlükte olan "
    "hükümlere göre çözülmelidir. Davalının itirazları bu kapsamda incelenmiş, hesaplamanın "
    "bilirkişi raporuyla yapılmasında usul ve yasaya aykırılık görülmemiştir.\n\n"
    "Sonuç: Bu metin yalnızca arayüzü denemek için üretilmiştir; gerçek bir karar değildir ve "
    "hiçbir hukuki değeri yoktur. Tarafların ve olayların hepsi kurgusaldır, bir karar sonucu "
    "belirtmek amacı taşımaz."
)

Rec = dict[str, Any]
ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")  # file names stay ASCII (macOS normalizes)


def rec(
    n: int,
    *,
    topic: str,
    court: str = "yargitay",
    level: str = "daire",
    chamber: str = "9. HD",
    esas: str,
    karar: str,
    date: str,
    statute: int = 4857,
    articles: tuple[str, ...] = ("17",),
    outcome: str = "bozma",
    issue: int = 91,
    warnings: tuple[str, ...] = (),
    region: str = "",
    **over: Any,
) -> Rec:
    name = f"Demo {n:02d} {topic.translate(ASCII)}.pdf"
    row: Rec = {
        "source_path": f"Yargi_Kararlari_Arsivi/{issue}. Sayi-Demo/{name}",
        "sha256": "",
        "status": "ok",
        "error": None,
        "journal_issue": issue,
        "journal_year": None,
        "journal_no": None,
        "journal_page": 10 + n,
        "layout": "era2_classic",
        "parser_version": PARSER_VERSION,
        "court": court,
        "court_level": level,
        "chamber": chamber,
        "source_chamber": "",
        "bam_region": region,
        "decision_kind": "karar",
        "jurisdiction": "adli",
        "esas_no": esas,
        "karar_no": karar,
        "decision_date": date,
        "related_articles": [
            {"statute": statute, "articles": list(articles), "label": "İşK", "raw": ""}
        ],
        "keywords": [topic, "demo"],
        "outcome": outcome,
        "editorial_summary": f"Kurgusal özet: {topic} üzerine örnek bir karar (demo verisi).",
        "full_text": BODY.format(topic=topic),
        "text_completeness": "full",
        "verification": "unverified",
        "missing": [],
        "warnings": list(warnings),
    }
    row.update(over)
    return row


RECORDS: list[Rec] = [
    # high: nothing to flag
    rec(1, topic="kıdem tazminatı", esas="2031/1001", karar="2031/2001", date="2031-02-11"),
    rec(
        2,
        topic="fazla mesai",
        esas="2031/1002",
        karar="2031/2002",
        date="2031-03-18",
        articles=("41",),
        outcome="onama",
    ),
    rec(
        3,
        topic="yıllık izin ücreti",
        chamber="22. HD",
        esas="2031/1003",
        karar="2031/2003",
        date="2031-05-06",
        articles=("53", "59"),
        outcome="onama",
    ),
    rec(
        4,
        topic="sendikal tazminat",
        chamber="22. HD",
        esas="2032/1004",
        karar="2032/2004",
        date="2032-01-22",
        statute=6356,
        articles=("25",),
        outcome="kabul",
    ),
    rec(
        5,
        topic="iş kazası tazminatı",
        esas="2032/1005",
        karar="2032/2005",
        date="2032-03-09",
        statute=6098,
        articles=("49",),
        outcome="düzelterek onama",
    ),
    rec(
        6,
        topic="işe iade",
        chamber="22. HD",
        esas="2032/1006",
        karar="2032/2006",
        date="2032-04-14",
        statute=4857,
        articles=("18", "19", "20", "21"),
    ),
    # medium: the parser guessed or the record contradicts itself
    rec(
        7,
        topic="ihbar tazminatı",
        esas="2031/1007",
        karar="2031/2007",
        date="2031-06-25",
        articles=("17",),
        warnings=("date_from_closing",),
    ),
    rec(
        8,
        topic="haksız fesih",
        chamber="22. HD",
        esas="2032/1008",
        karar="2032/2008",
        date="2032-05-19",
        articles=("25",),
        warnings=("header_closing_date_mismatch",),
    ),
    rec(
        9,
        topic="asgari geçim indirimi",
        court="bam",
        level="bam_bim",
        chamber="7. HD",
        region="Ankara",
        esas="2032/1009",
        karar="2032/2009",
        date="2032-06-03",
        outcome="red",
        warnings=("statute_inferred_from_date",),
    ),
    # a duplicate pair (same court, chamber, E/K and text in two issues): the longer copy is
    # medium, the other one low
    rec(
        10,
        topic="ücret alacağı",
        esas="2031/1010",
        karar="2031/2010",
        date="2031-09-30",
        outcome="onama",
    ),
    rec(
        11,
        topic="ücret alacağı",
        esas="2031/1010",
        karar="2031/2010",
        date="2031-09-30",
        outcome="onama",
        issue=92,
    ),
    # low: no karar no and no body (summary only)
    rec(
        12,
        topic="mobbing",
        chamber="22. HD",
        esas="2032/1012",
        karar="",
        date="2032-07-07",
        statute=6098,
        articles=("417",),
        full_text="",
        text_completeness="summary_only",
        warnings=("body_not_found",),
        missing=["karar_no", "full_text"],
    ),
]


def pdf(lines: list[str]) -> bytes:
    """The smallest valid one-page PDF with a few lines of Helvetica text."""
    text = "BT /F1 12 Tf 72 740 Td 16 TL " + " T* ".join(f"({s}) Tj" for s in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(text)} >>\nstream\n{text}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out


# The statute fixture: seven articles of 4857 picked from a real `statutes.jsonl` (public law
# text, no personal data), unchanged. They cover every case the statute review screen shows:
# high (1, 9), medium with a gap (18), medium with two versions and a gap (20), repealed (33),
# Geçici (Geçici 1, start unverified) and low with two versions and gaps (Ek 2).
STATUTE = "4857"
STATUTE_ARTICLES = ("1", "9", "18", "20", "33", "Geçici 1", "Ek 2")


def statute_fixture(source: Path) -> str:
    """The `statutes.jsonl` line of the demo: the 4857 record of `source` reduced to
    `STATUTE_ARTICLES`, in their original order."""
    for line in source.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["number"] == STATUTE:
            articles = {a["article_no"]: a for a in record["articles"]}
            record["articles"] = [articles[no] for no in STATUTE_ARTICLES]
            for snapshot in record["snapshots"]:
                snapshot["articles"] = len(STATUTE_ARTICLES)
            return json.dumps(record, ensure_ascii=False) + "\n"
    raise SystemExit(f"no record for statute {STATUTE} in {source}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--statutes", type=Path, help="real statutes.jsonl to pick the articles of")
    args = parser.parse_args()
    if args.statutes:
        (HERE / "statutes.jsonl").write_text(statute_fixture(args.statutes), encoding="utf-8")
    files = []
    for n, row in enumerate(RECORDS, 1):
        content = pdf(
            [
                f"DEMO {n:02d} - KURGUSAL KARAR (SYNTHETIC)",
                f"{row['chamber']}  E. {row['esas_no']}  K. {row['karar_no'] or '-'}",
                "Bu belge arayuzu denemek icin uretilmistir; gercek bir karar degildir.",
            ]
        )
        assert len(content) < 2048
        row["sha256"] = hashlib.sha256(content).hexdigest()
        target = ARCHIVE / row["source_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        files.append(
            {
                "path": row["source_path"],
                "sha256": row["sha256"],
                "size": len(content),
                "ext": ".pdf",
                "detected_type": "pdf",
                "extension_mismatch": False,
                "status": "ok",
            }
        )
    for name, rows in (("decisions.jsonl", RECORDS), ("files.jsonl", files)):
        with (HERE / name).open("w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


if __name__ == "__main__":
    main()
