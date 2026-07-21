"""OTLP JSON → TraceEvent contract.

The fixture `otlp_sample.json` contains exactly 3 spans:
  1. `00f067aa0ba902b7` — agent task
  2. `a1b2c3d4e5f60718` — chat call to gpt-4o-mini
  3. `b2c3d4e5f6071829` — tool call issue_refund
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alfred.trace.ingest import ingest_otlp_file, ingest_otlp_json
from alfred.trace.model import SpanKind, TraceIngestionError


def test_ingest_returns_all_spans(otlp_sample_payload: dict[str, object]) -> None:
    events = ingest_otlp_json(otlp_sample_payload)
    assert len(events) == 3


def test_ingest_preserves_span_id(otlp_sample_payload: dict[str, object]) -> None:
    events = ingest_otlp_json(otlp_sample_payload)
    expected = {"00f067aa0ba902b7", "a1b2c3d4e5f60718", "b2c3d4e5f6071829"}
    assert {e.event_id for e in events} == expected


def test_ingest_preserves_trace_id(otlp_sample_payload: dict[str, object]) -> None:
    events = ingest_otlp_json(otlp_sample_payload)
    assert all(e.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736" for e in events)


def test_ingest_normalizes_timestamps_utc(otlp_sample_payload: dict[str, object]) -> None:
    """OTLP nanosecond timestamps must land as UTC datetimes."""
    events = {e.event_id: e for e in ingest_otlp_json(otlp_sample_payload)}
    root = events["00f067aa0ba902b7"]
    assert root.start_time == datetime(2026, 8, 29, 21, 0, 0, tzinfo=UTC)
    assert root.end_time == datetime(2026, 8, 29, 21, 0, 12, tzinfo=UTC)


def test_ingest_extracts_gen_ai_usage(otlp_sample_payload: dict[str, object]) -> None:
    """Downstream cost accounting depends on gen_ai.usage.* being extractable."""
    events = {e.event_id: e for e in ingest_otlp_json(otlp_sample_payload)}
    chat = events["a1b2c3d4e5f60718"]
    assert chat.attributes["gen_ai.usage.input_tokens"] == 1284
    assert chat.attributes["gen_ai.usage.output_tokens"] == 192
    assert chat.attributes["gen_ai.request.model"] == "gpt-4o-mini"


def test_ingest_extracts_parent_span(otlp_sample_payload: dict[str, object]) -> None:
    events = {e.event_id: e for e in ingest_otlp_json(otlp_sample_payload)}
    assert events["00f067aa0ba902b7"].parent_span_id is None
    assert events["a1b2c3d4e5f60718"].parent_span_id == "00f067aa0ba902b7"


def test_ingest_kind_is_derived_from_gen_ai_operation_name(
    otlp_sample_payload: dict[str, object],
) -> None:
    """`.kind` must be inferred from `gen_ai.operation.name` (OTel GenAI semconv),
    not from ad-hoc attribute-key prefixes — see docs/adr/0003."""
    events = {e.event_id: e for e in ingest_otlp_json(otlp_sample_payload)}
    assert events["00f067aa0ba902b7"].kind == SpanKind.AGENT_TASK
    assert events["a1b2c3d4e5f60718"].kind == SpanKind.LLM_CALL
    assert events["b2c3d4e5f6071829"].kind == SpanKind.TOOL_CALL


def test_ingest_kind_is_unknown_without_operation_name() -> None:
    payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "t",
                                "spanId": "s",
                                "parentSpanId": "",
                                "name": "some.unlabelled.span",
                                "startTimeUnixNano": "1788037200000000000",
                                "endTimeUnixNano": "1788037201000000000",
                                "attributes": [],
                            }
                        ]
                    }
                ]
            }
        ]
    }
    events = ingest_otlp_json(payload)
    assert events[0].kind == SpanKind.UNKNOWN


def test_ingest_malformed_raises() -> None:
    """Missing required fields must fail loudly with the typed error."""
    with pytest.raises(TraceIngestionError):
        ingest_otlp_json({"garbage": True})


def test_ingest_file_delegates(otlp_sample_path: Path) -> None:
    """Reading from disk must produce the same events as parsing the dict.

    The fixture is a pretty-printed single OTLP object (newlines *inside* one
    payload); it must stay a single payload, never be split line by line.
    """
    from_file = ingest_otlp_file(otlp_sample_path)
    assert len(from_file) == 3


# --- Brique 10: real-world ingestion (OTel Collector bridge, standard semconv) ---


def _attr(key: str, value: dict[str, object]) -> dict[str, object]:
    return {"key": key, "value": value}


def _span(
    span_id: str, operation: str, *, extra: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
        "spanId": span_id,
        "parentSpanId": "",
        "name": f"span.{operation}",
        "startTimeUnixNano": "1788037200000000000",
        "endTimeUnixNano": "1788037201000000000",
        "attributes": [_attr("gen_ai.operation.name", {"stringValue": operation}), *(extra or [])],
    }


def _payload(*spans: dict[str, object]) -> dict[str, object]:
    return {"resourceSpans": [{"scopeSpans": [{"spans": list(spans)}]}]}


def test_ingest_ndjson_lines(tmp_path: Path) -> None:
    """The OTel Collector file exporter emits one OTLP payload per line (NDJSON)."""
    lines = [
        json.dumps(_payload(_span("00f067aa0ba902b7", "invoke_agent"))),
        json.dumps(_payload(_span("a1b2c3d4e5f60718", "chat"))),
        json.dumps(_payload(_span("b2c3d4e5f6071829", "execute_tool"))),
    ]
    path = tmp_path / "collector.ndjson"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    events = ingest_otlp_file(path)
    assert {e.event_id for e in events} == {
        "00f067aa0ba902b7",
        "a1b2c3d4e5f60718",
        "b2c3d4e5f6071829",
    }


def test_status_code_error_maps_to_tool_error() -> None:
    """A standard OTLP error status becomes the tool.result.status the engine reads."""
    span = _span("s", "execute_tool", extra=[_attr("gen_ai.tool.name", {"stringValue": "run_sql"})])
    span["status"] = {"code": "STATUS_CODE_ERROR"}
    events = ingest_otlp_json(_payload(span))
    assert events[0].attributes["tool.result.status"] == "error"


def test_status_code_error_accepts_integer_code() -> None:
    """The Collector may serialize the status code as the enum's integer value."""
    span = _span("s", "execute_tool")
    span["status"] = {"code": 2}
    events = ingest_otlp_json(_payload(span))
    assert events[0].attributes["tool.result.status"] == "error"


