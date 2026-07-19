"""OTLP JSON → list[TraceEvent].

See PLAN.md §5 Brique 1 for the contract, and tests/test_trace_ingest.py
for the falsifiable specification.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from alfred.trace.model import EventId, SpanKind, TraceEvent, TraceIngestionError


def _value(value: dict[str, Any]) -> Any:
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return value["doubleValue"]
    if "boolValue" in value:
        return value["boolValue"]
    raise TraceIngestionError(f"Unsupported OTLP attribute value: {value!r}")


def _attributes(raw: list[dict[str, Any]]) -> dict[str, Any]:
    return {kv["key"]: _value(kv["value"]) for kv in raw}


_OPERATION_KIND = {
    "chat": SpanKind.LLM_CALL,
    "text_completion": SpanKind.LLM_CALL,
    "embeddings": SpanKind.LLM_CALL,
    "execute_tool": SpanKind.TOOL_CALL,
    "invoke_agent": SpanKind.AGENT_TASK,
    "create_agent": SpanKind.AGENT_TASK,
}


def _kind(attributes: dict[str, Any]) -> SpanKind:
    """Discriminate SpanKind from `gen_ai.operation.name` (OTel GenAI semconv).

    See docs/adr/0003-span-kind-classification.md: unlike a prefix scan over
    `gen_ai.*`/`tool.*`/`agent.*` attribute keys, the semconv already carries
    tool and agent spans under the `gen_ai.*` namespace, so the operation
    name is the only reliable discriminator.
    """
    operation = attributes.get("gen_ai.operation.name")
    if isinstance(operation, str) and operation in _OPERATION_KIND:
        return _OPERATION_KIND[operation]
    return SpanKind.UNKNOWN


def _timestamp(nanos: str) -> datetime:
    seconds, nanoseconds = divmod(int(nanos), 1_000_000_000)
    return datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=nanoseconds // 1_000)


def _span_to_event(span: dict[str, Any]) -> TraceEvent:
    attributes = _attributes(span.get("attributes", []))
    parent_span_id = span.get("parentSpanId") or None
    return TraceEvent(
        event_id=EventId(str(span["spanId"]).lower()),
        trace_id=str(span["traceId"]).lower(),
        parent_span_id=str(parent_span_id).lower() if parent_span_id is not None else None,
        kind=_kind(attributes),
        name=span["name"],
        start_time=_timestamp(span["startTimeUnixNano"]),
        end_time=_timestamp(span["endTimeUnixNano"]),
        attributes=attributes,
    )


def ingest_otlp_json(payload: dict[str, object]) -> list[TraceEvent]:
    """Parse an OTLP JSON payload into normalized TraceEvents.

    Contract (must hold for every returned event):
    - `event_id` == the span's `spanId` (hex, lowercased).
    - Timestamps are UTC datetimes derived from `startTimeUnixNano`/`endTimeUnixNano`.
    - `attributes` is a flat `dict[str, Any]`, un-nested from OTLP's list-of-KV format.
    - Raises `TraceIngestionError` on malformed input (missing required fields).
    """
    try:
        resource_spans = cast("list[dict[str, Any]]", payload["resourceSpans"])
        events = [
            _span_to_event(span)
            for resource_span in resource_spans
            for scope_span in resource_span["scopeSpans"]
            for span in scope_span["spans"]
        ]
    except (KeyError, TypeError) as exc:
        raise TraceIngestionError(f"Malformed OTLP payload: {exc}") from exc
    return events


def ingest_otlp_file(path: Path) -> list[TraceEvent]:
    """Read an OTLP JSON file from disk and delegate to ingest_otlp_json."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ingest_otlp_json(payload)
