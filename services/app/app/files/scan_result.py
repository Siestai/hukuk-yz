"""What a (re)scan keeps of `ingest_file.scan_result` (task 12c)."""

from typing import Any

IMPORT_PATH = "import_path"


def carry_import_path(previous: dict[str, Any] | None) -> dict[str, Any]:
    """The part of the previous scan result that outlives a scan: the relative path the file had
    in the imported archive (written by `app.files.import_dir`)."""
    if previous and IMPORT_PATH in previous:
        return {IMPORT_PATH: previous[IMPORT_PATH]}
    return {}
