"""SQLite persistence for TraceEvents.

See PLAN.md §5 Brique 1 for the contract and tests/test_trace_store.py
for the falsifiable specification.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from alfred._fs import restrict
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
CREATE INDEX IF NOT EXISTS idx_trace_events_start_time ON trace_events (start_time);
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


# Append-only: an `event_id` already stored is never overwritten (ADR 0026
# decision 4). The caller learns which events were refused, so a rewrite is
# reported rather than silently applied.
_INSERT_SQL = """
    INSERT OR IGNORE INTO trace_events
        (event_id, trace_id, parent_span_id, kind, name, start_time, end_time, attributes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


_ROW_COLUMNS = (
    "event_id, trace_id, parent_span_id, kind, name, start_time, end_time, attributes"
)


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


class TraceStore:
    """SQLite-backed store, indexed by event_id and trace_id.

    Zero-infra by design: everything fits in a single file. See PLAN.md §10
    (backlog) — do not add another database in v0.x.

    `event_id` (the OTel spanId) is the primary key and is treated as
    globally unique across traces — an accepted v0.1 risk, not a spec
    guarantee. See docs/adr/0001-event-id-global-uniqueness.md.

    Append-only since docs/adr/0026-report-and-evidence-integrity.md: a stored
    event is never overwritten, so the agent cannot rewrite an anchor a past
    digest already quoted.
    """

    def __init__(self, path: Path | str) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        # The rows hold tool arguments — whatever the agent handled. sqlite3
        # creates the file with the process umask, typically world-readable
        # (ADR 0025 decision 7).
        restrict(Path(path))

    def put(self, event: TraceEvent) -> list[TraceEvent]:
        """Store `event` unless its `event_id` is already taken.

        Returns the event in a list when it conflicts with a *different* event
        already stored — the stored one wins. Re-putting an identical event
        stays a no-op, which is what makes a replayed ingest idempotent.
        """
        return self.put_many([event])

    def put_many(self, events: Iterable[TraceEvent]) -> list[TraceEvent]:
        """Insert every new event in one `executemany` and a single commit.

        A whole trace file is one transaction — no per-event `fsync` — and the
        batch is atomic: a failure rolls back the pass rather than leaving a
        partial ingest.

        Returns the events refused because their `event_id` is already stored
        with *different* content. `event_id` is the spanId the audited agent
        chose, so replacing on conflict let it rewrite an anchor a past digest
        already quoted (ADR 0026 decision 4). An identical re-put is not a
        conflict; the honest events of the batch are stored either way.
        """
        batch = list(events)
        stored = self._existing(event.event_id for event in batch)
        conflicts = [
            event
            for event in batch
            if event.event_id in stored and stored[event.event_id] != _event_to_row(event)
        ]
        self._conn.executemany(_INSERT_SQL, [_event_to_row(event) for event in batch])
        self._conn.commit()
        return conflicts

    def _existing(self, event_ids: Iterable[EventId]) -> dict[EventId, tuple[Any, ...]]:
        """The stored rows for `event_ids`, keyed by id, in one query."""
        ids = list(dict.fromkeys(event_ids))
        if not ids:
            return {}
        placeholders = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT {_ROW_COLUMNS} FROM trace_events WHERE event_id IN ({placeholders})",  # noqa: S608
            ids,
        ).fetchall()
        return {EventId(row[0]): tuple(row) for row in rows}

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

    def find_by_date_range(self, start: date, end: date) -> list[TraceEvent]:
        """Events whose local `start_time` date falls in `[start, end]` inclusive.

        Compares the `YYYY-MM-DD` prefix of the stored ISO timestamp, so the
        result is robust to the timezone suffix and matches how `watch_once`
        groups events by `start_time.date()`. Used to load the rolling baseline
        window (F3, docs/adr/0019).
        """
        rows = self._conn.execute(
            "SELECT * FROM trace_events "
            "WHERE substr(start_time, 1, 10) BETWEEN ? AND ? "
            "ORDER BY start_time, event_id",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [_row_to_event(row) for row in rows]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM trace_events").fetchone()
        return int(row[0])

    def close(self) -> None:
        self._conn.close()
