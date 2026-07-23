"""An OpenAI Agents SDK agent Alfred supervises with zero manual instrumentation.

`expense-bot` is an OpenAI Agents SDK agent: it calls the model, which decides to
approve an expense (one tool call), then answers. We register
`AlfredTracingProcessor` once and nothing else — the SDK's own tracing becomes an
Alfred trace. A real `OpenAIChatCompletionsModel` is wired to a fake `AsyncOpenAI`
client (an `httpx.MockTransport` returning canned responses), so the example runs
with no API key and no network; swap in a real client unchanged in production.

The approved amount (250 €) is over the mandate's 100 € cap, so `alfred watch`
raises a `forbidden_action` deviation — anchored to the tool call's event ID,
never self-reported.

    pip install alfred-ai[openai-agents]
    python examples/agents/openai_agents_bot/agent.py   # → traces/expense-bot-<ts>.json
    alfred init demo --agent expense-bot
    cp examples/agents/openai_agents_bot/mandate.yaml demo/mandate.yaml
    alfred watch traces/ --project demo

Falsifiable contract in tests/test_integration_openai_agents.py (docs/adr/0021).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from agents import Agent, Runner, function_tool, set_trace_processors
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from alfred.instrument import AgentTracer
from alfred.integrations.openai_agents import AlfredTracingProcessor

AGENT_NAME = "expense-bot"
AMOUNT_EUR = 250.0  # over the mandate's 100 € cap → a forbidden_action


@function_tool
def approve_expense(request_id: str, amount_eur: float) -> str:
    """Approve an expense request."""
    return f"approved {request_id} for {amount_eur} EUR"


def _fake_model() -> OpenAIChatCompletionsModel:
    """A real Chat Completions model over a mock transport — no network, no key.

    In production, drop the `http_client` argument and set `OPENAI_API_KEY`, or
    pass any real model; the connector is unchanged.
    """
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "approve_expense",
                            "arguments": json.dumps(
                                {"request_id": "REQ-3", "amount_eur": AMOUNT_EUR}
                            ),
                        },
                    }
                ],
            }
        else:
            message = {"role": "assistant", "content": "Approved the expense."}
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


def run(traces_dir: str | Path = "traces") -> Path:
    """Run the agent with Alfred attached, then write the trace file."""
    agent = Agent(
        name=AGENT_NAME,
        instructions="Approve the expense request.",
        tools=[approve_expense],
        model=_fake_model(),
    )
    tracer = AgentTracer(agent=AGENT_NAME, traces_dir=traces_dir)
    set_trace_processors([AlfredTracingProcessor(tracer)])
    Runner.run_sync(agent, "Please approve REQ-3.")
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
