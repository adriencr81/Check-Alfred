"""Normalized trace event model.

Invariant (see PLAN.md §3): every TraceEvent has a stable, unique `event_id`
that will serve as the anchor for every downstream report line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, NewType

EventId = NewType("EventId", str)


class SpanKind(StrEnum):
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    AGENT_TASK = "agent_task"
    UNKNOWN = "unknown"


class TraceIngestionError(Exception):
    """Raised when an incoming trace payload cannot be normalized."""


TOOL_STATUS_ATTR = "tool.result.status"


@dataclass(frozen=True, slots=True)
class TraceEvent:
    event_id: EventId
    trace_id: str
    parent_span_id: str | None
    kind: SpanKind
    name: str
    start_time: datetime
    end_time: datetime
    attributes: dict[str, Any] = field(default_factory=dict, hash=False)


def is_tool_error(event: TraceEvent) -> bool:
    """True when the event records a tool call that failed.

    Single source of truth: the mandate engine (`tool_error_rate`) and the
    report's Failed tool calls line must agree on what counts as a failure, or
    a digest contradicts its own deviations.
    """
    status = event.attributes.get(TOOL_STATUS_ATTR)
    return isinstance(status, str) and status.lower() != "ok"
