"""Generic OpenTelemetry SpanExporter that writes OTLP JSON files.

This is the "point your OTel traces at Alfred" bridge: any Python app
instrumented with the OTel SDK can add this exporter and drop files that
`alfred watch` ingests directly — no collector, no endpoint. The output
shape matches the OTLP JSON file format (resourceSpans/scopeSpans/spans
with typed key-value attributes).

Requires `opentelemetry-sdk` (example-only dependency).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


def _value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, Sequence):
        return {"arrayValue": {"values": [_value(item) for item in value]}}
    return {"stringValue": str(value)}


def _span_to_json(span: ReadableSpan) -> dict[str, Any]:
    context = span.get_span_context()
    return {
        "traceId": format(context.trace_id, "032x"),
        "spanId": format(context.span_id, "016x"),
        "parentSpanId": format(span.parent.span_id, "016x") if span.parent else "",
        "name": span.name or "",
        "kind": int(span.kind.value) if span.kind is not None else 0,
        "startTimeUnixNano": str(span.start_time or 0),
        "endTimeUnixNano": str(span.end_time or 0),
        "attributes": [
            {"key": key, "value": _value(value)}
            for key, value in (span.attributes or {}).items()
        ],
    }


class OTLPJsonFileExporter(SpanExporter):
    """Buffers spans and writes one OTLP JSON file on shutdown/flush."""

    def __init__(self, path: Path | str, *, service_name: str = "unknown_service") -> None:
        self._path = Path(path)
        self._service_name = service_name
        self._spans: list[dict[str, Any]] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self._spans.extend(_span_to_json(span) for span in spans)
        return SpanExportResult.SUCCESS

    def _write(self) -> None:
        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": _value(self._service_name)}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "otlp_file_exporter"},
                            "spans": list(self._spans),
                        }
                    ],
                }
            ]
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        self._write()
        return True

    def shutdown(self) -> None:
        self._write()