def test_status_code_error_does_not_overwrite_recorded_status() -> None:
    """An explicit tool.result.status is never clobbered by the status mapping."""
    span = _span("s", "execute_tool", extra=[_attr("tool.result.status", {"stringValue": "ok"})])
    span["status"] = {"code": "STATUS_CODE_ERROR"}
    events = ingest_otlp_json(_payload(span))
    assert events[0].attributes["tool.result.status"] == "ok"


def test_tool_call_arguments_json_parsed() -> None:
    """`gen_ai.tool.call.arguments` (a JSON string) flattens to tool.arguments.<key>."""
    args = json.dumps({"amount_eur": 250.0, "order_id": "ORD-1", "urgent": True})
    span = _span(
        "s", "execute_tool", extra=[_attr("gen_ai.tool.call.arguments", {"stringValue": args})]
    )
    attributes = ingest_otlp_json(_payload(span))[0].attributes
    assert attributes["tool.arguments.amount_eur"] == 250.0
    assert attributes["tool.arguments.order_id"] == "ORD-1"
    assert attributes["tool.arguments.urgent"] is True


def test_tool_call_arguments_json_does_not_overwrite_native() -> None:
    """A native tool.arguments.<key> wins over the same key in the JSON blob."""
    args = json.dumps({"amount_eur": 999.0})
    span = _span(
        "s",
        "execute_tool",
        extra=[
            _attr("tool.arguments.amount_eur", {"doubleValue": 42.5}),
            _attr("gen_ai.tool.call.arguments", {"stringValue": args}),
        ],
    )
    attributes = ingest_otlp_json(_payload(span))[0].attributes
    assert attributes["tool.arguments.amount_eur"] == 42.5


def test_malformed_ndjson_raises(tmp_path: Path) -> None:
    """An invalid NDJSON line fails loudly, naming the line number."""
    good = json.dumps(_payload(_span("s", "invoke_agent")))
    path = tmp_path / "bad.ndjson"
    path.write_text(good + "\n{ not json\n", encoding="utf-8")
    with pytest.raises(TraceIngestionError, match="line 2"):
        ingest_otlp_file(path)
