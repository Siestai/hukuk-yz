"""The trace of a run: per node the input summary, the output, the model, tokens, time and cost.

Always written to the structured log. With the `LANGFUSE_*` variables set, the model calls and one
span per run also go to Langfuse over OpenTelemetry. The harness (not a model) writes it.
"""

import base64
import logging
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic_ai import Agent
from pydantic_ai.models.instrumented import InstrumentationSettings

from agent.settings import LlmSettings

logger = logging.getLogger("agent.trace")


@dataclass
class NodeRecord:
    node: str
    input: dict[str, Any]
    output: dict[str, Any] = field(default_factory=dict)
    models: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float | None = None
    seconds: float = 0.0

    def add_usage(
        self, model: str, input_tokens: int, output_tokens: int, cost: float | None
    ) -> None:
        if model not in self.models:
            self.models.append(model)
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        if cost is not None:
            self.cost = (self.cost or 0.0) + cost


@dataclass
class Trace:
    trace_id: str
    records: list[NodeRecord] = field(default_factory=list)

    @property
    def input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.records)

    @property
    def output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.records)

    @property
    def cost(self) -> float | None:
        costs = [r.cost for r in self.records if r.cost is not None]
        return sum(costs) if costs else None

    @property
    def seconds(self) -> float:
        return sum(r.seconds for r in self.records)

    @asynccontextmanager
    async def node(self, name: str, input_summary: dict[str, Any]) -> AsyncIterator[NodeRecord]:
        record = NodeRecord(node=name, input=input_summary)
        token = _record.set(record)
        started = perf_counter()
        try:
            yield record
        finally:
            record.seconds = perf_counter() - started
            _record.reset(token)
            self.records.append(record)
            logger.info(
                "node %s",
                name,
                extra={"fields": {"trace_id": self.trace_id, **vars(record)}},
            )


_trace: ContextVar[Trace | None] = ContextVar("trace", default=None)
_record: ContextVar[NodeRecord | None] = ContextVar("record", default=None)


def current_trace() -> Trace:
    """The trace of the run in progress; a graph invoked outside `Tracing.run` gets its own."""
    trace = _trace.get()
    if trace is None:
        trace = Trace(uuid.uuid4().hex)
        _trace.set(trace)
    return trace


def current_record() -> NodeRecord | None:
    return _record.get()


class Tracing:
    """Langfuse over OpenTelemetry when configured, a plain id otherwise."""

    def __init__(self, provider: TracerProvider | None = None) -> None:
        self._provider = provider
        if provider is not None:
            Agent.instrument_all(InstrumentationSettings(tracer_provider=provider))

    @classmethod
    def from_settings(cls, settings: LlmSettings) -> "Tracing":
        host, public, secret = (
            settings.langfuse_host,
            settings.langfuse_public_key,
            settings.langfuse_secret_key,
        )
        if not (host and public and secret):
            return cls()
        token = base64.b64encode(f"{public}:{secret.get_secret_value()}".encode()).decode()
        exporter = OTLPSpanExporter(
            endpoint=f"{host.rstrip('/')}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {token}"},
        )
        provider = TracerProvider(resource=Resource.create({"service.name": "hukuk-agent"}))
        provider.add_span_processor(BatchSpanProcessor(exporter))
        return cls(provider)

    @contextmanager
    def run(self, thread_id: str) -> Iterator[Trace]:
        """One run of the graph: its trace is current inside, its id goes out with the answer."""
        # The variable is set, not reset: the stream of a response may be closed from another
        # context than the one it was opened in, and a reset would fail there.
        if self._provider is None:
            trace = Trace(uuid.uuid4().hex)
            _trace.set(trace)
            yield trace
            return
        tracer = self._provider.get_tracer("agent")
        with tracer.start_as_current_span("run", attributes={"thread_id": thread_id}) as span:
            trace = Trace(format(span.get_span_context().trace_id, "032x"))
            _trace.set(trace)
            yield trace

    def shutdown(self) -> None:
        if self._provider is not None:
            self._provider.shutdown()
