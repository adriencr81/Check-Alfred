"""SQLite persistence for TraceEvents.

STUB. See PLAN.md §5 Brique 1 for the contract and tests/test_trace_store.py
for the falsifiable specification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from alfred.trace.model import EventId, TraceEvent


class TraceStore:
    """SQLite-backed store, indexed by event_id and trace_id.

    Zero-infra by design: everything fits in a single file. See PLAN.md §10
    (backlog) — do not add another database in v0.x.
    """

    def __init__(self, path: Path | str) -> None:
        raise NotImplementedError("Brique 1: implement TraceStore.__init__")

    def put(self, event: TraceEvent) -> None:
        raise NotImplementedError("Brique 1: implement TraceStore.put")

    def put_many(self, events: Iterable[TraceEvent]) -> None:
        raise NotImplementedError("Brique 1: implement TraceStore.put_many")

    def get(self, event_id: EventId) -> TraceEvent | None:
        raise NotImplementedError("Brique 1: implement TraceStore.get")

    def find_by_trace(self, trace_id: str) -> list[TraceEvent]:
        raise NotImplementedError("Brique 1: implement TraceStore.find_by_trace")

    def count(self) -> int:
        raise NotImplementedError("Brique 1: implement TraceStore.count")

    def close(self) -> None:
        raise NotImplementedError("Brique 1: implement TraceStore.close")
