"""Report engine — trace events + mandate → Digest.

See PLAN.md §5 Brique 3. Design decisions (pricing table, zero-count line
omission, grouping by trace_id) are recorded in
docs/adr/0005-brique3-report-engine-design.md.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from alfred.cost import event_cost_eur
from alfred.mandate.model import EscalationRule, Mandate
from alfred.report.build import ReportError, build_digest
from alfred.report.model import Digest, Line, LineKind
from alfred.trace.model import EventId, SpanKind, TraceEvent
from alfred.trace.store import TraceStore


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
    trace_id: str = "trace-1",
    kind: SpanKind = SpanKind.TOOL_CALL,
    attributes: dict[str, object] | None = None,
) -> TraceEvent:
    return TraceEvent(
        event_id=EventId(event_id),
        trace_id=trace_id,
        parent_span_id=None,
        kind=kind,
        name="span",
        start_time=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 12, 0, 1, tzinfo=UTC),
        attributes=attributes or {},
    )


def _line(digest: Digest, kind: LineKind) -> Line:
    for line in digest.lines:
        if line.kind is kind:
            return line
    raise AssertionError(f"no {kind} line in digest")


def _typical_day_events() -> list[TraceEvent]:
    """Two tasks (two traces) on the same day: one clean, one deviating."""
    return [
        _event("e1", trace_id="trace-1", kind=SpanKind.AGENT_TASK),
        _event(
            "e2",
            trace_id="trace-1",
            attributes={"gen_ai.tool.name": "read_order", "tool.result.status": "ok"},
        ),
        _event(
            "e3",
            trace_id="trace-1",
            attributes={
                "gen_ai.tool.name": "issue_refund",
                "tool.arguments.amount_eur": 42.50,
                "tool.result.status": "ok",
            },
        ),
        _event(
            "e4",
            trace_id="trace-1",
            kind=SpanKind.LLM_CALL,
            attributes={
                "gen_ai.response.model": "gpt-4o-mini-2024-07-18",
                "gen_ai.usage.input_tokens": 1000,
                "gen_ai.usage.output_tokens": 200,
            },
        ),
        _event(
            "e8",
            trace_id="trace-1",
            kind=SpanKind.LLM_CALL,
            attributes={"gen_ai.usage.cost_eur": 0.50},
        ),
        _event("e5", trace_id="trace-2", kind=SpanKind.AGENT_TASK),
        _event("e6", trace_id="trace-2", attributes={"gen_ai.tool.name": "read_pii"}),
        _event(
            "e7",
            trace_id="trace-2",
            kind=SpanKind.AGENT_TASK,
            attributes={"alfred.escalated": True},
        ),
    ]


def test_build_digest_raises_on_empty_events() -> None:
    with pytest.raises(ReportError, match="empty"):
        build_digest(_mandate(), [], date(2026, 8, 30))


def test_tasks_completed_counts_agent_task_spans() -> None:
    events = [
        _event("e1", kind=SpanKind.AGENT_TASK),
        _event("e2", kind=SpanKind.AGENT_TASK),
    ]
    digest = build_digest(_mandate(), events, date(2026, 8, 30))
    line = _line(digest, LineKind.TASKS_COMPLETED)
    assert line.value == 2.0
    assert line.sources == (EventId("e1"), EventId("e2"))


def test_tasks_completed_line_absent_when_no_agent_task() -> None:
    events = [_event("e1", attributes={"gen_ai.tool.name": "read_order"})]
    digest = build_digest(_mandate(), events, date(2026, 8, 30))
    assert all(line.kind is not LineKind.TASKS_COMPLETED for line in digest.lines)


def test_cost_line_uses_cost_eur_when_present() -> None:
    events = [_event("e1", kind=SpanKind.LLM_CALL, attributes={"gen_ai.usage.cost_eur": 1.25})]
    digest = build_digest(_mandate(), events, date(2026, 8, 30))
    line = _line(digest, LineKind.COST_EUR)
    assert line.value == pytest.approx(1.25)
    assert line.sources == (EventId("e1"),)


def test_cost_line_falls_back_to_pricing_table() -> None:
    events = [
        _event(
            "e1",
            kind=SpanKind.LLM_CALL,
            attributes={
                "gen_ai.response.model": "gpt-4o-mini-2024-07-18",
                "gen_ai.usage.input_tokens": 1000,
                "gen_ai.usage.output_tokens": 200,
            },
        )
    ]
    digest = build_digest(_mandate(), events, date(2026, 8, 30))
    line = _line(digest, LineKind.COST_EUR)
    expected = (1000 / 1000) * 0.00015 + (200 / 1000) * 0.00060
    assert line.value == pytest.approx(expected)


def test_cost_line_absent_when_unpriced() -> None:
    events = [
        _event(
            "e1",
            kind=SpanKind.LLM_CALL,
            attributes={
                "gen_ai.response.model": "some-unknown-model",
                "gen_ai.usage.input_tokens": 1000,
                "gen_ai.usage.output_tokens": 200,
            },
        ),
        _event("e2", kind=SpanKind.AGENT_TASK),
    ]
    digest = build_digest(_mandate(), events, date(2026, 8, 30))
    assert all(line.kind is not LineKind.COST_EUR for line in digest.lines)


def test_escalations_line_counts_alfred_escalated_events() -> None:
    events = [
        _event("e1", kind=SpanKind.AGENT_TASK, attributes={"alfred.escalated": True}),
        _event("e2", attributes={"gen_ai.tool.name": "read_order"}),
    ]
    digest = build_digest(_mandate(), events, date(2026, 8, 30))
    line = _line(digest, LineKind.ESCALATIONS)
    assert line.value == 1.0
    assert line.sources == (EventId("e1"),)


def test_escalations_line_absent_when_none() -> None:
    events = [_event("e1", attributes={"gen_ai.tool.name": "read_order"})]
    digest = build_digest(_mandate(), events, date(2026, 8, 30))
    assert all(line.kind is not LineKind.ESCALATIONS for line in digest.lines)


def test_deviations_span_multiple_traces_in_one_day() -> None:
    events = [
        _event("e1", trace_id="trace-a", attributes={"gen_ai.tool.name": "read_pii"}),
        _event(
            "e2",
            trace_id="trace-b",
            kind=SpanKind.LLM_CALL,
            attributes={"gen_ai.usage.cost_eur": 10.0},
        ),
    ]
    digest = build_digest(_mandate(), events, date(2026, 8, 30))
    types = {deviation.type.value for deviation in digest.deviations}
    assert types == {"tool_not_allowed", "budget_exceeded", "escalation_missed"}
    assert len(digest.deviations) == 3


def test_digest_every_line_has_sources() -> None:
    digest = build_digest(_mandate(), _typical_day_events(), date(2026, 8, 30))
    assert digest.lines
    for line in digest.lines:
        assert line.sources
    for deviation in digest.deviations:
        assert deviation.event_ids


def test_digest_sources_exist_in_store(tmp_path: Path) -> None:
    events = _typical_day_events()
    store = TraceStore(tmp_path / "trace.db")
    store.put_many(events)
    digest = build_digest(_mandate(), events, date(2026, 8, 30))
    for line in digest.lines:
        for event_id in line.sources:
            assert store.get(event_id) is not None
    for deviation in digest.deviations:
        for event_id in deviation.event_ids:
            assert store.get(event_id) is not None
    store.close()


def test_digest_cost_matches_sum() -> None:
    events = _typical_day_events()
    digest = build_digest(_mandate(), events, date(2026, 8, 30))
    cost_line = _line(digest, LineKind.COST_EUR)
    by_id = {event.event_id: event for event in events}
    expected = sum(event_cost_eur(by_id[event_id]) for event_id in cost_line.sources)
    assert cost_line.value == pytest.approx(expected)


def test_reference_day_digest_snapshot() -> None:
    """Fixture 'trace journée type' (PLAN.md §5 Brique 3 definition-of-done)."""
    digest = build_digest(_mandate(), _typical_day_events(), date(2026, 8, 30))

    assert digest.agent == "refund-bot-v3"
    assert digest.date == date(2026, 8, 30)

    tasks = _line(digest, LineKind.TASKS_COMPLETED)
    assert tasks.value == 3.0
    assert tasks.sources == (EventId("e1"), EventId("e5"), EventId("e7"))

    cost = _line(digest, LineKind.COST_EUR)
    assert cost.value == pytest.approx(0.00015 + 0.00012 + 0.50)
    assert cost.sources == (EventId("e4"), EventId("e8"))

    escalations = _line(digest, LineKind.ESCALATIONS)
    assert escalations.value == 1.0
    assert escalations.sources == (EventId("e7"),)

    assert len(digest.deviations) == 1
    deviation = digest.deviations[0]
    assert deviation.type.value == "tool_not_allowed"
    assert deviation.event_ids == (EventId("e6"),)
