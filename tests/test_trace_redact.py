"""Falsifiable spec for declarative PII redaction at ingestion (ADR 0022).

The product guarantee under test: a value named in `redact` is masked before
the event reaches the trace store, so the raw value never lands in SQLite and
never travels to any downstream sink (Slack, HTML, narration).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from alfred.deliver.slack import build_block_kit_payload
from alfred.mandate.engine import evaluate
from alfred.mandate.model import DeviationType, ForbiddenRule, Mandate
from alfred.report.build import build_digest
from alfred.trace.ingest import ingest_otlp_json
from alfred.trace.redact import redact_attributes, redact_value
from alfred.trace.store import TraceStore

_EMAIL = "alice@example.com"


def _attr(key: str, value: dict[str, object]) -> dict[str, object]:
    return {"key": key, "value": value}


def _tool_span(span_id: str, *, extra: list[dict[str, object]]) -> dict[str, object]:
    return {
        "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
        "spanId": span_id,
        "parentSpanId": "",
        "name": "span.execute_tool",
        "startTimeUnixNano": "1788037200000000000",
        "endTimeUnixNano": "1788037201000000000",
        "attributes": [
            _attr("gen_ai.operation.name", {"stringValue": "execute_tool"}),
            _attr("gen_ai.tool.name", {"stringValue": "issue_refund"}),
            *extra,
        ],
    }


def _payload(*spans: dict[str, object]) -> dict[str, object]:
    return {"resourceSpans": [{"scopeSpans": [{"spans": list(spans)}]}]}


def test_redacted_value_absent_from_ingested_event() -> None:
    span = _tool_span("s1", extra=[_attr("tool.arguments.customer_email", {"stringValue": _EMAIL})])
    events = ingest_otlp_json(_payload(span), frozenset({"customer_email"}))
    masked = events[0].attributes["tool.arguments.customer_email"]
    assert masked.startswith("redacted:sha256:")
    assert _EMAIL not in masked


def test_redacted_value_absent_from_store(tmp_path: Path) -> None:
    """The client guarantee: the raw value is nowhere in the SQLite file."""
    span = _tool_span("s1", extra=[_attr("tool.arguments.customer_email", {"stringValue": _EMAIL})])
    events = ingest_otlp_json(_payload(span), frozenset({"customer_email"}))
    db_path = tmp_path / "traces.db"
    store = TraceStore(db_path)
    store.put_many(events)
    store.close()
    assert _EMAIL not in db_path.read_bytes().decode("utf-8", errors="ignore")


def test_redaction_is_stable_and_distinct() -> None:
    assert redact_value(_EMAIL) == redact_value(_EMAIL)
    assert redact_value(_EMAIL) != redact_value("bob@example.com")


def test_non_redacted_numeric_arg_untouched() -> None:
    """A field left out of `redact` stays numeric, so its forbidden rule still fires."""
    span = _tool_span("s1", extra=[_attr("tool.arguments.amount_eur", {"doubleValue": 250.0})])
    events = ingest_otlp_json(_payload(span), frozenset({"customer_email"}))
    assert events[0].attributes["tool.arguments.amount_eur"] == 250.0
    rule = ForbiddenRule(tool="issue_refund", arg="amount_eur", operator=">", threshold=100.0)
    mandate = Mandate(
        agent="refund-bot",
        allowed_tools=frozenset({"issue_refund"}),
        daily_budget_eur=5.0,
        forbidden_actions=(rule,),
        escalate_when=(),
        redact=frozenset({"customer_email"}),
    )
    deviations = evaluate(mandate, events)
    assert [d.type for d in deviations] == [DeviationType.FORBIDDEN_ACTION]


def test_redact_matches_bare_and_prefixed_key() -> None:
    attributes = {
        "tool.arguments.customer_email": _EMAIL,
        "gen_ai.prompt": "secret system prompt",
        "tool.arguments.amount_eur": 250.0,
    }
    redacted = redact_attributes(attributes, frozenset({"customer_email", "gen_ai.prompt"}))
    assert redacted["tool.arguments.customer_email"].startswith("redacted:sha256:")
    assert redacted["gen_ai.prompt"].startswith("redacted:sha256:")
    assert redacted["tool.arguments.amount_eur"] == 250.0


def test_empty_redact_is_noop() -> None:
    attributes = {"tool.arguments.customer_email": _EMAIL}
    assert redact_attributes(attributes, frozenset()) is attributes
    span = _tool_span("s1", extra=[_attr("tool.arguments.customer_email", {"stringValue": _EMAIL})])
    events = ingest_otlp_json(_payload(span))
    assert events[0].attributes["tool.arguments.customer_email"] == _EMAIL


def test_redacted_value_absent_from_slack_payload() -> None:
    """End to end: a redacted field never surfaces in the Slack Block Kit payload."""
    rule = ForbiddenRule(tool="issue_refund", arg="amount_eur", operator=">", threshold=100.0)
    span = _tool_span(
        "s1",
        extra=[
            _attr("tool.arguments.customer_email", {"stringValue": _EMAIL}),
            _attr("tool.arguments.amount_eur", {"doubleValue": 250.0}),
        ],
    )
    mandate = Mandate(
        agent="refund-bot",
        allowed_tools=frozenset({"issue_refund"}),
        daily_budget_eur=5.0,
        forbidden_actions=(rule,),
        escalate_when=(),
        redact=frozenset({"customer_email"}),
    )
    events = ingest_otlp_json(_payload(span), mandate.redact)
    digest = build_digest(mandate, events, date(2026, 7, 24))
    payload = build_block_kit_payload(digest)
    assert _EMAIL not in json.dumps(payload)


_ARGS_BLOB = "gen_ai.tool.call.arguments"


def _blob_span(span_id: str, blob: str) -> dict[str, object]:
    """A standard-semconv tool span: arguments packed in one JSON blob."""
    return _tool_span(span_id, extra=[_attr(_ARGS_BLOB, {"stringValue": blob})])


def test_redacted_value_masked_inside_the_raw_arguments_blob(tmp_path: Path) -> None:
    """ADR 0025 decision 1: flattening copied the arguments out of the blob but
    left the blob itself, so the declared PII reached SQLite in clear text."""
    blob = json.dumps({"customer_email": _EMAIL, "amount_eur": 250.0})
    events = ingest_otlp_json(_payload(_blob_span("s1", blob)), frozenset({"customer_email"}))

    assert _EMAIL not in events[0].attributes[_ARGS_BLOB]
    assert "250" in events[0].attributes[_ARGS_BLOB]  # untouched fields survive
    db_path = tmp_path / "traces.db"
    store = TraceStore(db_path)
    store.put_many(events)
    store.close()
    assert _EMAIL not in db_path.read_bytes().decode("utf-8", errors="ignore")


def test_redacted_value_masked_inside_a_nested_blob() -> None:
    blob = json.dumps({"customer": {"contacts": [{"customer_email": _EMAIL}]}})
    events = ingest_otlp_json(_payload(_blob_span("s1", blob)), frozenset({"customer_email"}))
    assert _EMAIL not in events[0].attributes[_ARGS_BLOB]


def test_unparsable_blob_is_masked_whole_when_redaction_is_configured() -> None:
    """Fail-closed: what cannot be inspected cannot be cleared."""
    events = ingest_otlp_json(
        _payload(_blob_span("s1", "{ not json " + _EMAIL)), frozenset({"customer_email"})
    )
    assert _EMAIL not in events[0].attributes[_ARGS_BLOB]


def test_blob_without_a_named_field_is_left_intact() -> None:
    blob = json.dumps({"order_id": "A-1", "amount_eur": 250.0})
    events = ingest_otlp_json(_payload(_blob_span("s1", blob)), frozenset({"customer_email"}))
    assert events[0].attributes[_ARGS_BLOB] == blob
