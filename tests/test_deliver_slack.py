"""alfred.deliver.slack — Digest → Block Kit payload → webhook delivery.

See PLAN.md §5 Brique 5 (`test_slack_payload_is_valid_block_kit`, and the
end-to-end "fixture trace → digest → payload Slack, sans appel réseau réel"
definition-of-done), docs/adr/0007-brique5-delivery-cli-design.md and
docs/adr/0012-slack-native-block-kit.md.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from alfred.deliver.slack import DeliverError, HTTPRequest, Transport, build_block_kit_payload, send
from alfred.mandate.model import Deviation, DeviationType, Mandate
from alfred.report.build import build_digest
from alfred.report.model import Digest, Line, LineKind
from alfred.trace.ingest import ingest_otlp_file
from alfred.trace.model import EventId

from ._block_kit import assert_valid_block_kit_payload

_CONSTRAINTS_PATH = Path(__file__).parent / "fixtures" / "block_kit_constraints.json"
_LONG_DEVIATION_ID = "784800533a465770"


def _constraints() -> dict[str, object]:
    return cast("dict[str, object]", json.loads(_CONSTRAINTS_PATH.read_text(encoding="utf-8")))


def _digest() -> Digest:
    return Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(Line(kind=LineKind.TASKS_COMPLETED, value=3.0, sources=(EventId("e1"),)),),
    )


def _digest_with_deviation() -> Digest:
    return Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(
            Line(
                LineKind.TASKS_COMPLETED,
                3.0,
                tuple(EventId(f"e69a993566e99bd{i}") for i in range(3)),
            ),
            Line(LineKind.COST_EUR, 0.06, tuple(EventId(f"f0dd0fd8f111ebc{i}") for i in range(6))),
        ),
        deviations=(
            Deviation(
                type=DeviationType.FORBIDDEN_ACTION,
                event_ids=(EventId(_LONG_DEVIATION_ID),),
                message="forbidden action 'issue_refund_above_100_eur': "
                "issue_refund called with amount_eur=250.0 > 100.0",
            ),
        ),
    )


def test_payload_has_header_and_one_field_per_line() -> None:
    payload = build_block_kit_payload(_digest())
    blocks = payload["blocks"]
    assert blocks[0]["type"] == "header"
    assert "refund-bot-v3" in blocks[0]["text"]["text"]
    assert blocks[1]["type"] == "section"
    fields = blocks[1]["fields"]
    assert len(fields) == 1
    assert "*Tasks completed*" in fields[0]["text"]
    assert "3" in fields[0]["text"]


def test_payload_without_deviation_has_no_warning_section() -> None:
    payload = build_block_kit_payload(_digest())
    assert not any("⚠️" in json.dumps(block) for block in payload["blocks"])
    assert payload["text"].endswith("all clear")


def test_payload_with_deviation_has_dedicated_warning_section() -> None:
    payload = build_block_kit_payload(_digest_with_deviation())
    warning_blocks = [
        block
        for block in payload["blocks"]
        if block["type"] == "section" and "⚠️" in block.get("text", {}).get("text", "")
    ]
    assert len(warning_blocks) == 1
    text = warning_blocks[0]["text"]["text"]
    assert "*1 deviation (mandate)*" in text
    assert "forbidden_action" in text
    assert "amount_eur=250.0 > 100.0" in text


def test_payload_fallback_text_counts_deviations() -> None:
    payload = build_block_kit_payload(_digest_with_deviation())
    assert payload["text"] == "Alfred · refund-bot-v3 · 2026-08-30 — 1 deviation"


def test_payload_evidence_context_truncates_ids() -> None:
    payload = build_block_kit_payload(_digest_with_deviation())
    context = payload["blocks"][-1]
    assert context["type"] == "context"
    evidence = context["elements"][0]["text"]
    assert evidence.startswith("Evidence — ")
    assert "tasks [evt:e69a9935…, e69a9935…, e69a9935…]" in evidence
    assert "cost [evt:f0dd0fd8…, f0dd0fd8…, f0dd0fd8… +3]" in evidence
    assert "deviation [evt:78480053…]" in evidence
    assert _LONG_DEVIATION_ID not in json.dumps(payload)


def test_slack_payload_is_valid_block_kit() -> None:
    for digest in (_digest(), _digest_with_deviation()):
        payload = build_block_kit_payload(digest)
        assert_valid_block_kit_payload(payload, _constraints())


def _fake_transport(captured: list[HTTPRequest]) -> Transport:
    def transport(request: HTTPRequest) -> None:
        captured.append(request)

    return transport


def test_send_posts_expected_request() -> None:
    captured: list[HTTPRequest] = []
    send(
        _digest(),
        "https://hooks.slack.com/services/T0/B0/xyz",
        transport=_fake_transport(captured),
    )

    assert len(captured) == 1
    request = captured[0]
    assert request.url == "https://hooks.slack.com/services/T0/B0/xyz"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.body) == build_block_kit_payload(_digest())


def test_send_propagates_transport_failure() -> None:
    def failing_transport(request: HTTPRequest) -> None:
        raise DeliverError("Slack webhook returned HTTP 404: Not Found")

    with pytest.raises(DeliverError, match="404"):
        send(_digest(), "https://hooks.slack.com/services/T0/B0/xyz", transport=failing_transport)


def _mandate() -> Mandate:
    return Mandate(
        agent="refund-bot-v3",
        allowed_tools=frozenset({"read_order", "issue_refund", "notify_customer"}),
        daily_budget_eur=5.0,
        forbidden_actions=(),
        escalate_when=(),
    )


def test_end_to_end_trace_to_digest_to_slack_payload_without_network(
    otlp_sample_path: Path,
) -> None:
    """DoD integration test: fixture trace → digest → Block Kit payload,
    delivered through a fake transport so no real network call is made."""
    events = ingest_otlp_file(otlp_sample_path)
    digest = build_digest(_mandate(), events, date(2026, 8, 30))

    payload = build_block_kit_payload(digest)
    assert_valid_block_kit_payload(payload, _constraints())

    captured: list[HTTPRequest] = []
    send(
        digest,
        "https://hooks.slack.com/services/T0/B0/xyz",
        transport=_fake_transport(captured),
    )
    assert len(captured) == 1
    assert json.loads(captured[0].body) == payload
