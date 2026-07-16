"""Digest model — every Line is anchored to trace event IDs.

Invariant (see PLAN.md §3): a `Digest` is a typed structure where each
`Line`'s `sources` is non-empty — a line with no anchor is a bug, not data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from alfred.mandate.model import Deviation
from alfred.trace.model import EventId


class LineKind(StrEnum):
    TASKS_COMPLETED = "tasks_completed"
    COST_EUR = "cost_eur"
    ESCALATIONS = "escalations"


@dataclass(frozen=True, slots=True)
class Line:
    kind: LineKind
    value: float
    sources: tuple[EventId, ...]

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError("Line must carry at least one event_id")


@dataclass(frozen=True, slots=True)
class Digest:
    agent: str
    date: date
    lines: tuple[Line, ...]
    deviations: tuple[Deviation, ...] = ()
