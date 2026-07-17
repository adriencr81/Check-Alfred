"""Digest → prose, verified against hallucinated citations.

See PLAN.md §5 Brique 4 and docs/verified_nlg.md for the guarantee this
module exists to enforce, and docs/adr/0006-brique4-verified-nlg-design.md
for the design decisions recorded here (file layout, HTTP client shape,
one-LLM-call-per-line, fail-whole-call-on-first-violation).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from alfred.narrate.model import NarratedDigest, Sentence
from alfred.report.model import Digest, Line
from alfred.trace.model import EventId

_CITATION_PATTERN = re.compile(r"\[evt:([^\]]*)\]")


class NarrateError(Exception):
    """Raised when the LLM's output violates the citation guarantee, or the
    LLM endpoint cannot be reached / returns a malformed response."""


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str: ...


def extract_event_ids(text: str) -> set[EventId]:
    ids: set[EventId] = set()
    for match in _CITATION_PATTERN.finditer(text):
        for raw in match.group(1).split(","):
            stripped = raw.strip()
            if stripped:
                ids.add(EventId(stripped))
    return ids


def _build_prompt(line: Line) -> str:
    allowed = ", ".join(line.sources)
    return (
        f"Write one short sentence reporting the metric {line.kind.value!r} "
        f"with value {line.value}. You may only cite these event IDs, and "
        f"must cite at least one, as a single trailing bracket in the exact "
        f"form [evt:id1, id2]: {allowed}"
    )


def _narrate_line(line: Line, llm_client: LLMClient) -> Sentence:
    text = llm_client.complete(_build_prompt(line))
    cited = extract_event_ids(text)
    if not cited:
        raise NarrateError(f"LLM produced a sentence with no event citation: {text!r}")
    hallucinated = cited - set(line.sources)
    if hallucinated:
        raise NarrateError(
            f"LLM cited events not in source {sorted(hallucinated)} "
            f"for line {line.kind.value!r}: {text!r}"
        )
    return Sentence(text=text, line=line)


def narrate(digest: Digest, llm_client: LLMClient) -> NarratedDigest:
    """Call `llm_client` once per `Line` of `digest.lines`, in order.

    Raises `NarrateError` the instant any sentence fails the citation
    guarantee — the whole call aborts, no partial `NarratedDigest` is ever
    returned (fail loudly, never silently degrade — see PLAN.md D5).
    """
    sentences = tuple(_narrate_line(line, llm_client) for line in digest.lines)
    return NarratedDigest(digest=digest, sentences=sentences)


@dataclass(frozen=True, slots=True)
class HTTPRequest:
    url: str
    headers: dict[str, str]
    body: bytes
    timeout_s: float


class Transport(Protocol):
    def __call__(self, request: HTTPRequest) -> bytes: ...


def _urllib_transport(request: HTTPRequest) -> bytes:
    if not request.url.startswith(("http://", "https://")):
        raise NarrateError(f"refusing to fetch non-HTTP(S) URL: {request.url!r}")
    urlreq = urllib.request.Request(  # noqa: S310
        request.url, data=request.body, headers=request.headers, method="POST"
    )
    try:
        with urllib.request.urlopen(urlreq, timeout=request.timeout_s) as response:  # noqa: S310
            content: bytes = response.read()
            return content
    except urllib.error.HTTPError as exc:
        raise NarrateError(f"LLM endpoint returned HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise NarrateError(f"LLM endpoint unreachable: {exc.reason}") from exc


def _extract_content(raw: bytes) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NarrateError(f"LLM response is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise NarrateError("LLM response JSON is not an object")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise NarrateError(f"LLM response missing 'choices[0]': {data!r}")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise NarrateError(f"LLM response missing 'choices[0].message': {data!r}")
    content = message.get("content")
    if not isinstance(content, str):
        raise NarrateError(f"LLM response missing 'choices[0].message.content': {data!r}")
    return content


@dataclass(frozen=True, slots=True)
class OpenAICompatibleClient:
    base_url: str
    api_key: str
    model: str
    timeout_s: float = 30.0
    transport: Transport = _urllib_transport

    def complete(self, prompt: str) -> str:
        body = json.dumps(
            {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        ).encode("utf-8")
        request = HTTPRequest(
            url=f"{self.base_url.rstrip('/')}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            body=body,
            timeout_s=self.timeout_s,
        )
        return _extract_content(self.transport(request))
