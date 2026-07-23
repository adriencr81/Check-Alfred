"""F3 — rolling baseline contextualization of digest lines.

Falsifiable spec for docs/adr/0019-baseline-contextualized-digest.md: each
number gains an `+X% vs 7-day avg` comparison, itself anchored to the
historical `event_id`s that produced the mean.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from alfred.mandate.model import EscalationRule, Mandate
from alfred.report.build import build_digest
from alfred.report.model import Baseline, Digest, Line, LineKind
from alfred.trace.model import EventId, SpanKind, TraceEvent

_ON = date(2026, 8, 30)


def _mandate() -> Mandate:
    return Mandate(
        agent="refund-bot-v3",
        allowed_tools=frozenset({"read_order", "issue_refund"}),
        daily_budget_eur=100.0,
        forbidden_actions=(),
        escalate_when=(EscalationRule("budget_used", ">", 0.80),),
    )


def _event(
    event_id: str,
    kind: SpanKind = SpanKind.TOOL_CALL,
    attributes: dict[str, object] | None = None,
) -> TraceEvent:
    return TraceEvent(
        event_id=EventId(event_id),
        trace_id=f"trace-{event_id}",
        parent_span_id=None,
        kind=kind,
        name="span",
        start_time=datetime(2026, 8, 29, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 29, 12, 0, 1, tzinfo=UTC),
        attributes=attributes or {},
    )


def _cost_day(event_id: str, cost_eur: float) -> list[TraceEvent]:
    return [_event(event_id, SpanKind.LLM_CALL, {"gen_ai.usage.cost_eur": cost_eur})]


def _tasks_day(*event_ids: str) -> list[TraceEvent]:
    return [_event(eid, SpanKind.AGENT_TASK) for eid in event_ids]


def _line(digest: Digest, kind: LineKind) -> Line:
    for line in digest.lines:
        if line.kind is kind:
            return line
    raise AssertionError(f"no {kind} line in digest")


def test_baseline_omitted_without_history() -> None:
    """Backward compatibility: no `history` keeps the plain Brique 3 digest."""
    digest = build_digest(_mandate(), _cost_day("today", 3.0), _ON)
    assert _line(digest, LineKind.COST_EUR).baseline is None


def test_baseline_omitted_below_three_active_days() -> None:
    history = [_cost_day("h1", 1.0), _cost_day("h2", 1.0)]
    digest = build_digest(_mandate(), _cost_day("today", 3.0), _ON, history=history)
    assert _line(digest, LineKind.COST_EUR).baseline is None


def test_baseline_mean_over_three_active_days() -> None:
    history = [_cost_day("h1", 1.0), _cost_day("h2", 2.0), _cost_day("h3", 3.0)]
    digest = build_digest(_mandate(), _cost_day("today", 4.0), _ON, history=history)
    baseline = _line(digest, LineKind.COST_EUR).baseline
    assert baseline is not None
    assert baseline.mean == pytest.approx(2.0)  # (1+2+3)/3
    assert baseline.window_days == 7
    assert baseline.sample_days == 3


def test_baseline_sources_union_of_history_events() -> None:
    history = [_cost_day("h1", 1.0), _cost_day("h2", 2.0), _cost_day("h3", 3.0)]
    digest = build_digest(_mandate(), _cost_day("today", 4.0), _ON, history=history)
    baseline = _line(digest, LineKind.COST_EUR).baseline
    assert baseline is not None
    assert baseline.sources == (EventId("h1"), EventId("h2"), EventId("h3"))


def test_active_day_without_the_metric_counts_as_a_real_zero() -> None:
    """A day the agent worked but spent nothing is a 0 sample, not a gap."""
    history = [_cost_day("h1", 3.0), _tasks_day("t2"), _tasks_day("t3")]
    digest = build_digest(_mandate(), _cost_day("today", 1.0), _ON, history=history)
    baseline = _line(digest, LineKind.COST_EUR).baseline
    assert baseline is not None
    assert baseline.mean == pytest.approx(1.0)  # (3+0+0)/3
    assert baseline.sources == (EventId("h1"),)  # only the day that spent anchors it


def test_baseline_omitted_when_no_active_day_has_the_metric() -> None:
    """Three active days but none spent → mean 0, no anchor → no baseline."""
    history = [_tasks_day("t1"), _tasks_day("t2"), _tasks_day("t3")]
    digest = build_digest(_mandate(), _cost_day("today", 1.0), _ON, history=history)
    assert _line(digest, LineKind.COST_EUR).baseline is None


def test_all_three_lines_are_contextualized() -> None:
    def _rich_day(tag: str) -> list[TraceEvent]:
        return [
            _event(f"{tag}-task", SpanKind.AGENT_TASK, {"alfred.escalated": True}),
            _event(f"{tag}-cost", SpanKind.LLM_CALL, {"gen_ai.usage.cost_eur": 1.0}),
        ]

    history = [_rich_day("h1"), _rich_day("h2"), _rich_day("h3")]
    today = [
        _event("today-task", SpanKind.AGENT_TASK, {"alfred.escalated": True}),
        _event("today-cost", SpanKind.LLM_CALL, {"gen_ai.usage.cost_eur": 1.0}),
    ]
    digest = build_digest(_mandate(), today, _ON, history=history)
    for kind in (LineKind.TASKS_COMPLETED, LineKind.COST_EUR, LineKind.ESCALATIONS):
        assert _line(digest, kind).baseline is not None


def test_baseline_dataclass_rejects_empty_sources() -> None:
    with pytest.raises(ValueError, match="event_id"):
        Baseline(mean=1.0, window_days=7, sample_days=3, sources=())
