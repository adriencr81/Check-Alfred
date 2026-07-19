"""SQLite persistence for TraceEvents.

See PLAN.md §5 Brique 1 for the contract and tests/test_trace_store.py
for the falsifiable specification.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from types import TracebackType

from alfred.trace.model import EventId, SpanKind, TraceEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trace_events (
    event_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    parent_span_id TEXT,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    attributes TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trace_events_trace_id ON trace_events (trace_id);
"""


_INSERT_SQL = """
INSERT OR REPLACE INTO trace_events
    (event_id, trace_id, parent_span_id, kind, name, start_time, end_time, attributes)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


def _event_to_row(event: TraceEvent) -> tuple[str, str, str | None, str, str, str, str, str]:
    return (
        event.event_id,
        event.trace_id,
        event.parent_span_id,
        event.kind.value,
        event.name,
        event.start_time.isoformat(),
        event.end_time.isoformat(),
        json.dumps(event.attributes),
    )


def _row_to_event(row: sqlite3.Row) -> TraceEvent:
    return TraceEvent(
        event_id=EventId(row["event_id"]),
        trace_id=row["trace_id"],
        parent_span_id=row["parent_span_id"],
        kind=SpanKind(row["kind"]),
        name=row["name"],
        start_time=datetime.fromisoformat(row["start_time"]),
        end_time=datetime.fromisoformat(row["end_time"]),
        attributes=json.loads(row["attributes"]),
    )


class TraceStore:
    """SQLite-backed store, indexed by event_id and trace_id.

    Zero-infra by design: everything fits in a single file. See PLAN.md §10
    (backlog) — do not add another database in v0.x.

    `event_id` (the OTel spanId) is the primary key and is treated as
    globally unique across traces — an accepted v0.1 risk, not a spec
    guarantee. See docs/adr/0001-event-id-global-uniqueness.md.
    """

    def __init__(self, path: Path | str) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def __enter__(self) -> TraceStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def put(self, event: TraceEvent) -> None:
        """Insert or, on a matching `event_id`, blindly replace.

        Re-putting an `event_id` with different field values silently
        overwrites the prior anchor (accepted for v0.1 — see
        docs/adr/0002-brique1-skeleton-fixes.md).
        """
        with self._conn:
            self._conn.execute(_INSERT_SQL, _event_to_row(event))

    def put_many(self, events: Iterable[TraceEvent]) -> None:
        """Insert a batch atomically: one transaction, all rows or none."""
        rows = [_event_to_row(event) for event in events]
        with self._conn:
            self._conn.executemany(_INSERT_SQL, rows)

    def get(self, event_id: EventId) -> TraceEvent | None:
        row = self._conn.execute(
            "SELECT * FROM trace_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return _row_to_event(row) if row is not None else None

    def find_by_trace(self, trace_id: str) -> list[TraceEvent]:
        rows = self._conn.execute(
            "SELECT * FROM trace_events WHERE trace_id = ? ORDER BY start_time, event_id",
            (trace_id,),
        ).fetchall()
        return [_row_to_event(row) for row in rows]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM trace_events").fetchone()
        return int(row[0])

    def close(self) -> None:
        self._conn.close()
