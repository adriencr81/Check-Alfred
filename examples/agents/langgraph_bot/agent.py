"""A LangGraph agent Alfred supervises with zero manual instrumentation.

`expense-bot` is a two-node LangGraph graph: it "thinks" (one model call) then
approves an expense (one tool call). We attach `AlfredCallbackHandler` to the
invocation and nothing else — the graph's own callbacks become an Alfred trace.
A deterministic fake chat model stands in for a real LLM so the example needs no
API key; swap in `ChatAnthropic`/`ChatOpenAI` unchanged in production.

The approved amount (250 €) is over the mandate's 100 € cap, so `alfred watch`
raises a `forbidden_action` deviation — anchored to the tool call's event ID,
never self-reported.

    pip install alfred-ai[langgraph]
    python examples/agents/langgraph_bot/agent.py   # → traces/expense-bot-<ts>.json
    alfred init demo --agent expense-bot
    cp examples/agents/langgraph_bot/mandate.yaml demo/mandate.yaml
    alfred watch traces/ --project demo

Falsifiable contract in tests/test_integration_langgraph.py (docs/adr/0014).
"""

from __future__ import annotations

import operator
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

from alfred.instrument import AgentTracer
from alfred.integrations.langgraph import AlfredCallbackHandler

AGENT_NAME = "expense-bot"
AMOUNT_EUR = 250.0  # over the mandate's 100 € cap → a forbidden_action


class State(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


@tool
def approve_expense(request_id: str, amount_eur: float) -> str:
    """Approve an expense request."""
    return f"approved {request_id} for {amount_eur} EUR"


def _fake_model() -> GenericFakeChatModel:
    """A deterministic stand-in for a real chat model — no network, no API key."""
    reply = AIMessage(
        content="Approving the expense.",
        usage_metadata={"input_tokens": 900, "output_tokens": 120, "total_tokens": 1020},
    )
    return GenericFakeChatModel(messages=iter([reply]))


def build_graph() -> Any:
    """A minimal think → act graph. Returns the compiled LangGraph app."""
    model = _fake_model()

    def think(state: State, config: RunnableConfig) -> dict[str, list[BaseMessage]]:
        return {"messages": [model.invoke("Handle the expense request.", config=config)]}

    def act(state: State, config: RunnableConfig) -> dict[str, list[BaseMessage]]:
        approve_expense.invoke(
            {"request_id": "REQ-3", "amount_eur": AMOUNT_EUR}, config=config
        )
        return {"messages": []}

    graph = StateGraph(State)
    graph.add_node("think", think)
    graph.add_node("act", act)
    graph.add_edge(START, "think")
    graph.add_edge("think", "act")
    graph.add_edge("act", END)
    return graph.compile()


def run(traces_dir: str | Path = "traces") -> Path:
    """Invoke the graph with Alfred attached, then write the trace file."""
    tracer = AgentTracer(agent=AGENT_NAME, traces_dir=traces_dir)
    handler = AlfredCallbackHandler(tracer)
    build_graph().invoke({"messages": []}, config={"callbacks": [handler]})
    return tracer.flush()


def main() -> None:
    trace_path = run()
    print(f"Trace written to {trace_path}")
    print("Now let Alfred verify what the agent actually did:")
    print(f"  alfred init demo --agent {AGENT_NAME}")
    print(f"  cp {Path(__file__).parent / 'mandate.yaml'} demo/mandate.yaml")
    print("  alfred watch traces/ --project demo")


if __name__ == "__main__":
    main()
