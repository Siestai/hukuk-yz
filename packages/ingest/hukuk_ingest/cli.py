"""`hukuk-ingest scan <dir> --out <report_dir>`."""

import argparse
import json
import multiprocessing
import os
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from functools import partial
from pathlib import Path
from typing import Any

from hukuk_ingest.pipeline import FileResult, error_result, process_file
from hukuk_ingest.report import build_summary, dump_json, render_markdown

Work = Callable[[Path], FileResult]

_MAX_TASKS_PER_CHILD = 200  # recycle workers: pdfium memory is not returned between files


def _run_isolated(path: Path, work: Work, root: Path) -> FileResult:
    """Retry one suspect file alone, so a hard crash is pinned on the file that causes it."""
    pool = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))
    try:
        return pool.submit(work, path).result()
    except BrokenProcessPool:
        return error_result(path, root, "worker_crash", "worker process died (pdfium crash/OOM?)")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _run_parallel(
    files: list[Path], work: Work, root: Path, workers: int, on_done: Callable[[], None]
) -> list[FileResult]:
    """Per-file submit with a bounded window; survives workers that die without an exception."""
    results: list[FileResult] = []
    todo = iter(files)
    window = workers * 2

    def new_pool() -> ProcessPoolExecutor:
        return ProcessPoolExecutor(
            max_workers=workers,
            mp_context=multiprocessing.get_context("spawn"),
            max_tasks_per_child=_MAX_TASKS_PER_CHILD,
        )

    pool = new_pool()
    pending: dict[Future[FileResult], Path] = {}
    try:
        while True:
            while len(pending) < window and (path := next(todo, None)) is not None:
                pending[pool.submit(work, path)] = path
            if not pending:
                break
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            suspects: list[Path] = []
            for future in done:
                path = pending.pop(future)
                try:
                    results.append(future.result())
                except BrokenProcessPool:
                    suspects.append(path)
                on_done()
            if suspects:
                # The pool is dead and every in-flight future with it: rebuild, then re-run
                # each affected file alone to find the culprit.
                suspects += pending.values()
                pending.clear()
                pool.shutdown(wait=False, cancel_futures=True)
                results += [_run_isolated(p, work, root) for p in suspects]
                pool = new_pool()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return results


def scan(
    root: Path, out: Path, text_cache: Path, workers: int, force: bool
) -> tuple[list[FileResult], dict[str, Any]]:
    start = time.perf_counter()
    cache = text_cache.resolve()
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and not p.resolve().is_relative_to(cache)
    )
    work = partial(process_file, root=root, cache_dir=text_cache, force=force)
    results: list[FileResult] = []
    done = 0

    def on_done() -> None:
        nonlocal done
        done += 1
        if done % 500 == 0:
            print(f"{done}/{len(files)}", file=sys.stderr)

    try:
        if workers > 1:
            results = _run_parallel(files, work, root, workers, on_done)
        else:
            for path in files:
                results.append(work(path))
                on_done()
    finally:  # a partial report beats none when the run is interrupted
        results.sort(key=lambda r: r.path)
        summary = build_summary(results, time.perf_counter() - start)
        out.mkdir(parents=True, exist_ok=True)
        with (out / "files.jsonl").open("w", encoding="utf-8") as fh:
            for r in results:
                fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
        (out / "summary.json").write_text(dump_json(summary), encoding="utf-8")
        (out / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    return results, summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hukuk-ingest")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("scan", help="detect types and extract text for every file under a dir")
    p.add_argument("dir", type=Path)
    p.add_argument("--out", type=Path, required=True, help="report directory")
    p.add_argument("--text-cache", type=Path, default=Path("data/extracted"))
    p.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    p.add_argument("--force", action="store_true", help="ignore cached extractions")
    args = parser.parse_args(argv)
    if not args.dir.is_dir():
        parser.error(f"not a directory: {args.dir}")
    if args.workers < 1:
        parser.error("--workers must be >= 1")

    _, summary = scan(args.dir, args.out, args.text_cache, args.workers, args.force)
    print(
        f"{summary['files']} files in {summary['total_seconds']} s, "
        f"{summary['cache_hits']} cache hits, {len(summary['errors'])} errors",
    )
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
