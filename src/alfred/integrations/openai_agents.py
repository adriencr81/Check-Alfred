"""Native OpenAI Agents SDK connector: register one processor, get an Alfred trace.

`AlfredTracingProcessor` is an OpenAI Agents SDK `TracingProcessor`. Register it
once and every `Runner.run(...)` becomes a trace in the exact OTLP JSON shape
`alfred.trace.ingest` reads — no manual instrumentation.

    from agents import Agent, Runner, set_trace_processors
    from alfred.instrument import AgentTracer
    from alfred.integrations.openai_agents import AlfredTracingProcessor

    tracer = AgentTracer(agent="support-bot", traces_dir="traces")
    set_trace_processors([AlfredTracingProcessor(tracer)])  # Alfred only, offline
    Runner.run_sync(agent, "handle the ticket")
    tracer.flush()  # → traces/support-bot-<ts>.json  → alfred watch

Use `add_trace_processor(AlfredTracingProcessor(tracer))` instead to keep the
SDK's own OpenAI trace export alongside Alfred's.

The design decision that makes this safe (docs/adr/0021): the SDK's tracing is
event-driven (`on_trace_start`/`on_trace_end`, `on_span_start`/`on_span_end`)
while `AgentTracer` exposes context managers. The processor bridges the two by
driving the proven `AgentTracer` context managers manually. It never re-emits
attribute keys itself, so the "every fact anchored to a real trace event"
guarantee (CLAUDE.md rule D5) is inherited, not re-implemented.

Requires the optional extra: ``pip install alfred-ai[openai-agents]``.
"""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from typing import Any

from agents.tracing import Span, Trace, TracingProcessor
from agents.tracing.span_data import (
    FunctionSpanData,
    GenerationSpanData,
    ResponseSpanData,
)

from alfred.instrument import AgentTracer


class AlfredTracingProcessor(TracingProcessor):
    """Records an OpenAI Agents SDK run as an Alfred OTLP trace.

    One session spans the root `Runner.run` trace (`invoke_agent`); model calls
    (`chat`) and tool calls (`execute_tool`) are its children. Successive runs
    accumulate in the tracer's payload, exactly like manual `AgentTracer`
    sessions.

    Model call spans and function (tool) spans are the only ones mapped; agent,
    turn and task spans are ignored — they carry no new measured fact for the
    mandate, and turn spans repeat token usage the model span already reports,
    so mapping them would double-count tokens (docs/adr/0021, decision 4).

    In production the processor never raises into the run. Pass
    ``raise_errors=True`` in tests so a mapping bug fails loudly instead of
    silently dropping spans.
    """

    def __init__(self, tracer: AgentTracer, *, raise_errors: bool = False) -> None:
        self._tracer = tracer
        self._raise_errors = raise_errors
        self._session_trace_id: str | None = None
        self._session_cm: AbstractContextManager[None] | None = None

    # -- Session: bounded by the root run trace --------------------------------

    def on_trace_start(self, trace: Trace) -> None:
        if self._session_trace_id is None:
            cm = self._tracer.session(task_name=trace.name or "workflow", task_id=trace.trace_id)
            cm.__enter__()
            self._session_cm = cm
            self._session_trace_id = trace.trace_id

    def on_trace_end(self, trace: Trace) -> None:
        if trace.trace_id == self._session_trace_id and self._session_cm is not None:
            self._session_cm.__exit__(None, None, None)
            self._session_cm = None
            self._session_trace_id = None

    # -- Spans: recorded at end, when usage/args/error are populated -----------

    def on_span_start(self, span: Span[Any]) -> None:
        return None

    def on_span_end(self, span: Span[Any]) -> None:
        try:
            self._record_span(span)
        except Exception:
            if self._raise_errors:
                raise

    def _record_span(self, span: Span[Any]) -> None:
        if self._session_trace_id is None:
            return
        data = span.span_data
        if isinstance(data, GenerationSpanData | ResponseSpanData):
            self._record_llm(data)
        elif isinstance(data, FunctionSpanData):
            self._record_tool(data, span)

    def _record_llm(self, data: GenerationSpanData | ResponseSpanData) -> None:
        model = _model_name(data)
        cm = self._tracer.llm_call(model=model)
        handle = cm.__enter__()
        usage = _usage(data)
        if usage is not None:
            handle.record_usage(
                input_tokens=usage[0],
                output_tokens=usage[1],
                response_model=model,
            )
        cm.__exit__(None, None, None)

    def _record_tool(self, data: FunctionSpanData, span: Span[Any]) -> None:
        cm = self._tracer.tool_call(data.name or "tool", _arguments(data.input))
        handle = cm.__enter__()
        handle.record_result(status="error" if span.error else "ok")
        cm.__exit__(None, None, None)

    # -- TracingProcessor lifecycle hooks (nothing to flush) -------------------

    def shutdown(self) -> None:
        return None

    def force_flush(self) -> None:
        return None


def _model_name(data: GenerationSpanData | ResponseSpanData) -> str | None:
    """The model id the span reports, from either the chat or responses path."""
    model = getattr(data, "model", None)
    if isinstance(model, str) and model:
        return model
    response = getattr(data, "response", None)
    response_model = getattr(response, "model", None)
    if isinstance(response_model, str) and response_model:
        return response_model
    return None


def _usage(data: GenerationSpanData | ResponseSpanData) -> tuple[int, int] | None:
    """(input_tokens, output_tokens) the span reports, or None if absent.

    Both the Chat Completions (`GenerationSpanData`) and Responses API
    (`ResponseSpanData`) paths serialize usage into a dict with the same
    `input_tokens`/`output_tokens` keys; the responses path also carries it on
    the `Response` object, used as a fallback.
    """
    usage = getattr(data, "usage", None)
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
            return input_tokens, output_tokens
    response_usage = getattr(getattr(data, "response", None), "usage", None)
    if response_usage is not None:
        input_tokens = getattr(response_usage, "input_tokens", None)
        output_tokens = getattr(response_usage, "output_tokens", None)
        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
            return input_tokens, output_tokens
    return None


def _arguments(raw: Any) -> dict[str, object] | None:
    """The tool's arguments as a dict; the SDK carries them as a JSON string."""
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return raw if isinstance(raw, dict) else None
