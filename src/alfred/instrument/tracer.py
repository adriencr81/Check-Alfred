"""Public instrumentation SDK: an agent loop → an OTLP JSON trace file.

This is deliberate hand-rolled emission, not the OTel SDK: there is no
stable OTLP-JSON file exporter in opentelemetry-python, and emitting the
exact GenAI semconv keys that `alfred.trace.ingest` reads (and that the
mandate engine and report builder consume) removes the "semconv still
moving" risk (PLAN.md §9). Span IDs, timestamps, token counts and tool
outcomes are all real — only the serialization is ours. Promoted from the
proven refund-bot example tracer per docs/adr/0013, decision 2.

Quickstart in docs/integrate.md; falsifiable contract in
tests/test_instrument.py (PLAN.md §12 Brique 8).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

_Scalar = str | int | float | bool


def _now() -> datetime:
    return datetime.now(UTC)


def _ns(moment: datetime) -> str:
    return str(int(moment.timestamp() * 1_000_000_000))


def _attr(key: str, value: _Scalar) -> dict[str, object]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": value}}


def _span_id() -> str:
    return os.urandom(8).hex()


class LLMCall:
    """Handle yielded by `AgentTracer.llm_call`; usage lands on the span at exit."""

    def __init__(self, request_model: str | None) -> None:
        self._request_model = request_model
        self._response_model: str | None = None
        self._input_tokens: int | None = None
        self._output_tokens: int | None = None
        self._cost_eur: float | None = None

    def record_usage(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        response_model: str | None = None,
        cost_eur: float | None = None,
    ) -> None:
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._response_model = response_model
        self._cost_eur = cost_eur

    def _name(self) -> str:
        model = self._response_model or self._request_model
        return f"chat {model}" if model else "chat"

    def _attributes(self) -> list[dict[str, object]]:
        # Whichever side named the model, emit both keys: the report builder
        # prices from gen_ai.response.model, generic OTel consumers expect
        # gen_ai.request.model.
        request_model = self._request_model or self._response_model
        response_model = self._response_model or self._request_model
        attributes = [_attr("gen_ai.operation.name", "chat")]
        if request_model is not None:
            attributes.append(_attr("gen_ai.request.model", request_model))
        if response_model is not None:
            attributes.append(_attr("gen_ai.response.model", response_model))
        if self._input_tokens is not None:
            attributes.append(_attr("gen_ai.usage.input_tokens", self._input_tokens))
        if self._output_tokens is not None:
            attributes.append(_attr("gen_ai.usage.output_tokens", self._output_tokens))
        if self._cost_eur is not None:
            attributes.append(_attr("gen_ai.usage.cost_eur", float(self._cost_eur)))
        return attributes


class ToolCall:
    """Handle yielded by `AgentTracer.tool_call`; outcome lands on the span at exit."""

    def __init__(self, tool: str, arguments: dict[str, object] | None) -> None:
        self._tool = tool
        self._arguments = dict(arguments) if arguments else {}
        self._status: str | None = None

    def record_result(self, *, status: str) -> None:
        self._status = status

    def _attributes(self) -> list[dict[str, object]]:
        attributes = [
            _attr("gen_ai.operation.name", "execute_tool"),
            _attr("gen_ai.tool.name", self._tool),
        ]
        for key, value in self._arguments.items():
            if isinstance(value, _Scalar):
                attributes.append(_attr(f"tool.arguments.{key}", value))
            else:
                attributes.append(_attr(f"tool.arguments.{key}", json.dumps(value, default=str)))
        attributes.append(_attr("tool.result.status", self._status or "ok"))
        return attributes


class AgentTracer:
    """Records what an agent actually did, in the OTLP JSON shape Alfred ingests.

    One `session()` per task opens a fresh trace; `llm_call()` and
    `tool_call()` spans are children of the session span. Successive
    sessions accumulate in the same payload; `flush()` writes it to
    `traces_dir/<agent>-<timestamp>.json` for `alfred watch`.
    """

    def __init__(self, agent: str, traces_dir: str | Path = "traces") -> None:
        self._agent = agent
        self._traces_dir = Path(traces_dir)
        self._spans: list[dict[str, object]] = []
        self._trace_id = ""
        self._session_span_id = ""

    @contextmanager
    def session(self, *, task_name: str = "session", task_id: str | None = None) -> Iterator[None]:
        """One agent task (`invoke_agent` span); everything inside is its child."""
        if self._session_span_id:
            raise RuntimeError("session() cannot be nested")
        self._trace_id = os.urandom(16).hex()
        self._session_span_id = _span_id()
        start = _now()
        attributes = [
            _attr("gen_ai.operation.name", "invoke_agent"),
            _attr("gen_ai.agent.name", self._agent),
            _attr("agent.task", task_name),
        ]
        if task_id is not None:
            attributes.append(_attr("agent.task.id", task_id))
        try:
            yield
        finally:
            # Emitted even on exception, so a crashed task still leaves a trace.
            self._append(
                span_id=self._session_span_id,
                parent_span_id="",
                name=f"agent_task.{task_name}",
                kind=1,
                start=start,
                attributes=attributes,
            )
            self._session_span_id = ""

    @contextmanager
    def llm_call(self, *, model: str | None = None) -> Iterator[LLMCall]:
        """One model call (`chat` span). `model` may instead arrive with
        `record_usage(response_model=...)` when only the response names it."""
        self._require_session()
        call = LLMCall(model)
        start = _now()
        try:
            yield call
        finally:
            self._append(
                span_id=_span_id(),
                parent_span_id=self._session_span_id,
                name=call._name(),
                kind=3,
                start=start,
                attributes=call._attributes(),
            )

    @contextmanager
    def tool_call(
        self, tool: str, arguments: dict[str, object] | None = None
    ) -> Iterator[ToolCall]:
        """One tool execution (`execute_tool` span). Scalar arguments are
        flattened to `tool.arguments.<key>`. A clean exit without
        `record_result` records status "ok"; an exception records "error"
        (unless a status was already recorded) and propagates."""
        self._require_session()
        call = ToolCall(tool, arguments)
        start = _now()
        try:
            yield call
        except BaseException:
            call._status = call._status or "error"
            raise
        finally:
            self._append(
                span_id=_span_id(),
                parent_span_id=self._session_span_id,
                name=f"tool_call.{tool}",
                kind=3,
                start=start,
                attributes=call._attributes(),
            )

    def payload(self) -> dict[str, object]:
        """The accumulated trace as an OTLP JSON payload (all sessions so far)."""
        return {
            "resourceSpans": [
                {
                    "resource": {"attributes": [_attr("service.name", self._agent)]},
                    "scopeSpans": [
                        {"scope": {"name": "alfred.instrument"}, "spans": list(self._spans)}
                    ],
                }
            ]
        }

    def flush(self) -> Path:
        """Write the payload to `traces_dir/<agent>-<timestamp>-<token>.json`.

        The timestamp is second-resolution (human-sortable); a short random
        token keeps two flushes within the same second from overwriting each
        other — otherwise the second write would silently clobber the first and
        `alfred watch` would never see that trace.
        """
        self._traces_dir.mkdir(parents=True, exist_ok=True)
        stamp = _now().strftime("%Y%m%d-%H%M%S")
        token = os.urandom(2).hex()
        path = self._traces_dir / f"{self._agent}-{stamp}-{token}.json"
        path.write_text(json.dumps(self.payload(), indent=2), encoding="utf-8")
        return path

    def _require_session(self) -> None:
        if not self._session_span_id:
            raise RuntimeError("llm_call()/tool_call() require an active session()")

    def _append(
        self,
        *,
        span_id: str,
        parent_span_id: str,
        name: str,
        kind: int,
        start: datetime,
        attributes: list[dict[str, object]],
    ) -> None:
        self._spans.append(
            {
                "traceId": self._trace_id,
                "spanId": span_id,
                "parentSpanId": parent_span_id,
                "name": name,
                "kind": kind,
                "startTimeUnixNano": _ns(start),
                "endTimeUnixNano": _ns(_now()),
                "attributes": attributes,
            }
        )
