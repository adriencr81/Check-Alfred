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


_TOOL_STATUS_ATTR = "tool.result.status"
_TOOL_ARGS_JSON_ATTR = "gen_ai.tool.call.arguments"
_TOOL_ARGS_PREFIX = "tool.arguments."


def _is_status_error(span: dict[str, Any]) -> bool:
    """OTLP span status carries ERROR as the enum name or its integer value (2)."""
    status = span.get("status")
    if not isinstance(status, dict):
        return False
    return status.get("code") in ("STATUS_CODE_ERROR", 2)


def _adapt_semconv(span: dict[str, Any], kind: SpanKind, attributes: dict[str, Any]) -> None:
    """Map standard OTel tool spans onto the home keys the mandate engine reads.

    Adaptation layer per PLAN.md §9 / ADR 0013 decision 5: the engine keeps
    its vocabulary, so a trace with only standard semconv (no `tool.result.status`,
    arguments packed in one JSON blob) still yields tool errors and per-argument
    values. Home keys always win — an explicit attribute is never overwritten.
    """
    if kind is not SpanKind.TOOL_CALL:
        return
    if _TOOL_STATUS_ATTR not in attributes and _is_status_error(span):
        attributes[_TOOL_STATUS_ATTR] = "error"
    raw_arguments = attributes.get(_TOOL_ARGS_JSON_ATTR)
    if isinstance(raw_arguments, str):
        _flatten_tool_arguments(raw_arguments, attributes)


def _flatten_tool_arguments(raw: str, attributes: dict[str, Any]) -> None:
    """`gen_ai.tool.call.arguments` (JSON object string) → `tool.arguments.<key>`."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return  # a malformed blob is left as-is, not fatal to the whole trace
    if not isinstance(parsed, dict):
        return
    for key, value in parsed.items():
        if isinstance(value, str | int | float):  # scalars only; bool is an int
            attributes.setdefault(f"{_TOOL_ARGS_PREFIX}{key}", value)


def _timestamp(nanos: str) -> datetime:
    seconds, nanoseconds = divmod(int(nanos), 1_000_000_000)
    return datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=nanoseconds // 1_000)


def _span_to_event(span: dict[str, Any]) -> TraceEvent:
    attributes = _attributes(span.get("attributes", []))
    kind = _kind(attributes)
    _adapt_semconv(span, kind, attributes)
    parent_span_id = span.get("parentSpanId") or None
    return TraceEvent(
        event_id=EventId(span["spanId"]),
        trace_id=span["traceId"],
        parent_span_id=parent_span_id,
        kind=kind,
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
    """Read one or more OTLP JSON payloads from a file into TraceEvents.

    Decodes the file as a stream of JSON values, so every real shape lands in
    one path: a single payload (pretty-printed over many lines), the
    newline-delimited payloads the OTel Collector file exporter writes (so the
    `agent → Collector → alfred watch` bridge works), or several concatenated.
    A malformed value raises `TraceIngestionError` naming the line it starts on.
    """
    text = Path(path).read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    events: list[TraceEvent] = []
    index, length = 0, len(text)
    while (index := _skip_whitespace(text, index)) < length:
        try:
            payload, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError as exc:
            raise TraceIngestionError(f"Malformed OTLP JSON at line {exc.lineno}: {exc}") from exc
        events.extend(ingest_otlp_json(payload))
    return events


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index
