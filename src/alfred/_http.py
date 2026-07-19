"""Shared HTTP plumbing for the modules that POST over the network.

`alfred.narrate.llm` and `alfred.deliver.slack` used to carry identical
copies of this request shape and urllib logic; they now share it here and
each wraps `TransportError` into its own domain error (`NarrateError`,
`DeliverError`). The injection pattern is unchanged: real urllib by
default, a fake transport in tests, zero real network calls in the suite.
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


class TransportError(Exception):
    """Raised when the endpoint is unreachable or rejects the request."""


def post(request: HTTPRequest) -> bytes:
    """POST `request` and return the response body.

    Raises `TransportError` on a non-HTTP(S) URL, an HTTP error status, or
    an unreachable endpoint.
    """
    if not request.url.startswith(("http://", "https://")):
        raise TransportError(f"refusing to POST to non-HTTP(S) URL: {request.url!r}")
    urlreq = urllib.request.Request(  # noqa: S310
        request.url, data=request.body, headers=request.headers, method="POST"
    )
    try:
        with urllib.request.urlopen(urlreq, timeout=request.timeout_s) as response:  # noqa: S310
            content: bytes = response.read()
            return content
    except urllib.error.HTTPError as exc:
        raise TransportError(f"HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise TransportError(f"unreachable: {exc.reason}") from exc
