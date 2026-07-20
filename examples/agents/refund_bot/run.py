"""Run the real refund-bot against the Anthropic API and write an OTLP trace.

Usage (needs the `anthropic` package and an ANTHROPIC_API_KEY):

    pip install anthropic
    python examples/agents/refund_bot/run.py [--model claude-opus-4-8] [--out traces]

Then verify the run with Alfred (see README.md in this directory).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alfred.instrument import AgentTracer
from refund_bot.agent import LLMResponse, run_ticket
from refund_bot.tools import load_orders

_TICKETS_PATH = Path(__file__).parent / "tickets.json"
AGENT_NAME = "refund-bot-v3"
DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicClient:
    """Adapts the Anthropic SDK to the example's LLMClient protocol."""

    def __init__(self, model: str) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise SystemExit(
                "The `anthropic` package is required for a real run: pip install anthropic"
            ) from exc
        self._client = anthropic.Anthropic()
        self._model = model

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
        )
        content: list[dict[str, Any]] = []
        for block in response.content:
            if block.type == "text":
                content.append({"type": "text", "text": str(block.text)})
            elif block.type == "tool_use":
                content.append(
                    {
                        "type": "tool_use",
                        "id": str(block.id),
                        "name": str(block.name),
                        "input": dict(block.input),
                    }
                )
        for block in content:
            if block["type"] == "text" and block["text"].strip():
                print(f"    agent: {block['text'].strip()}")
            elif block["type"] == "tool_use":
                arguments = ", ".join(f"{k}={v}" for k, v in block["input"].items())
                print(f"    -> {block['name']}({arguments})")
        return LLMResponse(
            content=content,
            stop_reason=str(response.stop_reason),
            model=str(response.model),
            input_tokens=int(response.usage.input_tokens),
            output_tokens=int(response.usage.output_tokens),
        )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", default="traces", help="Directory for the OTLP JSON trace")
    args = parser.parse_args(argv)

    client = AnthropicClient(args.model)
    orders = load_orders()
    tickets = json.loads(_TICKETS_PATH.read_text(encoding="utf-8"))
    tracer = AgentTracer(agent=AGENT_NAME, traces_dir=args.out)

    for ticket in tickets:
        print(f"Handling {ticket['id']} (order {ticket['order_id']})...")
        run_ticket(client, tracer, ticket, orders)

    trace_path = tracer.flush()

    print(f"\nTrace written to {trace_path}")
    print("Now let Alfred verify what the agent actually did:")
    print("  alfred init demo-project --agent refund-bot-v3")
    print("  cp examples/mandates/refund-bot.yaml demo-project/mandate.yaml")
    print(f"  alfred watch {args.out}/ --project demo-project")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
