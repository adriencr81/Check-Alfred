"""Digest → Slack Block Kit payload, delivered via incoming webhook.

See PLAN.md §5 Brique 5 and docs/adr/0007-brique5-delivery-cli-design.md for
why the payload wraps `alfred.report.render.render`'s fixed-format text in a
single Block Kit section — one source of truth for the digest's textual
layout — instead of re-deriving per-line blocks. HTTP plumbing is shared
with `alfred.narrate.llm` via `alfred._http`: real `urllib` by default, a
fake `Transport` in tests, zero real network calls in the test suite.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from alfred import _http
from alfred._http import HTTPRequest as HTTPRequest  # re-export: part of this module's API
from alfred.report.model import Digest
from alfred.report.render import render


class DeliverError(Exception):
    """Raised when a Slack webhook delivery fails."""


def build_block_kit_payload(digest: Digest) -> dict[str, Any]:
    """Build a Block Kit `blocks` payload wrapping the digest's rendered text."""
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Alfred · {digest.agent} · {digest.date.isoformat()}",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"```{render(digest)}```"},
            },
        ]
    }


class Transport(Protocol):
    def __call__(self, request: HTTPRequest) -> None: ...


def _urllib_transport(request: HTTPRequest) -> None:
    try:
        _http.post(request)
    except _http.TransportError as exc:
        raise DeliverError(f"Slack webhook: {exc}") from exc


def send(
    digest: Digest,
    webhook_url: str,
    transport: Transport = _urllib_transport,
    timeout_s: float = 10.0,
) -> None:
    """POST `digest`'s Block Kit payload to a Slack incoming webhook.

    Raises `DeliverError` if the webhook is unreachable or rejects the
    payload (fail loudly — no silent drop, matching CLAUDE.md's D5).
    """
    body = json.dumps(build_block_kit_payload(digest)).encode("utf-8")
    request = HTTPRequest(
        url=webhook_url,
        headers={"Content-Type": "application/json"},
        body=body,
        timeout_s=timeout_s,
    )
    transport(request)
