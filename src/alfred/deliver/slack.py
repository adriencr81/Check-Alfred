"""Digest → Slack Block Kit payload, delivered via incoming webhook.

See PLAN.md §5 Brique 5 and docs/adr/0007-brique5-delivery-cli-design.md for
why the payload wraps `alfred.report.render.render`'s fixed-format text in a
single Block Kit section — one source of truth for the digest's textual
layout — instead of re-deriving per-line blocks. The HTTP shape
(`HTTPRequest`/`Transport`) mirrors `alfred.narrate.llm`'s injection pattern
for the same reason: real `urllib` by default, a fake `Transport` in tests,
zero real network calls in the test suite.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

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


@dataclass(frozen=True, slots=True)
class HTTPRequest:
    url: str
    headers: dict[str, str]
    body: bytes
    timeout_s: float


class Transport(Protocol):
    def __call__(self, request: HTTPRequest) -> None: ...


def _urllib_transport(request: HTTPRequest) -> None:
    if not request.url.startswith(("http://", "https://")):
        raise DeliverError(f"refusing to post to non-HTTP(S) URL: {request.url!r}")
    urlreq = urllib.request.Request(  # noqa: S310
        request.url, data=request.body, headers=request.headers, method="POST"
    )
    try:
        urllib.request.urlopen(urlreq, timeout=request.timeout_s)  # noqa: S310
    except urllib.error.HTTPError as exc:
        raise DeliverError(f"Slack webhook returned HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise DeliverError(f"Slack webhook unreachable: {exc.reason}") from exc


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
