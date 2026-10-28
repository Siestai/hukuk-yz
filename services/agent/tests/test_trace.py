"""The trace of a run: records per node, a trace id, Langfuse only when configured."""

import logging

import pytest
from pydantic import SecretStr

from agent.settings import LlmSettings
from agent.trace import Tracing, current_trace


async def test_a_node_leaves_a_record_and_a_log_line(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="agent.trace")
    with Tracing().run("thread-1") as trace:
        async with current_trace().node("plan", {"topic": "ise_iade"}) as record:
            record.output = {"as_of": "2026-10-03"}
            record.add_usage("m", 10, 5, 0.25)
            record.add_usage("m", 1, 1, None)

    assert len(trace.trace_id) == 32
    assert [r.node for r in trace.records] == ["plan"]
    assert (trace.input_tokens, trace.output_tokens, trace.cost) == (11, 6, 0.25)
    assert trace.seconds >= 0
    fields = caplog.records[0].fields  # type: ignore[attr-defined]
    assert fields["trace_id"] == trace.trace_id
    assert fields["node"] == "plan"
    assert fields["output"] == {"as_of": "2026-10-03"}


def test_without_the_langfuse_variables_there_is_only_the_log() -> None:
    tracing = Tracing.from_settings(LlmSettings())

    with tracing.run("t") as trace:
        pass

    assert len(trace.trace_id) == 32
    assert tracing._provider is None


def test_with_the_langfuse_variables_the_run_has_an_opentelemetry_trace_id() -> None:
    settings = LlmSettings(
        langfuse_host="http://langfuse.invalid",
        langfuse_public_key="pk",
        langfuse_secret_key=SecretStr("sk"),
    )
    tracing = Tracing.from_settings(settings)

    with tracing.run("t") as trace:
        pass

    assert tracing._provider is not None
    assert len(trace.trace_id) == 32 and trace.trace_id != "0" * 32
    tracing._provider.shutdown()
