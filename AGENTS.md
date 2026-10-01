# hukuk-agent

An AI legal research and reasoning assistant for Turkish labour and social security law. It covers iş hukuku, SGK, sendika/TİS and İSG. Partners: Orhan (software), Baran and İbrahim (legal; approvers at institutions). Status 2026-10-01: data exploration is done; no app code yet.

## Source of requirements

- **Primary spec:** `~/Desktop/İş ve Sosyal Güvenlik Hukuku Yapay Zekâsı Kuralları.pdf`. It has 37 articles; "md. N" below refers to them. Every design decision must trace back to it.
- **Core rules:**
  - Decide legal status and critical dates first.
  - Apply the law in force on the event date, not today's law.
  - Keep source types separate: mevzuat / international / case law / administrative / TİS / case documents / doctrine / calculations (md. 28).
  - Judicial authority order (md. 15–16):
    - Adli yargı: AYM → Yargıtay İBK → HGK → daire → BAM.
    - İdari yargı: AYM → Danıştay İDDK → kurullar → daire → BİM.
  - **Never cite an unverified source** (md. 25).
  - Calculations run in a deterministic engine, never in the LLM (md. 29).
  - Comply with KVKK (md. 31) and copyright/licensing (md. 32).
- **Possible typo in md. 10:** "kapalı ve sınırlı liste" probably means an open list. Confirm with partners.

## Data (`data/`, gitignored: copyright + KVKK)

- `data/drive/`: rclone copy of İbrahim's Drive folder "Projem". 6,626 files, 1.3 GB, verified with `rclone check`.
  - Sync command: `rclone copy projem: data/drive`. The remote uses a read-only scope and our own OAuth client.
  - `Yargi_Kararlari_Arsivi/`: 6,342 decision files, one per file. They come from the decisions section of the journal **Çalışma ve Toplum**, issues 1–90 (https://yargi.calismatoplum.org). Issue 8 does not exist on the site either.
    - 6,334 are text-layer PDFs; no bulk OCR is needed.
    - 2 are `.doc` files saved as `.pdf`.
    - 6 are failed downloads (the site's HTML index page). Those decisions are missing; re-fetching them needs approval.
  - `Mevzuat/`: 280 files in Kanunlar, Genelge, Genel Yazı, Yönetmelik (+İSG), Tebliğ, Görüş, Diğer and Yargı Kararları. Each has an `Eskiler/` subfolder for older versions.
    - Formats: PDF, Word, UYAP `.udf` (a zip with XML inside), images.
    - E-signed SGK genelge PDFs extract as scrambled text and need layout-aware extraction or OCR.
  - Root: 4 Excel calculators (SGK Otomasyon, Bordro, Net-Brüt, İPC-PEK). Use them only as test oracles for the calculation engine; they are not legal norms.
  - `Kitaplar/`: empty so far.
- `data/text/`: cached `pdftotext` output of every decision.

## Decision archive findings

- **Issuing court** (classified from the header):

  | Court | Count |
  |---|---|
  | Yargıtay daire | 5,649 (9. HD 3,627; 22. HD 878; 10. HD 527; 21. HD 310; 7. HD 298) |
  | BAM | 297 (issues 76–90) |
  | HGK | 154 |
  | Foreign (ABAD, Alman Federal) | 64 |
  | AYM | 51 |
  | AİHM | 12 |
  | **İBK** | **5** |
  | Danıştay | 4 |

  Top-court coverage is thin, so a separate collector is needed (Baran's request).
- **Field coverage:** daire 98.5%, esas 95.7%, karar no 96%, tarih 95.8%, ilgili kanun 98.4%, ÖZETİ/ÖZÜ 99.2%.
- **Four layout eras.** The parser can be regex-based; it must detect file type by content, not by extension.
  1. Issues ~1–15: `İlgili Kanun/md:` → `ÖZÜ` → court + `ESAS NO:/KARAR NO:/TARİHİ:` **after** the summary.
  2. Issues ~16–75: İlgili Kanun → T.C. YARGITAY → n. HUKUK DAİRESİ → Esas/Karar/Tarihi → bulleted keywords → `ÖZETİ` → `DAVA:` … `SONUÇ:`.
  3. Issues in the 40s: two-column layout, so labels and values land on separate lines.
  4. Issues ~76–90: page header `Çalışma ve Toplum, YYYY/N`; body in the new Yargıtay template `I. DAVA … V. GEREKÇE … VI. KARAR`.
- **Noise to strip:** journal page numbers, repeated page headers, bullet glyphs (⚫ •), justified one-word lines, occasional OCR diacritic errors (`Î`).
- **The journal's ÖZETİ is editorial content.** Flag it as such and verify against official sources (md. 20, 26). Check permission to show it to end users.

## Planned pipeline and record

- **Pipeline:** ingest → detect type by content → extract text → clean → parse fields → normalize (daire, ISO dates, `4857 S. İşK/18-21` → `{kanun: 4857, maddeler: [18..21]}`) → QA report → verify (E/K against official Yargıtay/UYAP Emsal) → DB.
- **Per-decision record:**
  - court, decision type, daire, esas, karar no, date, jurisdiction branch
  - related statutes and articles, keywords, summary, full text, outcome
  - provenance (journal issue, file, hash)
  - full-text vs summary flag, verification status
- **Mevzuat is a separate pipeline:** article-level, with point-in-time versions (md. 4). This is the hardest data task.

## Open questions for partners

- Do we need permission from the journal to show its summaries?
- Should we re-fetch the 6 missing decisions?
- Baran's filter criteria for AYM / İBK / HGK / Danıştay collection: topics, date range, priority.
- Who are the target users?
- What does "offline" mean? No GPU is available, so the LLM goes through an API. KVKK cross-border transfer must be addressed before real personal data is used, since servers are in the EU.

## Infra

- See `~/Desktop/SERVERS.md`.
- Target deployment: `personal-orhanors` (46.225.92.71), managed from https://console.siestai.com. It also hosts the hukuk Hermes agent.
- Keep this project separate from Siestai infra (it is a partnership).

## Conventions

- **User-facing language:** Turkish. **Code and docs:** English or Turkish, kept consistent.
- **Commits:** ask before committing or branching. No secrets in the repo; secrets live under `data/` (gitignored).
