"""alfred._http — shared urllib POST transport used by Slack + narration.

Hermetic: the scheme guard needs no network, and the HTTPError/URLError paths
are exercised by monkeypatching `urllib.request.urlopen` so no real call is
made. See tests/test_deliver_slack.py and tests/test_narrate_llm.py for how
each sink wraps `HttpError` in its own domain error.
"""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from alfred._http import HttpError, HTTPRequest, _NoCrossHostRedirect
from alfred._http import post as http_post


def _request(url: str) -> HTTPRequest:
    return HTTPRequest(url=url, headers={}, body=b"{}", timeout_s=1.0)


def test_post_rejects_non_http_url() -> None:
    with pytest.raises(HttpError, match="https://"):
        http_post(_request("file:///etc/passwd"), label="X")


def test_post_labels_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError("https://x", 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", boom)
    with pytest.raises(HttpError, match="Slack webhook returned HTTP 404: Not Found"):
        http_post(_request("https://x"), label="Slack webhook")


def test_post_labels_unreachable_host(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", boom)
    with pytest.raises(HttpError, match="LLM endpoint unreachable: no route"):
        http_post(_request("https://api.example/v1"), label="LLM endpoint")


def test_post_rejects_cleartext_to_a_remote_host() -> None:
    """ADR 0025 decision 4: these requests carry a credential — the LLM API key
    in a header, the Slack webhook in the URL path itself."""
    with pytest.raises(HttpError, match="https://"):
        http_post(_request("http://api.example/v1/chat"), label="LLM endpoint")


def test_post_allows_cleartext_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """A self-hosted model on localhost never puts the key on a wire."""
    captured: list[str] = []

    class _Response:
        def read(self) -> bytes:
            return b"{}"

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

    def fake_open(_self: object, request: object, **_kwargs: object) -> _Response:
        captured.append(getattr(request, "full_url", ""))
        return _Response()

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    http_post(_request("http://127.0.0.1:11434/v1/chat"), label="LLM endpoint")
    assert captured == ["http://127.0.0.1:11434/v1/chat"]


def test_post_error_never_echoes_the_url_path() -> None:
    """The path of a Slack webhook is its password; it must not reach a log."""
    secret = "https://hooks.slack.com/services/T0/B0/SUPERSECRET"
    with pytest.raises(HttpError) as excinfo:
        http_post(_request(secret.replace("https", "ftp")), label="Slack webhook")
    assert "SUPERSECRET" not in str(excinfo.value)


def test_redirect_to_another_host_is_refused() -> None:
    """The audit's PoC: urllib keeps custom headers across a redirect, so a 302
    handed `Authorization: Bearer <key>` to whatever host the endpoint chose."""
    handler = _NoCrossHostRedirect()
    request = urllib.request.Request("https://api.example/v1/chat")
    with pytest.raises(urllib.error.HTTPError, match="another host"):
        handler.redirect_request(
            request, None, 302, "Found", {}, "https://evil.example/collect"
        )


def test_redirect_within_the_same_host_is_followed() -> None:
    handler = _NoCrossHostRedirect()
    request = urllib.request.Request("https://api.example/v1/chat")
    redirected = handler.redirect_request(
        request, None, 302, "Found", {}, "https://api.example/v2/chat"
    )
    assert redirected is not None
