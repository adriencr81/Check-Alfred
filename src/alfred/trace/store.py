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
    """

    def __init__(self, path: Path | str) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def put(self, event: TraceEvent) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO trace_events
                (event_id, trace_id, parent_span_id, kind, name, start_time, end_time, attributes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.trace_id,
                event.parent_span_id,
                event.kind.value,
                event.name,
                event.start_time.isoformat(),
                event.end_time.isoformat(),
                json.dumps(event.attributes),
            ),
        )
        self._conn.commit()

    def put_many(self, events: Iterable[TraceEvent]) -> None:
        for event in events:
            self.put(event)

    def get(self, event_id: EventId) -> TraceEvent | None:
        row = self._conn.execute(
            "SELECT * FROM trace_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return _row_to_event(row) if row is not None else None

    def find_by_trace(self, trace_id: str) -> list[TraceEvent]:
        rows = self._conn.execute(
            "SELECT * FROM trace_events WHERE trace_id = ?", (trace_id,)
        ).fetchall()
        return [_row_to_event(row) for row in rows]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM trace_events").fetchone()
        return int(row[0])

    def close(self) -> None:
        self._conn.close()
