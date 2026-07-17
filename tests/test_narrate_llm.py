"""Verified NLG — Digest → prose, anchored to event IDs.

See PLAN.md §5 Brique 4 for the key falsifiable test (`test_narrated_digest_
only_uses_source_events`, "the test that embodies the product thesis") and
docs/adr/0006-brique4-verified-nlg-design.md for the design decisions
(scope, HTTP client shape, one-LLM-call-per-line, fail-whole-call).
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from alfred.narrate.llm import (
    HTTPRequest,
    NarrateError,
    OpenAICompatibleClient,
    Transport,
    extract_event_ids,
    narrate,
)
from alfred.narrate.model import Sentence
from alfred.report.model import Digest, Line, LineKind
from alfred.trace.model import EventId


def _line(kind: LineKind, value: float, *sources: str) -> Line:
    return Line(kind=kind, value=value, sources=tuple(EventId(s) for s in sources))


def _digest(*lines: Line) -> Digest:
    return Digest(agent="refund-bot-v3", date=date(2026, 8, 30), lines=lines)


class _EchoStubLLM:
    """Well-behaved stub: cites exactly the event IDs allowed by the prompt."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        allowed = prompt.rsplit(":", 1)[1].strip()
        return f"Did the thing. [evt:{allowed}]"


class _FixedTextStubLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        return self.text


class _SequenceStubLLM:
    """Returns one fixed text per call, in order; records prompts received."""

    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._texts[len(self.prompts) - 1]


def test_narrated_digest_only_uses_source_events() -> None:
    digest = _digest(
        _line(LineKind.TASKS_COMPLETED, 2.0, "a1", "a2"),
        _line(LineKind.COST_EUR, 1.25, "c1"),
    )
    narrated = narrate(digest, llm_client=_EchoStubLLM())
    for sentence in narrated.sentences:
        cited = extract_event_ids(sentence.text)
        assert cited, f"Sentence with no event citation: {sentence.text}"
        assert cited.issubset(sentence.line.sources), (
            f"LLM cited events not in source: {cited - set(sentence.line.sources)}"
        )


def test_narrate_raises_on_missing_citation() -> None:
    digest = _digest(_line(LineKind.TASKS_COMPLETED, 1.0, "a1"))
    with pytest.raises(NarrateError, match="no event citation"):
        narrate(digest, llm_client=_FixedTextStubLLM("no citation here"))


def test_narrate_raises_on_hallucinated_citation() -> None:
    digest = _digest(_line(LineKind.TASKS_COMPLETED, 1.0, "a1"))
    with pytest.raises(NarrateError, match="not in source"):
        narrate(digest, llm_client=_FixedTextStubLLM("Did it. [evt:not-a-real-id]"))


def test_narrate_raises_on_partial_hallucination() -> None:
    digest = _digest(_line(LineKind.TASKS_COMPLETED, 1.0, "a1"))
    with pytest.raises(NarrateError, match="not in source"):
        narrate(digest, llm_client=_FixedTextStubLLM("Did it. [evt:a1, not-real]"))


def test_narrate_preserves_line_order() -> None:
    digest = _digest(
        _line(LineKind.TASKS_COMPLETED, 2.0, "a1"),
        _line(LineKind.COST_EUR, 1.25, "c1"),
        _line(LineKind.ESCALATIONS, 1.0, "e1"),
    )
    narrated = narrate(digest, llm_client=_EchoStubLLM())
    assert [sentence.line.kind for sentence in narrated.sentences] == [
        line.kind for line in digest.lines
    ]
    assert all(
        narrated.sentences[i].line is digest.lines[i] for i in range(len(digest.lines))
    )


def test_narrate_calls_llm_once_per_line() -> None:
    digest = _digest(
        _line(LineKind.TASKS_COMPLETED, 2.0, "a1"),
        _line(LineKind.COST_EUR, 1.25, "c1"),
    )
    stub = _EchoStubLLM()
    narrate(digest, llm_client=stub)
    assert len(stub.prompts) == len(digest.lines)


