"""Records what the agent actually did as an OTLP JSON payload.

This is deliberate hand-rolled emission, not the OTel SDK: there is no
stable OTLP-JSON file exporter in opentelemetry-python, and emitting the
exact GenAI semconv keys that `alfred.trace.ingest` reads removes the
"semconv still moving" risk (PLAN.md §9). Span IDs, timestamps, token
counts and tool outcomes are all real — only the serialization is ours.
The payload shape mirrors tests/fixtures/otlp_sample.json.

See docs/adr/0010-brique7-real-agent-example.md, decision 1.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime


def _now() -> datetime:
    return datetime.now(UTC)


def _ns(moment: datetime) -> str:
    return str(int(moment.timestamp() * 1_000_000_000))


def _attr(key: str, value: str | int | float | bool) -> dict[str, object]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": value}}


def _span_id() -> str:
    return os.urandom(8).hex()


class TraceRecorder:
    """One trace per task; chat/tool spans are children of the task span."""

    def __init__(self, agent: str) -> None:
        self._agent = agent
        self._spans: list[dict[str, object]] = []
        self._trace_id = ""
        self._task_span_id = ""
        self._task_name = ""
        self._task_id = ""
        self._task_start: datetime | None = None

    def begin_task(self, *, task_name: str, task_id: str) -> None:
        self._trace_id = os.urandom(16).hex()
        self._task_span_id = _span_id()
        self._task_name = task_name
        self._task_id = task_id
        self._task_start = _now()

    def end_task(self) -> None:
        if self._task_start is None:
            raise RuntimeError("end_task() called without begin_task()")
        self._spans.append(
            {
                "traceId": self._trace_id,
                "spanId": self._task_span_id,
                "parentSpanId": "",
                "name": f"agent_task.{self._task_name}",
                "kind": 1,
                "startTimeUnixNano": _ns(self._task_start),
                "endTimeUnixNano": _ns(_now()),
                "attributes": [
                    _attr("gen_ai.operation.name", "invoke_agent"),
                    _attr("gen_ai.agent.name", self._agent),
                    _attr("agent.task", self._task_name),
                    _attr("agent.task.id", self._task_id),
                ],
            }
        )
        self._task_start = None

    def record_chat(
        self,
        *,
        request_model: str,
        response_model: str,
        input_tokens: int,
        output_tokens: int,
        cost_eur: float,
        start: datetime,
        end: datetime,
    ) -> None:
        self._spans.append(
            {
                "traceId": self._trace_id,
                "spanId": _span_id(),
                "parentSpanId": self._task_span_id,
                "name": f"chat {request_model}",
                "kind": 3,
                "startTimeUnixNano": _ns(start),
                "endTimeUnixNano": _ns(end),
                "attributes": [
                    _attr("gen_ai.system", "anthropic"),
                    _attr("gen_ai.operation.name", "chat"),
                    _attr("gen_ai.request.model", request_model),
                    _attr("gen_ai.response.model", response_model),
                    _attr("gen_ai.usage.input_tokens", input_tokens),
                    _attr("gen_ai.usage.output_tokens", output_tokens),
                    _attr("gen_ai.usage.cost_eur", cost_eur),
                ],
            }
        )

    def record_tool(
        self,
        *,
        tool: str,
        status: str,
        start: datetime,
        end: datetime,
        amount_eur: float | None = None,
    ) -> None:
        attributes = [
            _attr("gen_ai.operation.name", "execute_tool"),
            _attr("gen_ai.tool.name", tool),
            _attr("tool.result.status", status),
        ]
        if amount_eur is not None:
            attributes.append(_attr("tool.arguments.amount_eur", float(amount_eur)))
        self._spans.append(
            {
                "traceId": self._trace_id,
                "spanId": _span_id(),
                "parentSpanId": self._task_span_id,
                "name": f"tool_call.{tool}",
                "kind": 3,
                "startTimeUnixNano": _ns(start),
                "endTimeUnixNano": _ns(end),
                "attributes": attributes,
            }
        )

    def payload(self) -> dict[str, object]:
        return {
            "resourceSpans": [
                {
                    "resource": {"attributes": [_attr("service.name", self._agent)]},
                    "scopeSpans": [
                        {"scope": {"name": "refund_bot.tracer"}, "spans": list(self._spans)}
                    ],
                }
            ]
        }
