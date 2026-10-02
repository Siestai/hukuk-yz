"""`hukuk-ingest decisions parse`: parse every cached decision text into decisions.jsonl."""

import json
import multiprocessing
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

from hukuk_ingest.decisions.parse import ARCHIVE_DIR, DecisionRecord, issue_of, parse_row
from hukuk_ingest.decisions.report import (
    build_summary,
    dump_json,
    flag_date_outliers,
    render_markdown,
)

_CHUNK = 50
_PROGRESS_EVERY = 1000


def select_rows(scan_report: Path, issue: int | None) -> list[dict[str, Any]]:
    """Archive decisions whose text was extracted (task 03 `status=ok`), optionally one issue."""
    rows = []
    with scan_report.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            if row["status"] != "ok" or not str(row["path"]).startswith(f"{ARCHIVE_DIR}/"):
                continue
            if issue is None or issue_of(row["path"]) == issue:
                rows.append(row)
    return rows


def run(
    scan_report: Path, text_cache: Path, out: Path, workers: int, issue: int | None
) -> tuple[list[DecisionRecord], dict[str, Any]]:
    start = time.perf_counter()
    rows = select_rows(scan_report, issue)
    work = partial(parse_row, text_cache=text_cache)
    records: list[DecisionRecord] = []
    if workers > 1:
        ctx = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            for i, record in enumerate(pool.map(work, rows, chunksize=_CHUNK), 1):
                records.append(record)
                if i % _PROGRESS_EVERY == 0:
                    print(f"{i}/{len(rows)}", file=sys.stderr)
    else:
        records = [work(row) for row in rows]
    records.sort(key=lambda r: r.source_path)
    flag_date_outliers(records)
    summary = build_summary(records, time.perf_counter() - start)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "decisions.jsonl").open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    (out / "summary.json").write_text(dump_json(summary), encoding="utf-8")
    (out / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    return records, summary
