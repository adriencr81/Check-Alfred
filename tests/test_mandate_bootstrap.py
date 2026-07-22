"""Bootstrap a mandate from observed traces — `alfred mandate init --from-traces`.

See docs/adr/0018-mandate-bootstrap-and-lint.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

from alfred.mandate.bootstrap import suggest_mandate
from alfred.trace.model import EventId, SpanKind, TraceEvent


def _event(
    event_id: str,
    *,
    kind: SpanKind = SpanKind.TOOL_CALL,
    day: int = 30,
    attributes: dict[str, object] | None = None,
) -> TraceEvent:
    return TraceEvent(
        event_id=EventId(event_id),
        trace_id="trace-1",
        parent_span_id=None,
        kind=kind,
        name="span",
        start_time=datetime(2026, 8, day, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, day, 12, 0, 1, tzinfo=UTC),
        attributes=attributes or {},
    )


def test_suggest_mandate_collects_observed_tools() -> None:
    events = [
        _event("e1", attributes={"gen_ai.tool.name": "read_order"}),
        _event("e2", attributes={"gen_ai.tool.name": "issue_refund"}),
        _event("e3", attributes={"gen_ai.tool.name": "read_order"}),  # duplicate collapses
        _event("e4", kind=SpanKind.LLM_CALL, attributes={"gen_ai.usage.cost_eur": 1.0}),
    ]
    assert suggest_mandate(events).allowed_tools == frozenset({"read_order", "issue_refund"})


def test_suggest_mandate_budget_is_ceil_of_peak_day() -> None:
    events = [
        _event("e1", kind=SpanKind.LLM_CALL, day=1, attributes={"gen_ai.usage.cost_eur": 1.20}),
        _event("e2", kind=SpanKind.LLM_CALL, day=1, attributes={"gen_ai.usage.cost_eur": 2.10}),
        _event("e3", kind=SpanKind.LLM_CALL, day=2, attributes={"gen_ai.usage.cost_eur": 0.50}),
    ]
    # Peak day is day 1 at 3.30€ → ceil to 4.0; day 2 (0.50€) is not the peak.
    assert suggest_mandate(events).daily_budget_eur == 4.0


def test_suggest_mandate_agent_from_trace_then_argument_override() -> None:
    events = [_event("e1", kind=SpanKind.AGENT_TASK, attributes={"gen_ai.agent.name": "obs-bot"})]
    assert suggest_mandate(events).agent == "obs-bot"
    assert suggest_mandate(events, agent="cli-bot").agent == "cli-bot"


def test_suggest_mandate_without_cost_falls_back_to_default_budget() -> None:
    events = [_event("e1", attributes={"gen_ai.tool.name": "read_order"})]
    assert suggest_mandate(events).daily_budget_eur == 5.00


def test_suggest_mandate_leaves_policy_fields_empty() -> None:
    events = [_event("e1", attributes={"gen_ai.tool.name": "read_order"})]
    mandate = suggest_mandate(events)
    assert mandate.forbidden_actions == ()
    assert mandate.escalate_when == ()


def test_suggest_mandate_no_agent_anywhere_uses_placeholder() -> None:
    events = [_event("e1", attributes={"gen_ai.tool.name": "read_order"})]
    assert suggest_mandate(events).agent == "your-agent"
