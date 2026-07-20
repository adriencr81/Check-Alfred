"""Mandate evaluation engine: trace events → typed deviations.

See PLAN.md §5 Brique 2 for the four deviation types and
tests/test_mandate_engine.py for the falsifiable specification. Design
decisions (forbidden_actions DSL, cost model, escalation signal) are
recorded in docs/adr/0004-brique2-mandate-engine-design.md; structured
forbidden rules and token-based budgets (Brique 9) in ADR 0013.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence

from alfred.mandate.model import Deviation, DeviationType, ForbiddenRule, Mandate, MandateError
from alfred.trace.cost import event_cost_eur
from alfred.trace.model import EventId, SpanKind, TraceEvent

_FORBIDDEN_PATTERN = re.compile(r"^(?P<tool>.+?)_above_(?P<amount>\d+(?:\.\d+)?)_eur$")

_TOOL_NAME_ATTR = "gen_ai.tool.name"
_TOOL_STATUS_ATTR = "tool.result.status"
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


def _check_tool_not_allowed(
    mandate: Mandate, tool_calls: Sequence[TraceEvent]
) -> list[Deviation]:
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


def _rule_matches(
    rule: ForbiddenRule, tool_calls: Sequence[TraceEvent]
) -> Iterator[tuple[TraceEvent, float]]:
    """Yield (event, argument value) for each tool call breaching `rule`."""
    arg_attr = f"tool.arguments.{rule.arg}"
    for event in tool_calls:
        if _tool_name(event) != rule.tool:
            continue
        value = event.attributes.get(arg_attr)
        if isinstance(value, int | float) and rule.triggered_by(float(value)):
            yield event, float(value)


def _check_forbidden_actions(
    mandate: Mandate, tool_calls: Sequence[TraceEvent]
) -> list[Deviation]:
    deviations: list[Deviation] = []
    for action in mandate.forbidden_actions:
        if isinstance(action, ForbiddenRule):
            for event, value in _rule_matches(action, tool_calls):
                deviations.append(
                    Deviation(
                        type=DeviationType.FORBIDDEN_ACTION,
                        event_ids=(event.event_id,),
                        message=(
                            f"forbidden action: {action.tool} called with "
                            f"{action.arg}={value}, breaching '{action.when}'"
                        ),
                        details={"tool": action.tool, "when": action.when, "value": value},
                    )
                )
            continue
        match = _FORBIDDEN_PATTERN.match(action)
        if match is not None:
            # The legacy DSL string is a fixed-shape ForbiddenRule; only the
            # message/details shape is kept distinct for backwards compat.
            tool, threshold = match["tool"], float(match["amount"])
            rule = ForbiddenRule(tool=tool, arg="amount_eur", operator=">", threshold=threshold)
            for event, amount in _rule_matches(rule, tool_calls):
                deviations.append(
                    Deviation(
                        type=DeviationType.FORBIDDEN_ACTION,
                        event_ids=(event.event_id,),
                        message=(
                            f"forbidden action '{action}': {tool} called with "
                            f"amount_eur={amount} > {threshold}"
                        ),
                        details={"action": action, "tool": tool, "amount_eur": amount},
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
    costs = [(event, event_cost_eur(event)) for event in events]
    contributing = [(event, cost) for event, cost in costs if cost > 0.0]
    total = sum(cost for _, cost in contributing)
    if total > mandate.daily_budget_eur:
        return [
            Deviation(
                type=DeviationType.BUDGET_EXCEEDED,
                event_ids=tuple(event.event_id for event, _ in contributing),
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
        costs = [(event, event_cost_eur(event)) for event in events]
        used = sum(cost for _, cost in costs) / mandate.daily_budget_eur
        return used, tuple(event.event_id for event, cost in costs if cost > 0.0)
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
    """Compare a single trace's events against a mandate.

    Contract: `events` must belong to one trace (e.g. via
    `TraceStore.find_by_trace`). Returns every `Deviation` detected, each
    anchored to at least one `event_id` from `events`.
    """
    tool_calls = _tool_calls(events)
    return [
        *_check_tool_not_allowed(mandate, tool_calls),
        *_check_forbidden_actions(mandate, tool_calls),
        *_check_budget_exceeded(mandate, events),
        *_check_escalation_missed(mandate, events, tool_calls),
    ]
