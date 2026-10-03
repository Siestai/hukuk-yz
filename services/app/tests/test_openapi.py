import json

from app.openapi import render


def test_render_is_stable_sorted_json() -> None:
    first = render()
    assert first == render()
    schema = json.loads(first)
    assert schema["info"]["title"] == "hukuk-agent"
    assert first.endswith("}\n")
    assert list(schema) == sorted(schema)
