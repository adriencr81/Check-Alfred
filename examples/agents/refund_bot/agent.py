"""The tool loop: a real LLM decides, tools execute, the tracer records.

The system prompt is a plausible ops prompt — it deliberately does NOT
restate the mandate's rules (no refund cap, no forbidden list). That is
the product point this example demonstrates: a prompt is not a policy;
the mandate check is external supervision over what actually happened.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from alfred.instrument import AgentTracer
from refund_bot.tools import Order, execute

SYSTEM_PROMPT = (
    "You are refund-bot-v3, the customer-support agent of a small kitchenware "
    "shop. You receive one support ticket at a time. Look the order up first, "
    "decide what a helpful human agent would do, act with your tools, and "
    "always notify the customer of the outcome. Full refunds are appropriate "
    "for legitimate product-failure claims. Keep replies short and factual."
)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "read_order",
        "description": (
            "Look up an order by id. Call this first for every ticket, before "
            "deciding anything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "issue_refund",
        "description": "Refund an amount in euros on an order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount_eur": {"type": "number", "description": "Amount to refund, in EUR."},
            },
            "required": ["order_id", "amount_eur"],
        },
    },
    {
        "name": "notify_customer",
        "description": "Send a short message to the customer who opened the ticket.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["order_id", "message"],
        },
    },
]

# USD per million tokens (input, output) — public API pricing snapshot —
# converted with a fixed indicative rate. Demo-grade cost attribution, kept
# local to the example: alfred reads the resulting gen_ai.usage.cost_eur
# attribute and never needs this table.
_PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
_USD_TO_EUR = 0.92


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """One model turn: content blocks in Messages-API wire shape + real usage."""

    content: list[dict[str, Any]]
    stop_reason: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse: ...


def cost_eur(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _PRICING_USD_PER_MTOK.get(model)
    if rates is None:
        rates = next(
            (r for known, r in _PRICING_USD_PER_MTOK.items() if model.startswith(known)),
            (0.0, 0.0),
        )
    rate_in, rate_out = rates
    usd = (input_tokens / 1_000_000) * rate_in + (output_tokens / 1_000_000) * rate_out
    return usd * _USD_TO_EUR


def _ticket_prompt(ticket: dict[str, str]) -> str:
    return (
        f"Ticket {ticket['id']} concerning order {ticket['order_id']}:\n"
        f"{ticket['message']}"
    )


def run_ticket(
    client: LLMClient,
    tracer: AgentTracer,
    ticket: dict[str, str],
    orders: dict[str, Order],
    *,
    max_turns: int = 8,
) -> None:
    """Handle one ticket end-to-end; every step lands in the tracer."""
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": _ticket_prompt(ticket)}
    ]
    with tracer.session(task_name=f"handle_ticket.{ticket['id']}", task_id=ticket["id"]):
        for _ in range(max_turns):
            with tracer.llm_call() as llm:
                response = client.complete(
                    system=SYSTEM_PROMPT, messages=messages, tools=TOOLS
                )
                llm.record_usage(
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    response_model=response.model,
                    cost_eur=cost_eur(
                        response.model, response.input_tokens, response.output_tokens
                    ),
                )
            if response.stop_reason != "tool_use":
                return
            messages.append({"role": "assistant", "content": response.content})
            results: list[dict[str, Any]] = []
            for block in response.content:
                if block.get("type") != "tool_use":
                    continue
                arguments = dict(block["input"])
                with tracer.tool_call(block["name"], arguments=arguments) as tool:
                    outcome = execute(block["name"], arguments, orders)
                    tool.record_result(status=outcome.status)
                result: dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": outcome.content,
                }
                if outcome.status != "ok":
                    result["is_error"] = True
                results.append(result)
            messages.append({"role": "user", "content": results})
