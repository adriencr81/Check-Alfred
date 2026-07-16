"""Mandate evaluation engine — one test per deviation type + its mirror.

See PLAN.md §5 Brique 2. Design decisions (forbidden_actions DSL, cost
model, escalation signal) are recorded in
docs/adr/0004-brique2-mandate-engine-design.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

from alfred.mandate.engine import evaluate
from alfred.mandate.model import EscalationRule, Mandate
from alfred.trace.model import EventId, SpanKind, TraceEvent


def _mandate() -> Mandate:
    return Mandate(
        agent="refund-bot-v3",
        allowed_tools=frozenset({"read_order", "issue_refund", "notify_customer"}),
        daily_budget_eur=5.0,
        forbidden_actions=("issue_refund_above_100_eur", "send_marketing"),
        escalate_when=(
            EscalationRule("tool_error_rate", ">", 0.10),
            EscalationRule("budget_used", ">", 0.80),
        ),
    )


def _event(
    event_id: str,
    kind: SpanKind = SpanKind.TOOL_CALL,
    attributes: dict[str, object] | None = None,
) -> TraceEvent:
    return TraceEvent(
        event_id=EventId(event_id),
        trace_id="trace-1",
        parent_span_id=None,
        kind=kind,
        name="span",
        start_time=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 12, 0, 1, tzinfo=UTC),
        attributes=attributes or {},
    )


def test_compliant_trace_produces_no_deviations() -> None:
    events = [
        _event("e1", attributes={"gen_ai.tool.name": "read_order", "tool.result.status": "ok"}),
        _event(
            "e2",
            attributes={
                "gen_ai.tool.name": "issue_refund",
                "tool.arguments.amount_eur": 42.50,
                "tool.result.status": "ok",
            },
        ),
        _event("e3", kind=SpanKind.LLM_CALL, attributes={"gen_ai.usage.cost_eur": 1.0}),
    ]
    assert evaluate(_mandate(), events) == []


def test_tool_not_allowed_detected() -> None:
    events = [_event("e1", attributes={"gen_ai.tool.name": "read_pii"})]
    deviations = evaluate(_mandate(), events)
    matches = [d for d in deviations if d.type.value == "tool_not_allowed"]
    assert len(matches) == 1
    assert matches[0].event_ids == (EventId("e1"),)


def test_tool_not_allowed_absent_for_allowed_tool() -> None:
    events = [_event("e1", attributes={"gen_ai.tool.name": "read_order"})]
    deviations = evaluate(_mandate(), events)
    assert not any(d.type.value == "tool_not_allowed" for d in deviations)


def test_forbidden_action_threshold_detected() -> None:
    events = [
        _event(
            "e1",
            attributes={"gen_ai.tool.name": "issue_refund", "tool.arguments.amount_eur": 150.0},
        )
    ]
    deviations = evaluate(_mandate(), events)
    matches = [d for d in deviations if d.type.value == "forbidden_action"]
    assert len(matches) == 1
    assert matches[0].event_ids == (EventId("e1"),)


def test_forbidden_action_absent_under_threshold() -> None:
    events = [
        _event(
            "e1",
            attributes={"gen_ai.tool.name": "issue_refund", "tool.arguments.amount_eur": 42.50},
        )
    ]
    deviations = evaluate(_mandate(), events)
    assert not any(d.type.value == "forbidden_action" for d in deviations)


def test_forbidden_action_exact_name_detected() -> None:
    events = [_event("e1", attributes={"gen_ai.tool.name": "send_marketing"})]
    deviations = evaluate(_mandate(), events)
    matches = [d for d in deviations if d.type.value == "forbidden_action"]
    assert len(matches) == 1
    assert matches[0].event_ids == (EventId("e1"),)


def test_budget_exceeded_detected() -> None:
    events = [_event("e1", kind=SpanKind.LLM_CALL, attributes={"gen_ai.usage.cost_eur": 6.0})]
    deviations = evaluate(_mandate(), events)
    matches = [d for d in deviations if d.type.value == "budget_exceeded"]
    assert len(matches) == 1
    assert matches[0].event_ids == (EventId("e1"),)


def test_budget_exceeded_absent_under_budget() -> None:
    events = [_event("e1", kind=SpanKind.LLM_CALL, attributes={"gen_ai.usage.cost_eur": 2.0})]
    deviations = evaluate(_mandate(), events)
    assert not any(d.type.value == "budget_exceeded" for d in deviations)


def test_escalation_missed_on_tool_error_rate() -> None:
    events = [
        _event(
            "e1", attributes={"gen_ai.tool.name": "read_order", "tool.result.status": "error"}
        )
    ]
    deviations = evaluate(_mandate(), events)
    matches = [d for d in deviations if d.type.value == "escalation_missed"]
    assert len(matches) == 1
    assert matches[0].event_ids == (EventId("e1"),)


def test_escalation_missed_absent_when_agent_escalates() -> None:
    events = [
        _event(
            "e1", attributes={"gen_ai.tool.name": "read_order", "tool.result.status": "error"}
        ),
        _event("e2", kind=SpanKind.AGENT_TASK, attributes={"alfred.escalated": True}),
    ]
    deviations = evaluate(_mandate(), events)
    assert not any(d.type.value == "escalation_missed" for d in deviations)


def test_escalation_missed_absent_below_threshold() -> None:
    events = [
        _event("e1", attributes={"gen_ai.tool.name": "read_order", "tool.result.status": "ok"}),
        _event("e2", attributes={"gen_ai.tool.name": "read_order", "tool.result.status": "ok"}),
    ]
    deviations = evaluate(_mandate(), events)
    assert not any(d.type.value == "escalation_missed" for d in deviations)


def test_deviation_carries_event_ids_present_in_trace() -> None:
    events = [
        _event("e1", attributes={"gen_ai.tool.name": "read_pii"}),
        _event(
            "e2",
            attributes={"gen_ai.tool.name": "issue_refund", "tool.arguments.amount_eur": 150.0},
        ),
        _event("e3", kind=SpanKind.LLM_CALL, attributes={"gen_ai.usage.cost_eur": 6.0}),
    ]
    all_ids = {event.event_id for event in events}
    deviations = evaluate(_mandate(), events)
    assert deviations
    for deviation in deviations:
        assert deviation.event_ids
        assert set(deviation.event_ids).issubset(all_ids)
