"""Trace events + mandate → Digest.

See PLAN.md §5 Brique 3 for the contract and tests/test_report_build.py for
the falsifiable specification. Design decisions (pricing table, zero-count
line omission, grouping by trace_id) are recorded in
docs/adr/0005-brique3-report-engine-design.md.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from alfred.mandate.engine import evaluate
from alfred.mandate.model import Deviation, Mandate
from alfred.report.model import Digest, Line, LineKind
from alfred.trace.cost import event_cost_eur
from alfred.trace.model import SpanKind, TraceEvent

_ESCALATED_ATTR = "alfred.escalated"


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
    contributing = [(event, event_cost_eur(event)) for event in events]
    contributing = [(event, cost) for event, cost in contributing if cost > 0.0]
    if not contributing:
        return None
    total = sum(cost for _, cost in contributing)
    return Line(
        kind=LineKind.COST_EUR,
        value=total,
        sources=tuple(event.event_id for event, _ in contributing),
    )


def _escalations_line(events: Sequence[TraceEvent]) -> Line | None:
    escalated = [event for event in events if event.attributes.get(_ESCALATED_ATTR) is True]
    if not escalated:
        return None
    return Line(
        kind=LineKind.ESCALATIONS,
        value=float(len(escalated)),
        sources=tuple(event.event_id for event in escalated),
    )


def _deviations(mandate: Mandate, events: Sequence[TraceEvent]) -> tuple[Deviation, ...]:
    by_trace: dict[str, list[TraceEvent]] = defaultdict(list)
    for event in events:
        by_trace[event.trace_id].append(event)
    deviations: list[Deviation] = []
    for trace_events in by_trace.values():
        deviations.extend(evaluate(mandate, trace_events))
    return tuple(deviations)


def build_digest(mandate: Mandate, events: Sequence[TraceEvent], on: date) -> Digest:
    """Build `mandate.agent`'s Digest for calendar day `on`.

    Contract: `events` must be non-empty and pre-scoped to one agent / one
    calendar day (caller's responsibility — mirrors the single-trace
    precondition already documented on `alfred.mandate.engine.evaluate`).
    Events are grouped by `trace_id` before being handed to `evaluate`,
    since one day typically spans multiple traces (multiple tasks).
    """
    if not events:
        raise ReportError("cannot build a Digest from an empty trace")
    lines = tuple(
        line
        for line in (
            _tasks_completed_line(events),
            _cost_line(events),
            _escalations_line(events),
        )
        if line is not None
    )
    return Digest(
        agent=mandate.agent,
        date=on,
        lines=lines,
        deviations=_deviations(mandate, events),
    )
