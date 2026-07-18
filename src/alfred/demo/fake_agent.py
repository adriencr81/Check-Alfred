"""Instrumented fake agent — synthesizes an OTLP JSON trace for `alfred demo`.

See PLAN.md §5 Brique 6 and
docs/adr/0008-brique6-demo-launch-polish-design.md for why this dogfoods
`alfred.trace.ingest.ingest_otlp_json` (the same entry point `alfred watch`
uses on a real file) instead of building `TraceEvent` objects by hand.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from alfred.mandate.model import Mandate

_MODEL = "gpt-4o-mini-2024-07-18"
_ALLOWED_TOOL = "send_email"
_FORBIDDEN_TOOL = "read_pii"


def _ns(dt: datetime) -> str:
    return str(int(dt.timestamp() * 1_000_000_000))


def _attr(key: str, value: str | int | float | bool) -> dict[str, object]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": value}}


def _task_spans(
    index: int,
    task: str,
    tool: str,
    start: datetime,
    cost_eur: float,
    *,
    escalated: bool = False,
) -> list[dict[str, object]]:
    trace_id = f"demo-trace-{index}"
    task_span_id = f"demo-{index}-task"
    llm_span_id = f"demo-{index}-llm"
    tool_span_id = f"demo-{index}-tool"

    llm_start = start + timedelta(seconds=1)
    llm_end = llm_start + timedelta(seconds=3)
    tool_start = llm_end + timedelta(seconds=1)
    tool_end = tool_start + timedelta(seconds=1, milliseconds=500)
    task_end = tool_end + timedelta(seconds=1)

    task_attributes = [
        _attr("gen_ai.operation.name", "invoke_agent"),
        _attr("gen_ai.agent.name", "demo-bot"),
        _attr("agent.task", task),
        _attr("agent.task.id", f"task-{index}"),
    ]
    if escalated:
        task_attributes.append(_attr("alfred.escalated", True))

    return [
        {
            "traceId": trace_id,
            "spanId": task_span_id,
            "parentSpanId": "",
            "name": f"agent_task.{task}",
            "kind": 1,
            "startTimeUnixNano": _ns(start),
            "endTimeUnixNano": _ns(task_end),
            "attributes": task_attributes,
        },
        {
            "traceId": trace_id,
            "spanId": llm_span_id,
            "parentSpanId": task_span_id,
            "name": "chat gpt-4o-mini",
            "kind": 3,
            "startTimeUnixNano": _ns(llm_start),
            "endTimeUnixNano": _ns(llm_end),
            "attributes": [
                _attr("gen_ai.system", "openai"),
                _attr("gen_ai.operation.name", "chat"),
                _attr("gen_ai.request.model", "gpt-4o-mini"),
                _attr("gen_ai.response.model", _MODEL),
                _attr("gen_ai.usage.input_tokens", 1400),
                _attr("gen_ai.usage.output_tokens", 260),
                _attr("gen_ai.usage.cost_eur", cost_eur),
            ],
        },
        {
            "traceId": trace_id,
            "spanId": tool_span_id,
            "parentSpanId": task_span_id,
            "name": f"tool_call.{tool}",
            "kind": 3,
            "startTimeUnixNano": _ns(tool_start),
            "endTimeUnixNano": _ns(tool_end),
            "attributes": [
                _attr("gen_ai.operation.name", "execute_tool"),
                _attr("gen_ai.tool.name", tool),
                _attr("tool.result.status", "ok"),
            ],
        },
    ]


def build_demo_payload(
    agent: str = "demo-bot", *, now: datetime | None = None
) -> dict[str, object]:
    """Synthesize an OTLP JSON payload for a 3-task demo day.

    Three independent traces, offset by a few seconds from `now` so every
    event's `start_time.date()` is today by construction:
    1. `onboard_customer` calls the allowed tool `send_email`.
    2. `handle_support_ticket` calls `read_pii`, which is not in the demo
       mandate's `allowed_tools` — the one deliberate `tool_not_allowed`
       deviation (echoes the `read_pii` example already used in
       PLAN.md/README).
    3. `escalate_complex_case` is flagged `alfred.escalated` — populates
       the Escalations line without tripping `escalation_missed`.
    """
    anchor = now or datetime.now(UTC)
    spans = [
        *_task_spans(1, "onboard_customer", _ALLOWED_TOOL, anchor, 0.29),
        *_task_spans(
            2,
            "handle_support_ticket",
            _FORBIDDEN_TOOL,
            anchor + timedelta(seconds=15),
            0.38,
        ),
        *_task_spans(
            3,
            "escalate_complex_case",
            _ALLOWED_TOOL,
            anchor + timedelta(seconds=30),
            0.51,
            escalated=True,
        ),
    ]
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": [_attr("service.name", agent)]},
                "scopeSpans": [{"scope": {"name": "alfred.demo"}, "spans": spans}],
            }
        ]
    }


def demo_mandate(agent: str = "demo-bot") -> Mandate:
    """The mandate the demo trace is evaluated against.

    Only `send_email` is allowed — deliberately narrower than the demo
    trace's tool calls, so the digest always shows the mandate catching
    something (see `build_demo_payload`).
    """
    return Mandate(
        agent=agent,
        allowed_tools=frozenset({_ALLOWED_TOOL}),
        daily_budget_eur=5.00,
        forbidden_actions=(),
        escalate_when=(),
    )
