"""Falsifiable specification for ingestion-boundary normalization (Brique 8).

`tests/fixtures/langgraph_otlp_sample.json` is NOT hand-written: it was
captured from a real LangGraph agent instrumented by
opentelemetry-instrumentation-langchain (OpenLLMetry) and exported through
`examples/agents/langgraph_refund_bot/otlp_file.py`. These tests pin the
adaptation layer PLAN.md §9 anticipated: third-party GenAI semconv variants
are normalized at the ingestion boundary onto the canonical attributes the
mandate engine and report builder read.

See docs/adr/0011-brique8-langgraph-adapter.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from alfred.mandate.engine import evaluate
from alfred.mandate.model import DeviationType
from alfred.mandate.yaml_io import load_mandate
from alfred.trace.ingest import ingest_otlp_json
from alfred.trace.model import SpanKind, TraceEvent

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "langgraph_otlp_sample.json"
MANDATE_PATH = REPO_ROOT / "examples" / "mandates" / "refund-bot.yaml"


def _fixture_events() -> list[TraceEvent]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return ingest_otlp_json(payload)


def _span(
    attributes: list[dict[str, object]],
    *,
    span_id: str = "aaaaaaaaaaaaaaaa",
    trace_id: str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
) -> dict[str, object]:
    return {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": span_id,
                                "parentSpanId": "",
                                "name": "test",
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000001000000000",
                                "attributes": attributes,
                            }
                        ]
                    }
                ]
            }
        ]
    }


def _attr(key: str, value: str) -> dict[str, object]:
    return {"key": key, "value": {"stringValue": value}}


def test_langgraph_fixture_ingests_with_expected_kinds() -> None:
    events = _fixture_events()
    kinds = {event.kind for event in events}
    assert SpanKind.AGENT_TASK in kinds
    assert SpanKind.LLM_CALL in kinds
    assert SpanKind.TOOL_CALL in kinds
    assert len({event.event_id for event in events}) == len(events)


def test_task_status_success_normalizes_to_ok() -> None:
    events = _fixture_events()
    refund = next(
        event
        for event in events
        if event.attributes.get("gen_ai.tool.name") == "issue_refund"
    )
    assert refund.attributes["gen_ai.task.status"] == "success"
    assert refund.attributes["tool.result.status"] == "ok"


def test_task_status_failure_normalizes_to_error() -> None:
    events = _fixture_events()
    failing = next(
        event
        for event in events
        if event.attributes.get("gen_ai.tool.name") == "charge_customer"
    )
    assert failing.attributes["gen_ai.task.status"] == "failure"
    assert failing.attributes["tool.result.status"] == "error"


def test_tool_arguments_promoted_from_instrumentor_payload() -> None:
    events = _fixture_events()
    refund = next(
        event
        for event in events
        if event.attributes.get("gen_ai.tool.name") == "issue_refund"
    )
    assert refund.attributes["tool.arguments.amount_eur"] == 250.0


def test_langgraph_trace_triggers_forbidden_action_under_stock_mandate() -> None:
    """The test that embodies the brick: a third-party-instrumented agent's
    over-limit refund is caught by the unmodified refund-bot mandate."""
    events = _fixture_events()
    refund = next(
        event
        for event in events
        if event.attributes.get("gen_ai.tool.name") == "issue_refund"
    )
    trace_events = [event for event in events if event.trace_id == refund.trace_id]
    mandate = load_mandate(MANDATE_PATH)
    deviations = evaluate(mandate, trace_events)
    forbidden = [d for d in deviations if d.type is DeviationType.FORBIDDEN_ACTION]
    assert len(forbidden) == 1
    assert forbidden[0].event_ids == (refund.event_id,)


def test_canonical_attributes_are_never_overwritten() -> None:
    payload = _span(
        [
            _attr("gen_ai.operation.name", "execute_tool"),
            _attr("gen_ai.tool.name", "issue_refund"),
            _attr("tool.result.status", "ok"),
            _attr("gen_ai.task.status", "failure"),
            {
                "key": "tool.arguments.amount_eur",
                "value": {"doubleValue": 40.0},
            },
            _attr("gen_ai.tool.call.arguments", '{"amount_eur": 999.0}'),
        ]
    )
    (event,) = ingest_otlp_json(payload)
    assert event.attributes["tool.result.status"] == "ok"
    assert event.attributes["tool.arguments.amount_eur"] == 40.0


def test_malformed_tool_call_arguments_are_ignored() -> None:
    payload = _span(
        [
            _attr("gen_ai.operation.name", "execute_tool"),
            _attr("gen_ai.tool.name", "issue_refund"),
            _attr("gen_ai.task.status", "success"),
            _attr("gen_ai.tool.call.arguments", "not json at all {{{"),
        ]
    )
    (event,) = ingest_otlp_json(payload)
    assert event.attributes["tool.result.status"] == "ok"
    assert not any(k.startswith("tool.arguments.") for k in event.attributes)


def test_create_agent_span_is_not_an_agent_task() -> None:
    """Instrumentors emit `create_agent` when the graph is *built* — that
    is not a completed task and must not land on the Tasks line (ADR 0011,
    supersedes the ADR 0003 mapping)."""
    payload = _span([_attr("gen_ai.operation.name", "create_agent")])
    (event,) = ingest_otlp_json(payload)
    assert event.kind is SpanKind.UNKNOWN


def test_array_attributes_ingest_without_error() -> None:
    payload = _span(
        [
            _attr("gen_ai.operation.name", "invoke_agent"),
            {
                "key": "gen_ai.workflow.nodes",
                "value": {
                    "arrayValue": {
                        "values": [{"stringValue": "agent"}, {"stringValue": "tools"}]
                    }
                },
            },
        ]
    )
    (event,) = ingest_otlp_json(payload)
    assert event.attributes["gen_ai.workflow.nodes"] == ["agent", "tools"]
