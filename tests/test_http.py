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

from alfred._http import HttpError, HTTPRequest
from alfred._http import post as http_post


def _request(url: str) -> HTTPRequest:
    return HTTPRequest(url=url, headers={}, body=b"{}", timeout_s=1.0)


def test_post_rejects_non_http_url() -> None:
    with pytest.raises(HttpError, match="non-HTTP"):
        http_post(_request("file:///etc/passwd"), label="X")


def test_post_labels_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError("http://x", 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(HttpError, match="Slack webhook returned HTTP 404: Not Found"):
        http_post(_request("http://x"), label="Slack webhook")


def test_post_labels_unreachable_host(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(HttpError, match="LLM endpoint unreachable: no route"):
        http_post(_request("https://api.example/v1"), label="LLM endpoint")
