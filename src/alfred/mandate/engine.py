"""Mandate evaluation engine: trace events → typed deviations.

See PLAN.md §5 Brique 2 for the four deviation types and
tests/test_mandate_engine.py for the falsifiable specification. Design
decisions (forbidden_actions DSL, cost model, escalation signal) are
recorded in docs/adr/0004-brique2-mandate-engine-design.md.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from alfred.cost import event_cost_eur
from alfred.mandate.model import Deviation, DeviationType, Mandate, MandateError
from alfred.trace.model import EventId, SpanKind, TraceEvent

_FORBIDDEN_PATTERN = re.compile(r"^(?P<tool>.+?)_above_(?P<amount>\d+(?:\.\d+)?)_eur$")

_TOOL_NAME_ATTR = "gen_ai.tool.name"
_TOOL_STATUS_ATTR = "tool.result.status"
_TOOL_AMOUNT_ATTR = "tool.arguments.amount_eur"
_ESCALATED_ATTR = "alfred.escalated"


def _tool_calls(events: Sequence[TraceEvent]) -> list[TraceEvent]:
    return [event for event in events if event.kind is SpanKind.TOOL_CALL]


def _tool_name(event: TraceEvent) -> str | None:
    name = event.attributes.get(_TOOL_NAME_ATTR)
    return name if isinstance(name, str) else None


def _is_error(event: TraceEvent) -> bool:
    status = event.attributes.get(_TOOL_STATUS_ATTR)
    return isinstance(status, str) and status.lower() != "ok"


def _is_escalated(events: Sequence[TraceEvent]) -> bool:
    return any(event.attributes.get(_ESCALATED_ATTR) is True for event in events)


def _check_tool_not_allowed(mandate: Mandate, tool_calls: Sequence[TraceEvent]) -> list[Deviation]:
    deviations: list[Deviation] = []
    for event in tool_calls:
        tool = _tool_name(event)
        if tool is not None and tool not in mandate.allowed_tools:
            deviations.append(
                Deviation(
                    type=DeviationType.TOOL_NOT_ALLOWED,
                    event_ids=(event.event_id,),
                    message=f"tool '{tool}' is not in allowed_tools",
                    details={"tool": tool},
                )
            )
    return deviations


def _check_forbidden_actions(mandate: Mandate, tool_calls: Sequence[TraceEvent]) -> list[Deviation]:
    deviations: list[Deviation] = []
    for action in mandate.forbidden_actions:
        match = _FORBIDDEN_PATTERN.match(action)
        if match is not None:
            tool, threshold = match["tool"], float(match["amount"])
            for event in tool_calls:
                if _tool_name(event) != tool:
                    continue
                amount = event.attributes.get(_TOOL_AMOUNT_ATTR)
                if isinstance(amount, int | float) and float(amount) > threshold:
                    deviations.append(
                        Deviation(
                            type=DeviationType.FORBIDDEN_ACTION,
                            event_ids=(event.event_id,),
                            message=(
                                f"forbidden action '{action}': {tool} called with "
                                f"amount_eur={float(amount)} > {threshold}"
                            ),
                            details={"action": action, "tool": tool, "amount_eur": float(amount)},
                        )
                    )
        else:
            for event in tool_calls:
                if _tool_name(event) == action:
                    deviations.append(
                        Deviation(
                            type=DeviationType.FORBIDDEN_ACTION,
                            event_ids=(event.event_id,),
                            message=f"forbidden action '{action}' was called",
                            details={"action": action, "tool": action},
                        )
                    )
    return deviations


def _check_budget_exceeded(mandate: Mandate, events: Sequence[TraceEvent]) -> list[Deviation]:
    contributing = [event for event in events if event_cost_eur(event) > 0.0]
    total = sum(event_cost_eur(event) for event in contributing)
    if total > mandate.daily_budget_eur:
        return [
            Deviation(
                type=DeviationType.BUDGET_EXCEEDED,
                event_ids=tuple(event.event_id for event in contributing),
                message=(
                    f"trace cost {total:.2f}€ exceeds daily_budget_eur "
                    f"{mandate.daily_budget_eur:.2f}€"
                ),
                details={"cost_eur": total, "budget_eur": mandate.daily_budget_eur},
            )
        ]
    return []


def _metric_value(
    metric: str,
    mandate: Mandate,
    events: Sequence[TraceEvent],
    tool_calls: Sequence[TraceEvent],
) -> tuple[float, tuple[EventId, ...]]:
    if metric == "tool_error_rate":
        if not tool_calls:
            return 0.0, ()
        errored = [event for event in tool_calls if _is_error(event)]
        return len(errored) / len(tool_calls), tuple(event.event_id for event in errored)
    if metric == "budget_used":
        if not mandate.daily_budget_eur:
            return 0.0, ()
        contributing = [event for event in events if event_cost_eur(event) > 0.0]
        used = sum(event_cost_eur(event) for event in contributing) / mandate.daily_budget_eur
        return used, tuple(event.event_id for event in contributing)
    raise MandateError(f"Unknown escalation metric: {metric!r}")


def _check_escalation_missed(
    mandate: Mandate,
    events: Sequence[TraceEvent],
    tool_calls: Sequence[TraceEvent],
) -> list[Deviation]:
    if _is_escalated(events):
        return []
    deviations: list[Deviation] = []
    for rule in mandate.escalate_when:
        value, source_ids = _metric_value(rule.metric, mandate, events, tool_calls)
        if source_ids and rule.breached(value):
            deviations.append(
                Deviation(
                    type=DeviationType.ESCALATION_MISSED,
                    event_ids=source_ids,
                    message=(
                        f"{rule.metric}={value:.2f} breaches "
                        f"'{rule.metric} {rule.operator} {rule.threshold}' without escalation"
                    ),
                    details={"metric": rule.metric, "value": value, "threshold": rule.threshold},
                )
            )
    return deviations


def evaluate(mandate: Mandate, events: Sequence[TraceEvent]) -> list[Deviation]:
    """Compare one agent-day's events against a mandate.

    Contract: `events` is every event of one agent for one calendar day
    (UTC) — the same scope `build_digest` receives. Per-event checks
    (tool_not_allowed, forbidden_action) are scope-independent; aggregated
    checks (budget_exceeded, escalation_missed) are computed over the whole
    day, because `daily_budget_eur` is a day budget, not a trace budget.
    See docs/adr/0011-day-scope-mandate-evaluation.md. Returns every
    `Deviation` detected, each anchored to at least one `event_id` from
    `events`.
    """
    tool_calls = _tool_calls(events)
    return [
        *_check_tool_not_allowed(mandate, tool_calls),
        *_check_forbidden_actions(mandate, tool_calls),
        *_check_budget_exceeded(mandate, events),
        *_check_escalation_missed(mandate, events, tool_calls),
    ]
