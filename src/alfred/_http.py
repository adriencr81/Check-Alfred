"""Shared HTTP request envelope + urllib POST transport.

Two sinks POST JSON over urllib behind an injectable transport (real urllib
by default, a fake in tests — zero real network calls in the suite): the
Slack webhook (fire-and-forget, `alfred.deliver.slack`) and the narration LLM
endpoint (reads the response body, `alfred.narrate.llm`). They share the
request shape and the same urllib mechanics — the http(s) scheme guard, the
POST, and the `HTTPError`/`URLError` translation — differing only in their own
error type and whether they consume the response body. This module holds that
common core; each sink keeps a thin transport that maps `HttpError` onto its
own exception (`DeliverError` / `NarrateError`) so callers still catch one
domain error.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HTTPRequest:
    url: str
    headers: dict[str, str]
    body: bytes
    timeout_s: float


class HttpError(Exception):
    """Raised by `post` when the request cannot be completed."""


def post(request: HTTPRequest, *, label: str) -> bytes:
    """POST `request` over urllib and return the response body.

    `label` names the endpoint in error messages (e.g. "Slack webhook",
    "LLM endpoint"). Raises `HttpError` on a non-HTTP(S) URL, an HTTP error
    status, or an unreachable host — the caller maps it onto its own type.
    """
    if not request.url.startswith(("http://", "https://")):
        raise HttpError(f"refusing to POST to non-HTTP(S) URL: {request.url!r}")
    urlreq = urllib.request.Request(  # noqa: S310
        request.url, data=request.body, headers=request.headers, method="POST"
    )
    try:
        with urllib.request.urlopen(urlreq, timeout=request.timeout_s) as response:  # noqa: S310
            content: bytes = response.read()
            return content
    except urllib.error.HTTPError as exc:
        raise HttpError(f"{label} returned HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise HttpError(f"{label} unreachable: {exc.reason}") from exc
