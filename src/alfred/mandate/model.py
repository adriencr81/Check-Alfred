"""Mandate + deviation model.

Invariant (see PLAN.md §5 Brique 2): every `Deviation` must carry at least
one `event_id` from the trace that proves it — no deviation without an
anchor, mirroring the `TraceEvent` contract in `alfred.trace.model`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from alfred.trace.model import EventId


class MandateError(Exception):
    """Raised when a mandate cannot be parsed or fails validation."""


class DeviationType(StrEnum):
    TOOL_NOT_ALLOWED = "tool_not_allowed"
    BUDGET_EXCEEDED = "budget_exceeded"
    FORBIDDEN_ACTION = "forbidden_action"
    ESCALATION_MISSED = "escalation_missed"
    LOOP_DETECTED = "loop_detected"


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    if operator == "==":
        return value == threshold
    raise MandateError(f"Unsupported operator: {operator!r}")


@dataclass(frozen=True, slots=True)
class EscalationRule:
    """A parsed `escalate_when` entry, e.g. `tool_error_rate > 0.10`."""

    metric: str
    operator: str
    threshold: float

    def breached(self, value: float) -> bool:
        return _compare(value, self.operator, self.threshold)


@dataclass(frozen=True, slots=True)
class ForbiddenRule:
    """A structured `forbidden_actions` entry (Brique 9, PLAN.md §12).

    YAML form: `- tool: execute_sql` / `when: args.rows_affected > 1000`.
    Matches a tool call whose `tool.arguments.<arg>` attribute satisfies
    `<operator> <threshold>`.
    """

    tool: str
    arg: str
    operator: str
    threshold: float

    @property
    def when(self) -> str:
        """The rule's condition in its YAML source form."""
        return f"args.{self.arg} {self.operator} {self.threshold}"

    def triggered_by(self, value: float) -> bool:
        return _compare(value, self.operator, self.threshold)


@dataclass(frozen=True, slots=True)
class Mandate:
    agent: str
    allowed_tools: frozenset[str]
    daily_budget_eur: float
    forbidden_actions: tuple[str | ForbiddenRule, ...]
    escalate_when: tuple[EscalationRule, ...]


@dataclass(frozen=True, slots=True)
class Deviation:
    type: DeviationType
    event_ids: tuple[EventId, ...]
    message: str
    details: dict[str, Any] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        if not self.event_ids:
            raise ValueError("Deviation must carry at least one event_id")
