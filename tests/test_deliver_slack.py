"""alfred.deliver.slack — Digest → Block Kit payload → webhook delivery.

See PLAN.md §5 Brique 5 (`test_slack_payload_is_valid_block_kit`, and the
end-to-end "fixture trace → digest → payload Slack, sans appel réseau réel"
definition-of-done) and docs/adr/0007-brique5-delivery-cli-design.md.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from alfred.deliver.slack import DeliverError, HTTPRequest, Transport, build_block_kit_payload, send
from alfred.mandate.model import Mandate
from alfred.report.build import build_digest
from alfred.report.model import Digest, Line, LineKind
from alfred.trace.ingest import ingest_otlp_file
from alfred.trace.model import EventId

from ._block_kit import assert_valid_block_kit_payload

_CONSTRAINTS_PATH = Path(__file__).parent / "fixtures" / "block_kit_constraints.json"


def _constraints() -> dict[str, object]:
    return cast("dict[str, object]", json.loads(_CONSTRAINTS_PATH.read_text(encoding="utf-8")))


def _digest() -> Digest:
    return Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(Line(kind=LineKind.TASKS_COMPLETED, value=3.0, sources=(EventId("e1"),)),),
    )


def test_build_block_kit_payload_wraps_rendered_digest() -> None:
    payload = build_block_kit_payload(_digest())
    assert payload["blocks"][0]["type"] == "header"
    assert "refund-bot-v3" in payload["blocks"][0]["text"]["text"]
    assert payload["blocks"][1]["type"] == "section"
    assert "Tasks completed" in payload["blocks"][1]["text"]["text"]
    assert "evt:e1" in payload["blocks"][1]["text"]["text"]


def test_slack_payload_is_valid_block_kit() -> None:
    payload = build_block_kit_payload(_digest())
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
