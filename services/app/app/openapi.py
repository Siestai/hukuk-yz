"""Print the OpenAPI schema as stable JSON: `python -m app.openapi`."""

import json

from app.main import app


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    print(render(), end="")