def test_narrate_aborts_whole_call_on_first_violation() -> None:
    digest = _digest(
        _line(LineKind.TASKS_COMPLETED, 2.0, "a1"),
        _line(LineKind.COST_EUR, 1.25, "c1"),
    )
    stub = _SequenceStubLLM(["Did it. [evt:a1]", "no citation on this one"])
    with pytest.raises(NarrateError):
        narrate(digest, llm_client=stub)
    assert len(stub.prompts) == 2


def test_narrated_digest_wraps_original_digest() -> None:
    digest = _digest(_line(LineKind.TASKS_COMPLETED, 1.0, "a1"))
    narrated = narrate(digest, llm_client=_EchoStubLLM())
    assert narrated.digest is digest


def test_extract_event_ids_single_bracket() -> None:
    assert extract_event_ids("Did X. [evt:a1, a2]") == {EventId("a1"), EventId("a2")}


def test_extract_event_ids_no_bracket_returns_empty_set() -> None:
    assert extract_event_ids("Did X, no citation.") == set()


def test_extract_event_ids_multiple_brackets_unions() -> None:
    text = "First [evt:a1]. Second [evt:a2, a3]."
    assert extract_event_ids(text) == {EventId("a1"), EventId("a2"), EventId("a3")}


def test_sentence_exposes_line_sources() -> None:
    line = _line(LineKind.TASKS_COMPLETED, 1.0, "a1", "a2")
    sentence = Sentence(text="Did the thing. [evt:a1, a2]", line=line)
    assert sentence.line.sources == (EventId("a1"), EventId("a2"))


def _fake_transport(responses: list[bytes]) -> tuple[list[HTTPRequest], Transport]:
    captured: list[HTTPRequest] = []

    def transport(request: HTTPRequest) -> bytes:
        captured.append(request)
        return responses[len(captured) - 1]

    return captured, transport


def _ok_response(content: str) -> bytes:
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")


@pytest.mark.parametrize("base_url", ["https://api.example.com", "https://api.example.com/"])
def test_openai_client_builds_expected_request(base_url: str) -> None:
    captured, transport = _fake_transport([_ok_response("hello [evt:a1]")])
    client = OpenAICompatibleClient(
        base_url=base_url, api_key="secret", model="gpt-4o-mini", transport=transport
    )
    client.complete("prompt text")

    assert len(captured) == 1
    request = captured[0]
    assert request.url == "https://api.example.com/chat/completions"
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.body) == {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "prompt text"}],
    }


def test_openai_client_parses_response_content() -> None:
    _, transport = _fake_transport([_ok_response("hello [evt:a1]")])
    client = OpenAICompatibleClient(
        base_url="https://api.example.com",
        api_key="secret",
        model="gpt-4o-mini",
        transport=transport,
    )
    assert client.complete("prompt text") == "hello [evt:a1]"


def test_openai_client_raises_narrate_error_on_malformed_json() -> None:
    _, transport = _fake_transport([b"not json"])
    client = OpenAICompatibleClient(
        base_url="https://api.example.com",
        api_key="secret",
        model="gpt-4o-mini",
        transport=transport,
    )
    with pytest.raises(NarrateError, match="not valid JSON"):
        client.complete("prompt text")


def test_openai_client_raises_narrate_error_on_missing_choices() -> None:
    _, transport = _fake_transport([b"{}"])
    client = OpenAICompatibleClient(
        base_url="https://api.example.com",
        api_key="secret",
        model="gpt-4o-mini",
        transport=transport,
    )
    with pytest.raises(NarrateError, match="choices"):
        client.complete("prompt text")


def test_openai_client_used_as_llm_client_in_narrate() -> None:
    digest = _digest(_line(LineKind.TASKS_COMPLETED, 1.0, "a1"))
    _, transport = _fake_transport([_ok_response("Did it. [evt:a1]")])
    client = OpenAICompatibleClient(
        base_url="https://api.example.com",
        api_key="secret",
        model="gpt-4o-mini",
        transport=transport,
    )
    narrated = narrate(digest, llm_client=client)
    assert narrated.sentences[0].text == "Did it. [evt:a1]"
