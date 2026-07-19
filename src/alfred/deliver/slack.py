"""Digest → Slack Block Kit payload, delivered via incoming webhook.

See PLAN.md §5 Brique 5, docs/adr/0007-brique5-delivery-cli-design.md and
docs/adr/0012-slack-native-block-kit.md for why the payload uses native
blocks (fields for the counters, a dedicated warning section for
deviations, evidence in a context block) instead of wrapping
`alfred.report.render.render`'s fixed-format text in a code block. The HTTP
shape (`HTTPRequest`/`Transport`) mirrors `alfred.narrate.llm`'s injection
pattern: real `urllib` by default, a fake `Transport` in tests, zero real
network calls in the test suite.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from alfred.mandate.model import Deviation
from alfred.report.model import Digest, LineKind
from alfred.report.render import LABELS, format_sources, format_value

_EVIDENCE_LABELS: dict[LineKind, str] = {
    LineKind.TASKS_COMPLETED: "tasks",
    LineKind.COST_EUR: "cost",
    LineKind.ESCALATIONS: "escalations",
}


class DeliverError(Exception):
    """Raised when a Slack webhook delivery fails."""


def _fields_section(digest: Digest) -> dict[str, Any]:
    return {
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*{LABELS[line.kind]}*\n{format_value(line)}"}
            for line in digest.lines
        ],
    }


def _deviation_section(deviations: tuple[Deviation, ...]) -> dict[str, Any]:
    if len(deviations) == 1:
        deviation = deviations[0]
        body = f"{deviation.type.value}: {deviation.message}"
    else:
        body = "\n".join(
            f"• {deviation.type.value}: {deviation.message}" for deviation in deviations
        )
    count = len(deviations)
    title = f"⚠️ *{count} deviation{'s' if count > 1 else ''} (mandate)*"
    return {"type": "section", "text": {"type": "mrkdwn", "text": f"{title}\n{body}"}}


def _evidence_context(digest: Digest) -> dict[str, Any]:
    parts = [
        f"{_EVIDENCE_LABELS[line.kind]} {format_sources(line.sources)}" for line in digest.lines
    ]
    parts.extend(
        f"deviation {format_sources(deviation.event_ids)}" for deviation in digest.deviations
    )
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "Evidence — " + " · ".join(parts)}],
    }


def build_block_kit_payload(digest: Digest) -> dict[str, Any]:
    """Build a native Block Kit payload: header, counter fields, a dedicated
    warning section when the mandate caught deviations, and the truncated
    evidence IDs in a context block. Full event IDs stay in the `Digest`."""
    title = f"Alfred · {digest.agent} · {digest.date.isoformat()}"
    count = len(digest.deviations)
    summary = f"{count} deviation{'s' if count > 1 else ''}" if count else "all clear"

    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": title}}
    ]
    if digest.lines:
        blocks.append(_fields_section(digest))
    if digest.deviations:
        blocks.append(_deviation_section(digest.deviations))
    if digest.lines or digest.deviations:
        blocks.append(_evidence_context(digest))
    return {"text": f"{title} — {summary}", "blocks": blocks}


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
