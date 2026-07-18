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
from alfred.trace.model import EventId, SpanKind, TraceEvent

_COST_ATTR = "gen_ai.usage.cost_eur"
_MODEL_ATTR = "gen_ai.response.model"
_INPUT_TOKENS_ATTR = "gen_ai.usage.input_tokens"
_OUTPUT_TOKENS_ATTR = "gen_ai.usage.output_tokens"
_ESCALATED_ATTR = "alfred.escalated"

# €/1K-token rates (input, output), keyed by gen_ai.response.model. Public
# pricing snapshot, not tied to any date — extend as new models are seen.
# See docs/adr/0005-brique3-report-engine-design.md.
_PRICING_EUR_PER_1K_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.00060),
    "gpt-4o-mini-2024-07-18": (0.00015, 0.00060),
    "gpt-4o": (0.00250, 0.01000),
    "gpt-4o-2024-08-06": (0.00250, 0.01000),
    # Anthropic public $/MTok converted at a fixed 0.92 USD→EUR snapshot,
    # same convention as above. See docs/adr/0011-brique8-langgraph-adapter.md.
    "claude-opus-4-8": (0.00460, 0.02300),
    "claude-sonnet-5": (0.00276, 0.01380),
    "claude-haiku-4-5": (0.00092, 0.00460),
}


class ReportError(Exception):
    """Raised when a Digest cannot be built."""


def _event_cost_eur(event: TraceEvent) -> float:
    cost = event.attributes.get(_COST_ATTR)
    if isinstance(cost, int | float):
        return float(cost)
    model = event.attributes.get(_MODEL_ATTR)
    rates = _PRICING_EUR_PER_1K_TOKENS.get(model) if isinstance(model, str) else None
    input_tokens = event.attributes.get(_INPUT_TOKENS_ATTR)
    output_tokens = event.attributes.get(_OUTPUT_TOKENS_ATTR)
    if (
        rates is not None
        and isinstance(input_tokens, int | float)
        and isinstance(output_tokens, int | float)
    ):
        rate_in, rate_out = rates
        return (input_tokens / 1000) * rate_in + (output_tokens / 1000) * rate_out
    return 0.0


def _has_agent_task_ancestor(event: TraceEvent, by_id: dict[EventId, TraceEvent]) -> bool:
    seen: set[str] = set()
    parent = event.parent_span_id
    while parent and parent not in seen:
        seen.add(parent)
        ancestor = by_id.get(EventId(parent))
        if ancestor is None:
            return False
        if ancestor.kind is SpanKind.AGENT_TASK:
            return True
        parent = ancestor.parent_span_id
    return False


def _tasks_completed_line(events: Sequence[TraceEvent]) -> Line | None:
    # Real instrumentors nest an inner invoke_agent span under the root
    # one — only ancestor-free agent spans count as tasks (ADR 0011).
    by_id = {event.event_id: event for event in events}
    tasks = [
        event
        for event in events
        if event.kind is SpanKind.AGENT_TASK and not _has_agent_task_ancestor(event, by_id)
    ]
    if not tasks:
        return None
    return Line(
        kind=LineKind.TASKS_COMPLETED,
        value=float(len(tasks)),
        sources=tuple(event.event_id for event in tasks),
    )


def _cost_line(events: Sequence[TraceEvent]) -> Line | None:
    contributing = [(event, _event_cost_eur(event)) for event in events]
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
