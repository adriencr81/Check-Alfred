"""Falsifiable spec for declarative PII redaction at ingestion (ADR 0022).

The product guarantee under test: a value named in `redact` is masked before
the event reaches the trace store, so the raw value never lands in SQLite and
never travels to any downstream sink (Slack, HTML, narration).
"""

from __future__ import annotations

import json
import stat
from datetime import date
from pathlib import Path

from alfred.deliver.slack import build_block_kit_payload
from alfred.mandate.engine import evaluate
from alfred.mandate.model import DeviationType, ForbiddenRule, Mandate
from alfred.report.build import build_digest
from alfred.trace.ingest import ingest_otlp_json
from alfred.trace.redact import Redactor, redactor_for
from alfred.trace.store import TraceStore

_EMAIL = "alice@example.com"


def _redactor(*names: str) -> Redactor:
    """A Redactor over a fixed test key — the key's provenance is covered by
    tests/test_config.py, these tests are about what gets masked."""
    return Redactor(names=frozenset(names), key=b"test-key")


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
    events = ingest_otlp_json(_payload(span), _redactor("customer_email"))
    masked = events[0].attributes["tool.arguments.customer_email"]
    assert masked.startswith("redacted:hmac:")
    assert _EMAIL not in masked


def test_redacted_value_absent_from_store(tmp_path: Path) -> None:
    """The client guarantee: the raw value is nowhere in the SQLite file."""
    span = _tool_span("s1", extra=[_attr("tool.arguments.customer_email", {"stringValue": _EMAIL})])
    events = ingest_otlp_json(_payload(span), _redactor("customer_email"))
    db_path = tmp_path / "traces.db"
    store = TraceStore(db_path)
    store.put_many(events)
    store.close()
    assert _EMAIL not in db_path.read_bytes().decode("utf-8", errors="ignore")


def test_redaction_is_stable_and_distinct() -> None:
    """Equality survives masking — what loop_detected depends on."""
    redactor = _redactor("customer_email")
    assert redactor.value(_EMAIL) == redactor.value(_EMAIL)
    assert redactor.value(_EMAIL) != redactor.value("bob@example.com")


def test_non_redacted_numeric_arg_untouched() -> None:
    """A field left out of `redact` stays numeric, so its forbidden rule still fires."""
    span = _tool_span("s1", extra=[_attr("tool.arguments.amount_eur", {"doubleValue": 250.0})])
    events = ingest_otlp_json(_payload(span), _redactor("customer_email"))
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
    redacted = _redactor("customer_email", "gen_ai.prompt").apply(attributes)
    assert redacted["tool.arguments.customer_email"].startswith("redacted:hmac:")
    assert redacted["gen_ai.prompt"].startswith("redacted:hmac:")
    assert redacted["tool.arguments.amount_eur"] == 250.0


def test_empty_redact_is_noop() -> None:
    attributes = {"tool.arguments.customer_email": _EMAIL}
    assert Redactor(names=frozenset(), key=b"k").apply(attributes) is attributes
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
    events = ingest_otlp_json(_payload(span), _redactor(*mandate.redact))
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
    events = ingest_otlp_json(_payload(_blob_span("s1", blob)), _redactor("customer_email"))

    assert _EMAIL not in events[0].attributes[_ARGS_BLOB]
    assert "250" in events[0].attributes[_ARGS_BLOB]  # untouched fields survive
    db_path = tmp_path / "traces.db"
    store = TraceStore(db_path)
    store.put_many(events)
    store.close()
    assert _EMAIL not in db_path.read_bytes().decode("utf-8", errors="ignore")


def test_redacted_value_masked_inside_a_nested_blob() -> None:
    blob = json.dumps({"customer": {"contacts": [{"customer_email": _EMAIL}]}})
    events = ingest_otlp_json(_payload(_blob_span("s1", blob)), _redactor("customer_email"))
    assert _EMAIL not in events[0].attributes[_ARGS_BLOB]


def test_unparsable_blob_is_masked_whole_when_redaction_is_configured() -> None:
    """Fail-closed: what cannot be inspected cannot be cleared."""
    events = ingest_otlp_json(
        _payload(_blob_span("s1", "{ not json " + _EMAIL)), _redactor("customer_email")
    )
    assert _EMAIL not in events[0].attributes[_ARGS_BLOB]


def test_blob_without_a_named_field_is_left_intact() -> None:
    blob = json.dumps({"order_id": "A-1", "amount_eur": 250.0})
    events = ingest_otlp_json(_payload(_blob_span("s1", blob)), _redactor("customer_email"))
    assert events[0].attributes[_ARGS_BLOB] == blob


def test_redaction_key_is_created_private_and_reused(tmp_path: Path) -> None:
    """ADR 0025 decision 3: the key is what stops a masked email from being
    recovered from a dictionary, so it is owner-only and stable."""
    first = redactor_for(tmp_path, frozenset({"customer_email"}))
    assert first is not None
    key_file = tmp_path / ".alfred" / "redaction-key"
    assert key_file.is_file()
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600

    again = redactor_for(tmp_path, frozenset({"customer_email"}))
    assert again is not None
    assert again.value(_EMAIL) == first.value(_EMAIL)  # stable across passes


def test_redaction_tokens_differ_between_projects(tmp_path: Path) -> None:
    one = redactor_for(tmp_path / "a", frozenset({"customer_email"}))
    other = redactor_for(tmp_path / "b", frozenset({"customer_email"}))
    assert one is not None and other is not None
    assert one.value(_EMAIL) != other.value(_EMAIL)


def test_no_key_is_created_when_the_mandate_redacts_nothing(tmp_path: Path) -> None:
    assert redactor_for(tmp_path, frozenset()) is None
    assert not (tmp_path / ".alfred" / "redaction-key").exists()
