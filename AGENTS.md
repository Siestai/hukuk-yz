# hukuk-agent

An AI legal research and reasoning assistant for Turkish labour and social security law. It covers iş hukuku, SGK, sendika/TİS and İSG. Partners: Orhan (software), Baran and İbrahim (legal; approvers at institutions). Status 2026-10-02: data exploration done; monorepo scaffold (app, worker, compose, CI) merged; KB schema (task 02) in progress. Repo: `Siestai/hukuk-yz` (public).

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
    - E-signed SGK genelge PDFs extract cleanly with `pypdfium2` (they were scrambled only under `pdftotext`). The real gap is scans: 25 Mevzuat PDFs have no text layer, ~5 have a broken OCR layer, plus 16 images (task 03 spike, 2026-10-02).
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
- ~~Who are the target users?~~ Answered 2026-10-01: accountants (mali müşavir) first, then HR specialists, lawyers, corporate HR, inspectors. See `docs/decisions.md`.
- What does "offline" mean? No GPU is available, so the LLM goes through an API. KVKK cross-border transfer must be addressed before real personal data is used, since servers are in the EU.

## Decision log and design docs

- **`docs/decisions.md` is the project decision log.** Every decision taken with the partners (WhatsApp group, meetings) or by Orhan lands there with a date and owner. Read it before proposing anything; update it in the same PR as the change it motivates.
- Design: `docs/architecture.md`, `docs/data-model.md`, `docs/roadmap.md`. Market research: `docs/market-research-2026-10-02.md`.
- **Verification rule (İbrahim, 2026-10-02):** the journal archive is a search aid only. Any Yargıtay decision shown to a user must be verified against https://karararama.yargitay.gov.tr/ by esas/karar number, and that site is the cited source. Unverified decisions are flagged, never silently passed. In code: `decision.verification`.

## Infra

- Server details live outside the repo in `~/Desktop/SERVERS.md` (Orhan's machine). Never put IPs of new hosts, phone numbers, tokens or allowlists here: the repo is public.
- Target deployment (changed 2026-10-05, see `docs/decisions.md`): the Dokploy host itself (https://console.siestai.com), next to the Siestai apps, as its own Dokploy project `hukuk-yz` with its own Postgres. It shares CPU, RAM and disk with them, nothing else. Dashboard: `dash-hukuk.siestai.com` behind Cloudflare (`docs/deploy.md`). `personal-orhanors` (also a Dokploy server) runs only Themis.
- **Themis (Hermes Agent, Nous Research)** runs on the same server:
  - Plain `docker compose` in `/opt/hermes-hukuk`, container `hermes-hukuk`, `gateway run`. No published ports, no Docker socket, `no-new-privileges`, 1.5 GB RAM / 1.5 CPU limit.
  - State in `/opt/hermes-hukuk/data` → `/opt/data` in the container.
  - Project data: Drive copy at `/opt/data/projects/hukuk-yz/data/raw/` (6,626 files, sha256-verified; `MANIFEST.txt` lists path, bytes, sha256).
  - Channels: Telegram (Orhan) and the partners' WhatsApp group, both behind allowlists.
  - Models: main `claude-opus-5-5`; subagents `claude-sonnet-5-5` (`delegation.model`); context compression at 80k tokens.
  - `.env` and `config.yaml` are mounted **read-only**: Themis cannot change its own access, model or token settings. Changes go through Orhan / Claude Code on the host, followed by `docker compose up -d --force-recreate`.

## OCR and legacy `.doc` (task 07)

- `hukuk-ingest scan` OCRs `needs_ocr` files (scans, photos, bad or partial text layers) with a local **Tesseract** binary run via `subprocess` (`packages/ingest/hukuk_ingest/ocr.py`); nothing is sent to an API. `--no-ocr` turns it off; without Tesseract the files stay `needs_ocr` with an `ocr_unavailable` warning. Weak pages get a second pass that tries both adaptive thresholdings (`thresholding_method` 1 Otsu and 2 Sauvola) and keeps the better; a third pass rotates by OSD. The page images are rotated only for PDFs (there is no imaging library for photos).
- Old Word 97-2003 `.doc` files (also those named `.pdf`) are read in pure Python with `olefile` (`legacy_doc.py`).
- **Server install (no root):** a conda-forge/micromamba env with `tesseract` (`micromamba create -n ocr -c conda-forge tesseract`); its `share/tessdata` must hold `tur.traineddata` and `osd.traineddata`. Set `HUKUK_TESSERACT` to the env's `bin/tesseract` and `TESSDATA_PREFIX` to its `share/tessdata`; the default is `tesseract` on `PATH`.
- **CI** installs `tesseract-ocr` and `tesseract-ocr-tur` via apt, so the OCR integration tests run there; locally they skip when Tesseract is missing.
- The Docker image (`services/app/Dockerfile`) does **not** get Tesseract in this task, to keep it small. Add it when ingest moves to the worker.

## Conventions

- **User-facing language:** Turkish. **Code and docs:** English or Turkish, kept consistent.
- **Commits:** an approved task includes its branch and PR; merge is always Orhan's. Commit and PR titles in English, docs in Turkish. No secrets in the repo; secrets live under `data/` (gitignored).
- **Project skills** (`.claude/skills/`), loaded when the work matches:
  - `task-pr-hygiene`: task spec format, scope, test file layout, commits and PRs.
  - `db-migration`: Alembic, enums, bitemporal tables, ORM consistency tests.
  - `frontend-ui`: no DB in the UI (API only, generated types), design tokens, i18n (Turkish first).
  - `connect-vps`: SSH to the server (Orhan's machine only).
