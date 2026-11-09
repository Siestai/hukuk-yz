"""Offline HTTP integration server: real graph/PG/HTTP KB, scripted model only.

Run from the repo root with PYTHONPATH=services/agent/tests and TEST_STATUTE_VERSION_ID
pointing at the synthetic test article's version UUID. This is not a legal quality demo.
"""

import json
import os
from typing import cast

from agent_fakes import M18_1, Script, scripted

from agent.api import create_app
from agent.llm import Models
from agent.settings import get_settings

script = Script()
version = os.environ["TEST_STATUTE_VERSION_ID"]


def replace[T](value: T) -> T:
    wire = json.dumps(value, ensure_ascii=False)
    wire = wire.replace(json.dumps("statute:4857:m18"), json.dumps(version))
    wire = wire.replace(
        json.dumps(M18_1, ensure_ascii=False),
        json.dumps(os.environ["TEST_STATUTE_QUOTE"], ensure_ascii=False),
    )
    return cast(T, json.loads(wire))


script.holding = replace(script.holding)
script.drafts = replace(script.drafts)
model = scripted(script)
app = create_app(get_settings(), models=Models(model, model))
