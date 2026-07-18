"""OTLP JSON → list[TraceEvent].

See PLAN.md §5 Brique 1 for the contract, and tests/test_trace_ingest.py
for the falsifiable specification.
"""

from __future__ import annotations

import ast
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
    if "arrayValue" in value:
        return [_value(item) for item in value["arrayValue"].get("values", [])]
    raise TraceIngestionError(f"Unsupported OTLP attribute value: {value!r}")


def _attributes(raw: list[dict[str, Any]]) -> dict[str, Any]:
    return {kv["key"]: _value(kv["value"]) for kv in raw}


_OPERATION_KIND = {
    "chat": SpanKind.LLM_CALL,
    "text_completion": SpanKind.LLM_CALL,
    "embeddings": SpanKind.LLM_CALL,
    "execute_tool": SpanKind.TOOL_CALL,
    "invoke_agent": SpanKind.AGENT_TASK,
    # "create_agent" (agent/graph construction) is deliberately NOT an
    # AGENT_TASK: it would count as a completed task in the digest.
    # ADR 0011 supersedes the ADR 0003 mapping on this point.
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
_THIRD_PARTY_STATUS_ATTR = "gen_ai.task.status"
_TOOL_ARGS_PREFIX = "tool.arguments."
_THIRD_PARTY_ARGS_ATTR = "gen_ai.tool.call.arguments"
# Wrapper keys some instrumentors (OpenLLMetry) put around the actual tool
# arguments inside gen_ai.tool.call.arguments.
_ARGS_WRAPPER_KEYS = frozenset({"tags", "metadata"})


def _parse_mapping(text: str) -> dict[str, Any] | None:
    """Best-effort parse of a JSON object or Python-repr dict; None on failure."""
    for parse in (json.loads, ast.literal_eval):
        try:
            parsed = parse(text)
        except (ValueError, SyntaxError):
            continue
        if isinstance(parsed, dict):
            return cast("dict[str, Any]", parsed)
    return None


def _third_party_tool_args(raw: str) -> dict[str, Any]:
    """Extract the actual tool arguments from an instrumentor's payload.

    OpenLLMetry emits `{"input_str": "<python repr of args>", "tags": …,
    "metadata": …}`; other emitters put the argument mapping directly in
    the JSON. Returns only scalar-valued arguments; empty dict on failure.
    """
    parsed = _parse_mapping(raw)
    if parsed is None:
        return {}
    inner = parsed.get("input_str")
    if isinstance(inner, str):
        parsed = _parse_mapping(inner) or {}
    arguments = {
        key: value
        for key, value in parsed.items()
        if key not in _ARGS_WRAPPER_KEYS and isinstance(value, str | int | float | bool)
    }
    return arguments


def _normalize_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Map third-party GenAI semconv variants onto Alfred's canonical keys.

    This is the adaptation layer PLAN.md §9 anticipated ("isoler l'ingest
    derrière une couche d'adaptation"): normalization happens once, at the
    ingestion boundary, so the mandate engine and report builder only ever
    read canonical attributes. Canonical keys already present are never
    overwritten. See docs/adr/0011-brique8-langgraph-adapter.md.
    """
    if attributes.get("gen_ai.operation.name") != "execute_tool":
        return attributes
    status = attributes.get(_THIRD_PARTY_STATUS_ATTR)
    if _TOOL_STATUS_ATTR not in attributes and isinstance(status, str):
        attributes[_TOOL_STATUS_ATTR] = "ok" if status == "success" else "error"
    raw_args = attributes.get(_THIRD_PARTY_ARGS_ATTR)
    has_canonical_args = any(key.startswith(_TOOL_ARGS_PREFIX) for key in attributes)
    if not has_canonical_args and isinstance(raw_args, str):
        for key, value in _third_party_tool_args(raw_args).items():
            attributes[f"{_TOOL_ARGS_PREFIX}{key}"] = value
    return attributes


def _timestamp(nanos: str) -> datetime:
    seconds, nanoseconds = divmod(int(nanos), 1_000_000_000)
    return datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=nanoseconds // 1_000)


def _span_to_event(span: dict[str, Any]) -> TraceEvent:
    attributes = _normalize_attributes(_attributes(span.get("attributes", [])))
    parent_span_id = span.get("parentSpanId") or None
    return TraceEvent(
        event_id=EventId(span["spanId"]),
        trace_id=span["traceId"],
        parent_span_id=parent_span_id,
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
