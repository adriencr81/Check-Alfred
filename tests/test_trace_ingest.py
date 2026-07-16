"""OTLP JSON → TraceEvent contract.

The fixture `otlp_sample.json` contains exactly 3 spans:
  1. `00f067aa0ba902b7` — agent task
  2. `a1b2c3d4e5f60718` — chat call to gpt-4o-mini
  3. `b2c3d4e5f6071829` — tool call issue_refund
"""

from __future__ import annotations

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
    """Reading from disk must produce the same events as parsing the dict."""
    from_file = ingest_otlp_file(otlp_sample_path)
    assert len(from_file) == 3
