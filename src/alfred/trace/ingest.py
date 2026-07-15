"""OTLP JSON → list[TraceEvent].

STUB. To implement in the first Claude Code session on Alfred.
See PLAN.md §5 Brique 1 for the contract, and tests/test_trace_ingest.py
for the falsifiable specification.
"""

from __future__ import annotations

from pathlib import Path

from alfred.trace.model import TraceEvent


def ingest_otlp_json(payload: dict[str, object]) -> list[TraceEvent]:
    """Parse an OTLP JSON payload into normalized TraceEvents.

    Contract (must hold for every returned event):
    - `event_id` == the span's `spanId` (hex, lowercased).
    - Timestamps are UTC datetimes derived from `startTimeUnixNano`/`endTimeUnixNano`.
    - `attributes` is a flat `dict[str, Any]`, un-nested from OTLP's list-of-KV format.
    - Raises `TraceIngestionError` on malformed input (missing required fields).
    """
    raise NotImplementedError("Brique 1: implement ingest_otlp_json")


def ingest_otlp_file(path: Path) -> list[TraceEvent]:
    """Read an OTLP JSON file from disk and delegate to ingest_otlp_json."""
    raise NotImplementedError("Brique 1: implement ingest_otlp_file")
