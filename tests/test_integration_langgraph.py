"""Falsifiable specification for the native LangGraph connector (docs/adr/0014).

`alfred.integrations.langgraph.AlfredCallbackHandler` turns a LangGraph run into
an Alfred OTLP trace with no manual instrumentation. These tests drive a real
`StateGraph` with a deterministic fake chat model (no network, per ADR 0006 test
philosophy) and prove the brique's contract: the run's trace is ingestible, tool
calls carry the exact attributes `alfred.mandate.engine` reads, LLM usage is
propagated, an over-limit approval surfaces as a `forbidden_action` deviation,
and every digest line stays anchored to a real event ID.

Requires the `[langgraph]` extra (installed via `pip install -e ".[dev]"`).
"""

from __future__ import annotations

import operator
from datetime import date
from typing import Annotated, TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

from alfred.instrument import AgentTracer
from alfred.integrations.langgraph import AlfredCallbackHandler
from alfred.mandate.engine import evaluate
from alfred.mandate.model import DeviationType, Mandate
from alfred.report.build import build_digest
from alfred.trace.ingest import ingest_otlp_json
from alfred.trace.model import SpanKind, TraceEvent

AGENT = "expense-bot"


class State(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


@tool
def approve_expense(request_id: str, amount_eur: float) -> str:
    """Approve an expense request."""
    return f"approved {request_id}"


@tool
def failing_tool(reason: str) -> str:
    """A tool that always fails."""
    raise ValueError("smtp down")


def _fake_model() -> GenericFakeChatModel:
    reply = AIMessage(
        content="ok",
        usage_metadata={"input_tokens": 900, "output_tokens": 120, "total_tokens": 1020},
    )
    return GenericFakeChatModel(messages=iter([reply]))


def _run(amount_eur: float = 40.0, *, fail_tool: bool = False) -> list[TraceEvent]:
    model = _fake_model()

    def think(state: State, config: RunnableConfig) -> dict[str, list[BaseMessage]]:
        return {"messages": [model.invoke("go", config=config)]}

    def act(state: State, config: RunnableConfig) -> dict[str, list[BaseMessage]]:
        if fail_tool:
            failing_tool.invoke({"reason": "x"}, config=config)
        else:
            approve_expense.invoke(
                {"request_id": "REQ-1", "amount_eur": amount_eur}, config=config
            )
        return {"messages": []}

    graph = StateGraph(State)
    graph.add_node("think", think)
    graph.add_node("act", act)
    graph.add_edge(START, "think")
    graph.add_edge("think", "act")
    graph.add_edge("act", END)
    app = graph.compile()

    tracer = AgentTracer(agent=AGENT)
    handler = AlfredCallbackHandler(tracer, raise_errors=True)
    if fail_tool:
        with pytest.raises(ValueError, match="smtp down"):
            app.invoke({"messages": []}, config={"callbacks": [handler]})
    else:
        app.invoke({"messages": []}, config={"callbacks": [handler]})
    return ingest_otlp_json(tracer.payload())


def _mandate(*, forbidden: tuple[str, ...] = ()) -> Mandate:
    return Mandate(
        agent=AGENT,
        allowed_tools=frozenset({"approve_expense"}),
        daily_budget_eur=5.0,
        forbidden_actions=forbidden,
        escalate_when=(),
    )


def test_graph_run_ingests() -> None:
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


def test_digest_from_graph_trace_anchored() -> None:
    events = _run(amount_eur=40.0)
    digest = build_digest(_mandate(), events, date(2026, 7, 21))
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
