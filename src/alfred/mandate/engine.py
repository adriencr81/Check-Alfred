"""Mandate evaluation engine: trace events → typed deviations.

See PLAN.md §5 Brique 2 for the four deviation types and
tests/test_mandate_engine.py for the falsifiable specification. Design
decisions (forbidden_actions DSL, cost model, escalation signal) are
recorded in docs/adr/0004-brique2-mandate-engine-design.md; structured
forbidden rules and token-based budgets (Brique 9) in ADR 0013.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable, Iterator, Sequence
from typing import Any

from alfred.mandate.model import Deviation, DeviationType, ForbiddenRule, Mandate, MandateError
from alfred.trace.cost import event_cost_eur
from alfred.trace.model import EventId, SpanKind, TraceEvent

_FORBIDDEN_PATTERN = re.compile(r"^(?P<tool>.+?)_above_(?P<amount>\d+(?:\.\d+)?)_eur$")

_TOOL_NAME_ATTR = "gen_ai.tool.name"
_TOOL_STATUS_ATTR = "tool.result.status"
_TOOL_ARGS_PREFIX = "tool.arguments."
_ESCALATED_ATTR = "alfred.escalated"

# A run of this many identical consecutive tool calls (same tool + same
# arguments) is read as an agent spinning without progress (ADR: silent-failure
# detection). Fixed, not mandate-configurable, until a real need to tune it.
_LOOP_THRESHOLD = 3

_CallSignature = tuple[str, tuple[tuple[str, Any], ...]]


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
    arg_attr = f"{_TOOL_ARGS_PREFIX}{rule.arg}"
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


_MetricComputer = Callable[
    [Mandate, Sequence[TraceEvent], Sequence[TraceEvent]], tuple[float, tuple[EventId, ...]]
]


def _tool_error_rate(
    mandate: Mandate, events: Sequence[TraceEvent], tool_calls: Sequence[TraceEvent]
) -> tuple[float, tuple[EventId, ...]]:
    if not tool_calls:
        return 0.0, ()
    errored = [event for event in tool_calls if _is_error(event)]
    return len(errored) / len(tool_calls), tuple(event.event_id for event in errored)


def _budget_used(
    mandate: Mandate, events: Sequence[TraceEvent], tool_calls: Sequence[TraceEvent]
) -> tuple[float, tuple[EventId, ...]]:
    if not mandate.daily_budget_eur:
        return 0.0, ()
    costs = [(event, event_cost_eur(event)) for event in events]
    used = sum(cost for _, cost in costs) / mandate.daily_budget_eur
    return used, tuple(event.event_id for event, cost in costs if cost > 0.0)


# Dispatch table for `escalate_when` metrics. It is the single source of truth:
# `KNOWN_ESCALATION_METRICS` is derived from its keys so the set can never drift
# from what `watch` actually computes, and `alfred.mandate.lint` reads that set
# to flag a typo'd metric statically — before it would crash a `watch` run.
_METRIC_COMPUTERS: dict[str, _MetricComputer] = {
    "tool_error_rate": _tool_error_rate,
    "budget_used": _budget_used,
}

KNOWN_ESCALATION_METRICS = frozenset(_METRIC_COMPUTERS)


def _metric_value(
    metric: str,
    mandate: Mandate,
    events: Sequence[TraceEvent],
    tool_calls: Sequence[TraceEvent],
) -> tuple[float, tuple[EventId, ...]]:
    computer = _METRIC_COMPUTERS.get(metric)
    if computer is None:
        raise MandateError(
            f"Unknown escalation metric: {metric!r} (known: {sorted(KNOWN_ESCALATION_METRICS)})"
        )
    return computer(mandate, events, tool_calls)


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


def _check_required_actions(
    mandate: Mandate, tool_calls: Sequence[TraceEvent]
) -> list[Deviation]:
    """Flag a conditional obligation that was triggered but left unsatisfied.

    For each `required_actions` rule, if `when_tool` was called in the trace
    but `require_tool` never was, raise one deviation anchored to every
    `when_tool` event — the events that created (and prove) the obligation.
    """
    by_tool: dict[str, list[TraceEvent]] = {}
    for event in tool_calls:
        if (name := _tool_name(event)) is not None:
            by_tool.setdefault(name, []).append(event)
    deviations: list[Deviation] = []
    for rule in mandate.required_actions:
        if rule.require_tool in by_tool:
            continue
        anchors = by_tool.get(rule.when_tool)
        if not anchors:
            continue
        deviations.append(
            Deviation(
                type=DeviationType.REQUIRED_ACTION_MISSING,
                event_ids=tuple(event.event_id for event in anchors),
                message=(
                    f"required action missing: '{rule.when_tool}' was called but "
                    f"'{rule.require_tool}' never was"
                ),
                details={"when_tool": rule.when_tool, "require_tool": rule.require_tool},
            )
        )
    return deviations


def _call_signature(event: TraceEvent) -> _CallSignature | None:
    """`(tool, sorted arguments)` — identical signatures mean an identical call.

    Returns None for a tool call without a resolvable name, so it can never
    extend or start a run.
    """
    tool = _tool_name(event)
    if tool is None:
        return None
    arguments = tuple(
        sorted(
            (key, value)
            for key, value in event.attributes.items()
            if key.startswith(_TOOL_ARGS_PREFIX)
        )
    )
    return tool, arguments


def _loop_deviation(run: Sequence[TraceEvent], signature: _CallSignature | None) -> list[Deviation]:
    if signature is None or len(run) < _LOOP_THRESHOLD:
        return []
    tool, _ = signature
    return [
        Deviation(
            type=DeviationType.LOOP_DETECTED,
            event_ids=tuple(event.event_id for event in run),
            message=f"tool '{tool}' called {len(run)} times in a row with identical arguments",
            details={"tool": tool, "count": len(run)},
        )
    ]


def _check_repeated_action(tool_calls: Sequence[TraceEvent]) -> list[Deviation]:
    """Flag every run of ≥ `_LOOP_THRESHOLD` identical consecutive tool calls.

    Identical = same tool name and the same `tool.arguments.*` — the signature
    of an agent stuck retrying without progress. Anchored to every event in the
    run. Consecutive is judged over the tool-call subsequence ordered by
    `start_time`, so interleaved LLM/agent spans don't break a loop apart.
    """
    ordered = sorted(tool_calls, key=lambda event: event.start_time)
    deviations: list[Deviation] = []
    for signature, group in itertools.groupby(ordered, key=_call_signature):
        deviations.extend(_loop_deviation(list(group), signature))
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
        *_check_required_actions(mandate, tool_calls),
        *_check_repeated_action(tool_calls),
    ]
