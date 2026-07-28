"""Falsifiable specification for the native OpenAI Agents SDK connector (docs/adr/0021).

`alfred.integrations.openai_agents.AlfredTracingProcessor` turns an OpenAI Agents
SDK run into an Alfred OTLP trace with no manual instrumentation. These tests
drive a real `Runner.run_sync` with a real `OpenAIChatCompletionsModel` wired to
a fake `AsyncOpenAI` client (an `httpx.MockTransport` returning canned responses,
so there is no network and no API key, per ADR 0006 test philosophy) and prove
the brique's contract: the run's trace is ingestible, tool calls carry the exact
attributes `alfred.mandate.engine` reads, LLM usage is propagated, a failing tool
surfaces as a `tool.result.status: error`, an over-limit approval surfaces as a
`forbidden_action` deviation, and every digest line stays anchored to a real
event ID.

Requires the `[openai-agents]` extra (installed via `pip install -e ".[dev]"`).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date

import httpx
import pytest
from agents import Agent, Runner, function_tool
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.tracing import set_trace_processors
from openai import AsyncOpenAI

from alfred.instrument import AgentTracer
from alfred.integrations.openai_agents import AlfredTracingProcessor
from alfred.mandate.engine import evaluate
from alfred.mandate.model import DeviationType, Mandate
from alfred.report.build import build_digest
from alfred.trace.ingest import ingest_otlp_json
from alfred.trace.model import SpanKind, TraceEvent

AGENT = "expense-bot"


@function_tool
def approve_expense(request_id: str, amount_eur: float) -> str:
    """Approve an expense request."""
    return f"approved {request_id}"


@function_tool
def failing_tool(reason: str) -> str:
    """A tool that always fails."""
    raise ValueError("smtp down")


def _fake_model(amount_eur: float, *, fail_tool: bool) -> OpenAIChatCompletionsModel:
    """A real Chat Completions model over a mock transport: no network, no key.

    First call returns a tool call (the SDK creates a real generation span with
    usage, then a real function span); the second returns the final answer.
    """
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            name, arguments = (
                ("failing_tool", {"reason": "x"})
                if fail_tool
                else ("approve_expense", {"request_id": "REQ-1", "amount_eur": amount_eur})
            )
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }
                ],
            }
        else:
            message = {"role": "assistant", "content": "done"}
        body = {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o-mini",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 120, "total_tokens": 1020},
        }
        return httpx.Response(200, json=body)

    client = AsyncOpenAI(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return OpenAIChatCompletionsModel(model="gpt-4o-mini", openai_client=client)


def _run(amount_eur: float = 40.0, *, fail_tool: bool = False) -> list[TraceEvent]:
    agent = Agent(
        name=AGENT,
        instructions="Approve the expense.",
        tools=[approve_expense, failing_tool],
        model=_fake_model(amount_eur, fail_tool=fail_tool),
    )
    tracer = AgentTracer(agent=AGENT)
    set_trace_processors([AlfredTracingProcessor(tracer, raise_errors=True)])
    try:
        # A failing tool is non-fatal in this SDK: the run completes normally.
        Runner.run_sync(agent, "Please approve REQ-1.")
    finally:
        set_trace_processors([])
    return ingest_otlp_json(tracer.payload())


def _mandate(*, forbidden: tuple[str, ...] = ()) -> Mandate:
    return Mandate(
        agent=AGENT,
        allowed_tools=frozenset({"approve_expense"}),
        daily_budget_eur=5.0,
        forbidden_actions=forbidden,
        escalate_when=(),
    )


def test_run_ingests() -> None:
    events = _run()
    kinds = [event.kind for event in events]
    assert kinds.count(SpanKind.AGENT_TASK) == 1
    assert kinds.count(SpanKind.LLM_CALL) >= 1
    assert kinds.count(SpanKind.TOOL_CALL) >= 1
    assert len({event.event_id for event in events}) == len(events)
    assert len({event.trace_id for event in events}) == 1

    task = next(event for event in events if event.kind is SpanKind.AGENT_TASK)
    assert task.attributes["gen_ai.agent.name"] == AGENT
    for event in events:
        if event is not task:
            assert event.parent_span_id == task.event_id
            assert task.start_time <= event.start_time
            assert event.end_time <= task.end_time


def test_tool_arguments_flattened() -> None:
    events = _run(amount_eur=250.0)
    tool_event = next(event for event in events if event.kind is SpanKind.TOOL_CALL)
    assert tool_event.attributes["gen_ai.tool.name"] == "approve_expense"
    assert tool_event.attributes["tool.arguments.amount_eur"] == 250.0
    assert tool_event.attributes["tool.arguments.request_id"] == "REQ-1"
    assert tool_event.attributes["tool.result.status"] == "ok"


def test_tool_error_recorded_as_status() -> None:
    events = _run(fail_tool=True)
    tool_event = next(event for event in events if event.kind is SpanKind.TOOL_CALL)
    assert tool_event.attributes["tool.result.status"] == "error"


def test_llm_usage_propagated() -> None:
    events = _run()
    llm_event = next(event for event in events if event.kind is SpanKind.LLM_CALL)
    assert llm_event.attributes["gen_ai.usage.input_tokens"] == 900
    assert llm_event.attributes["gen_ai.usage.output_tokens"] == 120


def test_digest_from_trace_anchored() -> None:
    events = _run(amount_eur=40.0)
    digest = build_digest(_mandate(), events, date(2026, 7, 23))
    assert digest.lines
    event_ids = {event.event_id for event in events}
    for line in digest.lines:
        assert line.sources
        assert set(line.sources) <= event_ids


def test_overlimit_yields_forbidden_action() -> None:
    events = _run(amount_eur=250.0)
    mandate = _mandate(forbidden=("approve_expense_above_100_eur",))
    deviations = evaluate(mandate, events)
    assert len(deviations) == 1
    deviation = deviations[0]
    assert deviation.type is DeviationType.FORBIDDEN_ACTION
    tool_event = next(event for event in events if event.kind is SpanKind.TOOL_CALL)
    assert deviation.event_ids == (tool_event.event_id,)


def test_conform_run_yields_no_deviations() -> None:
    events = _run(amount_eur=40.0)
    assert evaluate(_mandate(forbidden=("approve_expense_above_100_eur",)), events) == []


@pytest.fixture(autouse=True)
def _reset_trace_processors() -> Iterator[None]:
    """Never leave Alfred's processor on the SDK's global registry between tests."""
    yield
    set_trace_processors([])
