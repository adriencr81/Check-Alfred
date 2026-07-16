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


@dataclass(frozen=True, slots=True)
class EscalationRule:
    """A parsed `escalate_when` entry, e.g. `tool_error_rate > 0.10`."""

    metric: str
    operator: str
    threshold: float

    def breached(self, value: float) -> bool:
        if self.operator == ">":
            return value > self.threshold
        if self.operator == ">=":
            return value >= self.threshold
        if self.operator == "<":
            return value < self.threshold
        if self.operator == "<=":
            return value <= self.threshold
        if self.operator == "==":
            return value == self.threshold
        raise MandateError(f"Unsupported escalation operator: {self.operator!r}")


@dataclass(frozen=True, slots=True)
class Mandate:
    agent: str
    allowed_tools: frozenset[str]
    daily_budget_eur: float
    forbidden_actions: tuple[str, ...]
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
