"""Normalized trace event model.

Invariant (see PLAN.md §3): every TraceEvent has a stable, unique `event_id`
that will serve as the anchor for every downstream report line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, NewType

EventId = NewType("EventId", str)


class SpanKind(str, Enum):
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    AGENT_TASK = "agent_task"
    UNKNOWN = "unknown"


class TraceIngestionError(Exception):
    """Raised when an incoming trace payload cannot be normalized."""


@dataclass(frozen=True, slots=True)
class TraceEvent:
    event_id: EventId
    trace_id: str
    parent_span_id: str | None
    kind: SpanKind
    name: str
    start_time: datetime
    end_time: datetime
    attributes: dict[str, Any] = field(default_factory=dict)
