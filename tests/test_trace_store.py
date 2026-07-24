"""TraceStore round-trip and query contract.

Uses in-memory SQLite (`:memory:`) to keep tests hermetic and fast.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

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


class _CountingConnection:
    """Delegates to a real connection but tallies `commit()` calls."""

    def __init__(self, conn: object) -> None:
        self._conn = conn
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1
        self._conn.commit()  # type: ignore[attr-defined]

    def __getattr__(self, name: str) -> object:
        return getattr(self._conn, name)


def test_put_many_commits_once_regardless_of_event_count(store: TraceStore) -> None:
    """A whole trace file is one transaction — not one fsync per span."""
    spy = _CountingConnection(store._conn)
    store._conn = spy  # type: ignore[assignment]
    store.put_many([_event("a"), _event("b"), _event("c"), _event("d")])
    assert spy.commits == 1
    assert store.count() == 4


def test_put_many_is_idempotent_on_repeated_id(store: TraceStore) -> None:
    """Re-ingesting a file (watch replay) must not double-count in the batch path."""
    store.put_many([_event("a"), _event("b")])
    store.put_many([_event("a"), _event("b")])
    assert store.count() == 2


def test_put_is_idempotent_on_same_id(store: TraceStore) -> None:
    """Re-ingesting the same span (e.g., watch replay) must not double-count."""
    store.put(_event("evt-1"))
    store.put(_event("evt-1"))
    assert store.count() == 1


def test_find_by_trace_returns_all_events_of_a_trace(store: TraceStore) -> None:
    store.put_many([
        _event("a", "trace-A"),
        _event("b", "trace-A"),
        _event("c", "trace-B"),
    ])
    got = store.find_by_trace("trace-A")
    assert {e.event_id for e in got} == {"a", "b"}


def test_find_by_trace_orders_by_start_time(store: TraceStore) -> None:
    store.put_many([
        _event("c", "trace-A", start_time=datetime(2026, 8, 30, 12, 0, 2, tzinfo=UTC)),
        _event("a", "trace-A", start_time=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)),
        _event("b", "trace-A", start_time=datetime(2026, 8, 30, 12, 0, 1, tzinfo=UTC)),
    ])
    got = store.find_by_trace("trace-A")
    assert [e.event_id for e in got] == ["a", "b", "c"]


def _at(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 9, 0, 0, tzinfo=UTC)


def test_find_by_date_range_is_inclusive_on_both_bounds(store: TraceStore) -> None:
    store.put_many([
        _event("d23", start_time=_at(date(2026, 8, 23))),
        _event("d26", start_time=_at(date(2026, 8, 26))),
        _event("d29", start_time=_at(date(2026, 8, 29))),
    ])
    got = store.find_by_date_range(date(2026, 8, 23), date(2026, 8, 29))
    assert {e.event_id for e in got} == {"d23", "d26", "d29"}


def test_find_by_date_range_excludes_days_outside_the_window(store: TraceStore) -> None:
    store.put_many([
        _event("before", start_time=_at(date(2026, 8, 22))),
        _event("inside", start_time=_at(date(2026, 8, 25))),
        _event("after", start_time=_at(date(2026, 8, 30))),
    ])
    got = store.find_by_date_range(date(2026, 8, 23), date(2026, 8, 29))
    assert {e.event_id for e in got} == {"inside"}


def test_attributes_survive_roundtrip(store: TraceStore) -> None:
    """Attribute values must round-trip verbatim (used for cost computation)."""
    original = _event("evt-x")
    store.put(original)
    got = store.get(EventId("evt-x"))
    assert got is not None
    assert got.attributes == original.attributes
