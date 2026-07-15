"""TraceEvent invariants — the anchor contract.

Every event must be uniquely addressable by its `event_id`. Every downstream
report line will cite one or more `event_id`s from the store, so the identity
of these objects is load-bearing (PLAN.md §3).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from alfred.trace.model import EventId, SpanKind, TraceEvent


def _sample_event(event_id: str = "abc123") -> TraceEvent:
    return TraceEvent(
        event_id=EventId(event_id),
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        parent_span_id=None,
        kind=SpanKind.LLM_CALL,
        name="chat gpt-4o-mini",
        start_time=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 12, 0, 3, tzinfo=UTC),
        attributes={"gen_ai.system": "openai"},
    )


def test_event_is_immutable() -> None:
    """Mutating an event would break the anchoring guarantee — reject it."""
    event = _sample_event()
    with pytest.raises(FrozenInstanceError):
        event.event_id = EventId("other")  # type: ignore[misc]


def test_events_with_same_id_are_equal() -> None:
    """Equality by value: two events with the same fields must compare equal."""
    assert _sample_event() == _sample_event()


def test_events_with_different_ids_are_not_equal() -> None:
    assert _sample_event("a") != _sample_event("b")


def test_event_is_hashable() -> None:
    """Needed to use events in sets and dict keys (deduplication in the store)."""
    assert hash(_sample_event()) == hash(_sample_event())
    assert {_sample_event(), _sample_event()} == {_sample_event()}
