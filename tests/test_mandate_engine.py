"""Mandate evaluation engine — one test per deviation type + its mirror.

See PLAN.md §5 Brique 2. Design decisions (forbidden_actions DSL, cost
model, escalation signal) are recorded in
docs/adr/0004-brique2-mandate-engine-design.md.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from alfred.mandate.engine import evaluate
from alfred.mandate.model import EscalationRule, ForbiddenRule, Mandate, RequiredAction
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


def _sql_mandate() -> Mandate:
    """Structured-rule mandate (Brique 9): forbid SQL touching > 1000 rows."""
    return Mandate(
        agent="sql-analyst",
        allowed_tools=frozenset({"execute_sql", "send_report"}),
        daily_budget_eur=3.0,
        forbidden_actions=(ForbiddenRule("execute_sql", "rows_affected", ">", 1000.0),),
        escalate_when=(),
    )


def test_structured_forbidden_rule_triggers() -> None:
    events = [
        _event(
            "e1",
            attributes={"gen_ai.tool.name": "execute_sql", "tool.arguments.rows_affected": 5000},
        )
    ]
    deviations = evaluate(_sql_mandate(), events)
    assert len(deviations) == 1
    assert deviations[0].type.value == "forbidden_action"
    assert deviations[0].event_ids == (EventId("e1"),)


def test_structured_forbidden_rule_conforming_trace() -> None:
    events = [
        _event(
            "e1",
            attributes={"gen_ai.tool.name": "execute_sql", "tool.arguments.rows_affected": 12},
        )
    ]
    assert evaluate(_sql_mandate(), events) == []


def test_budget_from_tokens_without_cost_attr() -> None:
    """Tokens + known model, no cost_eur → budget_exceeded and budget_used work."""
    mandate = Mandate(
        agent="refund-bot-v3",
        allowed_tools=frozenset({"read_order"}),
        daily_budget_eur=0.01,
        forbidden_actions=(),
        escalate_when=(EscalationRule("budget_used", ">", 0.80),),
    )
    events = [
        _event(
            "e1",
            kind=SpanKind.LLM_CALL,
            attributes={
                "gen_ai.response.model": "gpt-4o",
                "gen_ai.usage.input_tokens": 2000,
                "gen_ai.usage.output_tokens": 1000,
            },
        )
    ]
    deviations = evaluate(mandate, events)
    budget = [d for d in deviations if d.type.value == "budget_exceeded"]
    assert len(budget) == 1
    assert budget[0].event_ids == (EventId("e1"),)
    assert budget[0].details["cost_eur"] == pytest.approx(2 * 0.00250 + 1 * 0.01000)
    escalation = [d for d in deviations if d.type.value == "escalation_missed"]
    assert len(escalation) == 1
    assert escalation[0].event_ids == (EventId("e1"),)


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


def _notify_mandate() -> Mandate:
    """A mandate requiring `notify_customer` whenever `issue_refund` runs."""
    return Mandate(
        agent="refund-bot-v3",
        allowed_tools=frozenset({"issue_refund", "notify_customer"}),
        daily_budget_eur=5.0,
        forbidden_actions=(),
        escalate_when=(),
        required_actions=(RequiredAction("issue_refund", "notify_customer"),),
    )


def test_required_action_missing_detected() -> None:
    events = [_event("e1", attributes={"gen_ai.tool.name": "issue_refund"})]
    deviations = evaluate(_notify_mandate(), events)
    matches = [d for d in deviations if d.type.value == "required_action_missing"]
    assert len(matches) == 1
    assert matches[0].event_ids == (EventId("e1"),)


def test_required_action_satisfied_when_follow_up_present() -> None:
    events = [
        _event("e1", attributes={"gen_ai.tool.name": "issue_refund"}),
        _event("e2", attributes={"gen_ai.tool.name": "notify_customer"}),
    ]
    deviations = evaluate(_notify_mandate(), events)
    assert not any(d.type.value == "required_action_missing" for d in deviations)


def test_required_action_not_triggered_without_when_tool() -> None:
    events = [_event("e1", attributes={"gen_ai.tool.name": "notify_customer"})]
    deviations = evaluate(_notify_mandate(), events)
    assert not any(d.type.value == "required_action_missing" for d in deviations)


def test_loop_detected_on_repeated_identical_calls() -> None:
    events = [
        _event(eid, attributes={"gen_ai.tool.name": "read_order", "tool.arguments.id": "A"})
        for eid in ("e1", "e2", "e3")
    ]
    deviations = evaluate(_mandate(), events)
    matches = [d for d in deviations if d.type.value == "loop_detected"]
    assert len(matches) == 1
    assert matches[0].event_ids == (EventId("e1"), EventId("e2"), EventId("e3"))


def test_loop_absent_when_arguments_change() -> None:
    events = [
        _event("e1", attributes={"gen_ai.tool.name": "read_order", "tool.arguments.id": "A"}),
        _event("e2", attributes={"gen_ai.tool.name": "read_order", "tool.arguments.id": "B"}),
        _event("e3", attributes={"gen_ai.tool.name": "read_order", "tool.arguments.id": "C"}),
    ]
    deviations = evaluate(_mandate(), events)
    assert not any(d.type.value == "loop_detected" for d in deviations)


def test_loop_absent_below_threshold() -> None:
    events = [
        _event(eid, attributes={"gen_ai.tool.name": "read_order", "tool.arguments.id": "A"})
        for eid in ("e1", "e2")
    ]
    deviations = evaluate(_mandate(), events)
    assert not any(d.type.value == "loop_detected" for d in deviations)


def test_loop_threshold_from_mandate_lowers_the_bar() -> None:
    mandate = replace(_mandate(), loop_threshold=2)
    events = [
        _event(eid, attributes={"gen_ai.tool.name": "read_order", "tool.arguments.id": "A"})
        for eid in ("e1", "e2")
    ]
    matches = [d for d in evaluate(mandate, events) if d.type.value == "loop_detected"]
    assert len(matches) == 1
    assert matches[0].event_ids == (EventId("e1"), EventId("e2"))


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
