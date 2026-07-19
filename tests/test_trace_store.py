"""TraceStore round-trip and query contract.

Uses in-memory SQLite (`:memory:`) to keep tests hermetic and fast.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alfred.trace.model import EventId, SpanKind, TraceEvent
from alfred.trace.store import TraceStore


def _event(
    event_id: str,
    trace_id: str = "trace-1",
    start_time: datetime = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC),
) -> TraceEvent:
    return TraceEvent(
        event_id=EventId(event_id),
        trace_id=trace_id,
        parent_span_id=None,
        kind=SpanKind.LLM_CALL,
        name="chat",
        start_time=start_time,
        end_time=start_time,
        attributes={"gen_ai.usage.output_tokens": 42},
    )


@pytest.fixture
def store() -> TraceStore:
    return TraceStore(":memory:")


def test_put_then_get_roundtrip(store: TraceStore) -> None:
    e = _event("evt-1")
    store.put(e)
    got = store.get(EventId("evt-1"))
    assert got == e


def test_get_missing_returns_none(store: TraceStore) -> None:
    assert store.get(EventId("nope")) is None


def test_put_many_and_count(store: TraceStore) -> None:
    store.put_many([_event("a"), _event("b"), _event("c")])
    assert store.count() == 3


def test_put_is_idempotent_on_same_id(store: TraceStore) -> None:
    """Re-ingesting the same span (e.g., watch replay) must not double-count."""
    store.put(_event("evt-1"))
    store.put(_event("evt-1"))
    assert store.count() == 1


def test_find_by_trace_returns_all_events_of_a_trace(store: TraceStore) -> None:
    store.put_many(
        [
            _event("a", "trace-A"),
            _event("b", "trace-A"),
            _event("c", "trace-B"),
        ]
    )
    got = store.find_by_trace("trace-A")
    assert {e.event_id for e in got} == {"a", "b"}


def test_find_by_trace_orders_by_start_time(store: TraceStore) -> None:
    store.put_many(
        [
            _event("c", "trace-A", start_time=datetime(2026, 8, 30, 12, 0, 2, tzinfo=UTC)),
            _event("a", "trace-A", start_time=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)),
            _event("b", "trace-A", start_time=datetime(2026, 8, 30, 12, 0, 1, tzinfo=UTC)),
        ]
    )
    got = store.find_by_trace("trace-A")
    assert [e.event_id for e in got] == ["a", "b", "c"]


def test_put_many_is_atomic_on_bad_event(store: TraceStore) -> None:
    """B5 regression: a batch with one unserializable event leaves zero rows —
    no partially-ingested batch on failure."""
    bad = _event("bad")
    bad.attributes["unserializable"] = object()
    with pytest.raises(TypeError):
        store.put_many([_event("a"), bad, _event("c")])
    assert store.count() == 0


def test_store_is_a_context_manager() -> None:
    with TraceStore(":memory:") as store:
        store.put(_event("evt-1"))
        assert store.count() == 1


def test_attributes_survive_roundtrip(store: TraceStore) -> None:
    """Attribute values must round-trip verbatim (used for cost computation)."""
    original = _event("evt-x")
    store.put(original)
    got = store.get(EventId("evt-x"))
    assert got is not None
    assert got.attributes == original.attributes
