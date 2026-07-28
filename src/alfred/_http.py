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
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.client import HTTPMessage
from typing import IO


@dataclass(frozen=True, slots=True)
class HTTPRequest:
    url: str
    headers: dict[str, str]
    body: bytes
    timeout_s: float


class HttpError(Exception):
    """Raised by `post` when the request cannot be completed."""


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def endpoint_error(url: str) -> str | None:
    """Why `url` is unfit to carry a credential, or None if it is fit.

    HTTPS everywhere, except cleartext to loopback — the real case of a
    self-hosted model (ollama, llama.cpp, vLLM), where the request never
    reaches a wire. See ADR 0025 decision 4. Shared with `alfred.config` so the
    same rule is applied at `init`, at config load, and at request time.
    """
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == "https":
        return None
    if parsed.scheme == "http" and (parsed.hostname or "").lower() in _LOOPBACK_HOSTS:
        return None
    return f"must be an https:// URL (http:// is only allowed for localhost), got {safe(url)}"


def safe(url: str) -> str:
    """`url` reduced to `scheme://host` — never its path or query.

    A Slack incoming webhook *is* its path: repeating a URL in an error message
    or a log leaks the credential (ADR 0025 decision 6).
    """
    parsed = urllib.parse.urlsplit(url)
    if not parsed.scheme:
        return "<malformed URL>"
    return f"{parsed.scheme}://{parsed.netloc}/…"


class _NoCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse any redirect that changes host.

    urllib carries the request's custom headers across a redirect, including to
    another origin, so a `302` from the configured endpoint handed
    `Authorization: Bearer <key>` to a host of its choosing — the audit's PoC.
    No legitimate webhook or LLM endpoint needs a cross-host bounce on a POST.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        if urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            raise urllib.error.HTTPError(
                safe(newurl),
                code,
                f"refusing to follow a redirect to another host ({safe(newurl)})",
                headers,
                None,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# Built once: the default global opener follows cross-host redirects, which is
# exactly what `_NoCrossHostRedirect` exists to prevent.
_OPENER = urllib.request.build_opener(_NoCrossHostRedirect)


def post(request: HTTPRequest, *, label: str) -> bytes:
    """POST `request` over urllib and return the response body.

    `label` names the endpoint in error messages (e.g. "Slack webhook",
    "LLM endpoint"). Raises `HttpError` on a URL unfit to carry a credential,
    a cross-host redirect, an HTTP error status, or an unreachable host — the
    caller maps it onto its own type. Error messages name only `scheme://host`.
    """
    unfit = endpoint_error(request.url)
    if unfit is not None:
        raise HttpError(f"refusing to POST to {label}: it {unfit}")
    urlreq = urllib.request.Request(  # noqa: S310
        request.url, data=request.body, headers=request.headers, method="POST"
    )
    try:
        with _OPENER.open(urlreq, timeout=request.timeout_s) as response:
            content: bytes = response.read()
            return content
    except urllib.error.HTTPError as exc:
        raise HttpError(f"{label} returned HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise HttpError(f"{label} unreachable: {exc.reason}") from exc
