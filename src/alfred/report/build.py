"""Trace events + mandate → Digest.

See PLAN.md §5 Brique 3 for the contract and tests/test_report_build.py for
the falsifiable specification. Design decisions (pricing table, zero-count
line omission, grouping by trace_id) are recorded in
docs/adr/0005-brique3-report-engine-design.md.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date
from functools import partial

from alfred.mandate.engine import evaluate_day, evaluate_trace
from alfred.mandate.model import Deviation, Mandate
from alfred.report.model import Baseline, Digest, Line, LineKind
from alfred.trace.cost import contributing_costs
from alfred.trace.model import EventId, SpanKind, TraceEvent

_TOOL_NAME_ATTR = "gen_ai.tool.name"

# Rolling baseline (F3, docs/adr/0019). The window is the 7 calendar days before
# the digest's day; a comparison is attached only from ≥3 *active* days (days
# with any events) — fewer would let a single noisy day show a misleading mean.
BASELINE_WINDOW_DAYS = 7
_MIN_BASELINE_SAMPLE_DAYS = 3


class ReportError(Exception):
    """Raised when a Digest cannot be built."""


def _tasks_completed_line(events: Sequence[TraceEvent]) -> Line | None:
    tasks = [event for event in events if event.kind is SpanKind.AGENT_TASK]
    if not tasks:
        return None
    return Line(
        kind=LineKind.TASKS_COMPLETED,
        value=float(len(tasks)),
        sources=tuple(event.event_id for event in tasks),
    )


def _cost_line(events: Sequence[TraceEvent]) -> Line | None:
    contributing = contributing_costs(events)
    if not contributing:
        return None
    total = sum(cost for _, cost in contributing)
    return Line(
        kind=LineKind.COST_EUR,
        value=total,
        sources=tuple(event.event_id for event, _ in contributing),
    )


def _escalations_line(
    escalation_tools: frozenset[str], events: Sequence[TraceEvent]
) -> Line | None:
    """Count the calls to the mandate's escalation tools.

    Counted from real tool calls, not from the `alfred.escalated` attribute the
    agent used to write itself — which handed it a flattering Escalations line
    for free (ADR 0023 decision 4).
    """
    escalated = [
        event
        for event in events
        if event.kind is SpanKind.TOOL_CALL
        and event.attributes.get(_TOOL_NAME_ATTR) in escalation_tools
    ]
    if not escalated:
        return None
    return Line(
        kind=LineKind.ESCALATIONS,
        value=float(len(escalated)),
        sources=tuple(event.event_id for event in escalated),
    )


_LineBuilder = Callable[[Sequence[TraceEvent]], Line | None]


def _line_builders(mandate: Mandate) -> tuple[_LineBuilder, ...]:
    """The same builders compute the current day's lines and each history day's
    value, so a Baseline can never diverge from the line it contextualizes.

    Built per mandate because the Escalations line needs its `escalation_tools`
    to know what an escalation is.
    """
    return (
        _tasks_completed_line,
        _cost_line,
        partial(_escalations_line, mandate.escalation_tools),
    )


def _with_baseline(
    line: Line, builder: _LineBuilder, history: Sequence[Sequence[TraceEvent]]
) -> Line:
    """Attach a rolling baseline to `line`, computed by re-running `builder`.

    `history` is one event list per *active* day in the window (already scoped
    by the caller). A day whose builder yields no line counts as a real 0 (the
    metric didn't happen, but the day did). The baseline is attached only from
    `_MIN_BASELINE_SAMPLE_DAYS` active days and only if at least one produced a
    positive value — otherwise it has no anchoring event and is omitted.
    """
    if len(history) < _MIN_BASELINE_SAMPLE_DAYS:
        return line
    total = 0.0
    sources: list[EventId] = []
    for day_events in history:
        day_line = builder(day_events)
        if day_line is not None:
            total += day_line.value
            sources.extend(day_line.sources)
    if not sources:
        return line
    baseline = Baseline(
        mean=total / len(history),
        window_days=BASELINE_WINDOW_DAYS,
        sample_days=len(history),
        sources=tuple(dict.fromkeys(sources)),
    )
    return replace(line, baseline=baseline)


def _deviations(mandate: Mandate, events: Sequence[TraceEvent]) -> tuple[Deviation, ...]:
    """Trace-scoped checks per trace, aggregate checks once over the whole day.

    One day spans several traces (one per task), so the budget and the
    `escalate_when` rates must be computed over their union — evaluating them
    per trace turned `daily_budget_eur` into a per-task budget (ADR 0023
    decision 1).
    """
    by_trace: dict[str, list[TraceEvent]] = defaultdict(list)
    for event in events:
        by_trace[event.trace_id].append(event)
    deviations: list[Deviation] = []
    for trace_events in by_trace.values():
        deviations.extend(evaluate_trace(mandate, trace_events))
    deviations.extend(evaluate_day(mandate, events))
    return tuple(deviations)


def build_digest(
    mandate: Mandate,
    events: Sequence[TraceEvent],
    on: date,
    *,
    history: Sequence[Sequence[TraceEvent]] = (),
) -> Digest:
    """Build `mandate.agent`'s Digest for calendar day `on`.

    Contract: `events` must be non-empty and pre-scoped to one agent / one
    calendar day (caller's responsibility). Events are grouped by `trace_id`
    for the trace-scoped checks, since one day typically spans multiple traces
    (multiple tasks), while the budget and the `escalate_when` rates are
    evaluated once over the whole day (see `_deviations`).

    `history` (F3, docs/adr/0019) is one event list per *active* day in the
    trailing `BASELINE_WINDOW_DAYS`-day window, already scoped by the caller.
    When supplied, each line gains a rolling `Baseline`; empty (the default)
    keeps the plain Brique 3 digest.
    """
    if not events:
        raise ReportError("cannot build a Digest from an empty trace")
    lines: list[Line] = []
    for builder in _line_builders(mandate):
        line = builder(events)
        if line is None:
            continue
        if history:
            line = _with_baseline(line, builder, history)
        lines.append(line)
    return Digest(
        agent=mandate.agent,
        date=on,
        lines=tuple(lines),
        deviations=_deviations(mandate, events),
    )
