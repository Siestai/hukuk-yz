"""The golden point-in-time queries (`tests/fixtures/statutes/golden.toml`): loading and checking,
shared by the ingest test (timeline in memory) and the app test (database and HTTP API)."""

import tomllib
from pathlib import Path
from typing import Any


def load_golden(path: Path) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = tomllib.loads(path.read_text(encoding="utf-8"))["query"]
    return queries


def _flat(text: str) -> str:
    return " ".join(text.split())


def check_golden(query: dict[str, Any], result: dict[str, Any]) -> str | None:
    """None when `result` (an `as_of` result or its API form) satisfies the query, else the
    failure. `found` is checked for `contains`; `not_contains` for any text; a `gap` has none."""
    label = f"{query['statute']} m.{query['article']} @ {query['as_of']}"
    if result["status"] != query["expect"]:
        return f"{label}: expected {query['expect']}, got {result['status']}"
    text = _flat(result.get("version", {}).get("text", ""))
    if query["expect"] == "found" and "contains" in query and _flat(query["contains"]) not in text:
        return f"{label}: missing {query['contains']!r}"
    if "not_contains" in query and _flat(query["not_contains"]) in text:
        return f"{label}: unexpected {query['not_contains']!r}"
    if query["expect"] == "gap" and "version" in result:
        return f"{label}: a gap carries text"
    return None
