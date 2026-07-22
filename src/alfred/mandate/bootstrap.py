"""Suggest a mandate from observed trace events — `alfred mandate init --from-traces`.

Only trace *facts* are proposed: the tool names actually called and the
observed daily cost. Policy fields (forbidden_actions, escalate_when) stay
empty — inferring them would be self-reported, violating the product rule that
every claim is anchored to a trace event. See
docs/adr/0018-mandate-bootstrap-and-lint.md and tests/test_mandate_bootstrap.py.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from alfred.mandate.model import Mandate
from alfred.trace.cost import event_cost_eur
from alfred.trace.model import SpanKind, TraceEvent

_TOOL_NAME_ATTR = "gen_ai.tool.name"
_AGENT_NAME_ATTR = "gen_ai.agent.name"

# Fallback when no cost is observable in the trace — matches the scaffold
# default written by `alfred init` (config._scaffold_mandate).
_DEFAULT_BUDGET_EUR = 5.00
_DEFAULT_AGENT = "your-agent"


def _observed_tools(events: Sequence[TraceEvent]) -> frozenset[str]:
    return frozenset(
        name
        for event in events
        if event.kind is SpanKind.TOOL_CALL
        and isinstance((name := event.attributes.get(_TOOL_NAME_ATTR)), str)
    )


def _observed_agent(events: Sequence[TraceEvent]) -> str | None:
    for event in events:
        name = event.attributes.get(_AGENT_NAME_ATTR)
        if isinstance(name, str) and name:
            return name
    return None


def _suggested_budget(events: Sequence[TraceEvent]) -> float:
    """Cost of the most expensive observed day, rounded up to the next euro.

    Uses the same `event_cost_eur` as the budget engine, so the suggestion and
    the later `budget_exceeded` check agree to the cent. Falls back to the
    scaffold default when nothing in the trace has a computable cost.
    """
    cost_by_day: dict[date, float] = defaultdict(float)
    for event in events:
        cost_by_day[event.start_time.date()] += event_cost_eur(event)
    peak = max(cost_by_day.values(), default=0.0)
    return float(math.ceil(peak)) if peak > 0 else _DEFAULT_BUDGET_EUR


def suggest_mandate(events: Sequence[TraceEvent], *, agent: str | None = None) -> Mandate:
    """Build a starting `Mandate` from observed events.

    `allowed_tools` and `daily_budget_eur` are observed; `agent` is taken from
    the explicit argument, else the trace's `gen_ai.agent.name`, else a
    placeholder. Policy fields are left empty for the human to fill in.
    """
    return Mandate(
        agent=agent or _observed_agent(events) or _DEFAULT_AGENT,
        allowed_tools=_observed_tools(events),
        daily_budget_eur=_suggested_budget(events),
        forbidden_actions=(),
        escalate_when=(),
    )
