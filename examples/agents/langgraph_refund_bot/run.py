"""The Brique 7 refund scenario, rebuilt on LangGraph and instrumented by a
THIRD-PARTY OTel instrumentor (opentelemetry-instrumentation-langchain).

Alfred never sees this code — it only reads the OTLP JSON file the
instrumentor's spans are exported to. That is the point of the example:
the trace attributes are whatever OpenLLMetry emits, not what we control.

Usage (needs an ANTHROPIC_API_KEY):

    pip install langgraph langchain-anthropic opentelemetry-sdk \\
        opentelemetry-instrumentation-langchain
    python examples/agents/langgraph_refund_bot/run.py \\
        [--model claude-opus-4-8] [--out traces]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from refund_bot.agent import SYSTEM_PROMPT
from refund_bot.tools import execute, load_orders

_TICKETS_PATH = Path(__file__).parent.parent / "refund_bot" / "tickets.json"
DEFAULT_MODEL = "claude-opus-4-8"
SERVICE_NAME = "langgraph-refund-bot"


def build_tools(orders: dict[str, Any]) -> list[Any]:
    """The same three tools as the Brique 7 refund-bot, as LangChain tools.

    Errors raise so the instrumentor records them (`gen_ai.task.status`).
    """
    from langchain_core.tools import tool

    def _run(name: str, arguments: dict[str, Any]) -> str:
        outcome = execute(name, arguments, orders)
        if outcome.status != "ok":
            raise ValueError(outcome.content)
        return outcome.content

    @tool
    def read_order(order_id: str) -> str:
        """Look up an order by id. Call this first for every ticket."""
        return _run("read_order", {"order_id": order_id})

    @tool
    def issue_refund(order_id: str, amount_eur: float) -> str:
        """Refund an amount in euros on an order."""
        return _run("issue_refund", {"order_id": order_id, "amount_eur": amount_eur})

    @tool
    def notify_customer(order_id: str, message: str) -> str:
        """Send a short message to the customer who opened the ticket."""
        return _run("notify_customer", {"order_id": order_id, "message": message})

    return [read_order, issue_refund, notify_customer]


def setup_tracing(trace_path: Path) -> Any:
    """Global OTel provider + file exporter + third-party instrumentor."""
    from opentelemetry import trace
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    from langgraph_refund_bot.otlp_file import OTLPJsonFileExporter

    provider = TracerProvider()
    provider.add_span_processor(
        SimpleSpanProcessor(OTLPJsonFileExporter(trace_path, service_name=SERVICE_NAME))
    )
    trace.set_tracer_provider(provider)
    LangchainInstrumentor().instrument(tracer_provider=provider)
    return provider


def build_agent(model: Any, orders: dict[str, Any]) -> Any:
    from langgraph.prebuilt import create_react_agent

    return create_react_agent(model, build_tools(orders), prompt=SYSTEM_PROMPT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", default="traces", help="Directory for the OTLP JSON trace")
    args = parser.parse_args(argv)

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    trace_path = Path(args.out) / f"langgraph-refund-bot-{stamp}.json"
    provider = setup_tracing(trace_path)

    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:  # pragma: no cover - depends on local env
        raise SystemExit(
            "Missing example dependencies: pip install langgraph langchain-anthropic "
            "opentelemetry-sdk opentelemetry-instrumentation-langchain"
        ) from exc

    orders = load_orders()
    agent = build_agent(ChatAnthropic(model=args.model), orders)
    tickets = json.loads(_TICKETS_PATH.read_text(encoding="utf-8"))

    for ticket in tickets:
        print(f"Handling {ticket['id']} (order {ticket['order_id']})...")
        prompt = (
            f"Ticket {ticket['id']} concerning order {ticket['order_id']}:\n"
            f"{ticket['message']}"
        )
        result = agent.invoke({"messages": [("user", prompt)]})
        print("  →", result["messages"][-1].content)

    provider.force_flush()
    provider.shutdown()

    print(f"\nTrace written to {trace_path}")
    print("Now let Alfred verify what the agent actually did:")
    print("  alfred init demo-project --agent refund-bot-v3")
    print("  cp examples/mandates/refund-bot.yaml demo-project/mandate.yaml")
    print(f"  alfred watch {args.out}/ --project demo-project")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
