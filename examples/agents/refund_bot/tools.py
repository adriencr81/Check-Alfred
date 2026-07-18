"""The refund-bot's three tools, executed on local fake order data.

The *data* is fake (orders.json); the *execution* is real — the model
decides which tool to call with which arguments, and the outcome
(including errors) is whatever actually happened here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ORDERS_PATH = Path(__file__).parent / "orders.json"

Order = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """What a tool execution actually did: `status` is "ok" or "error"."""

    status: str
    content: str


def load_orders(path: Path | None = None) -> dict[str, Order]:
    raw = json.loads((path or _ORDERS_PATH).read_text(encoding="utf-8"))
    return dict(raw)


def _read_order(orders: dict[str, Order], arguments: dict[str, Any]) -> ToolOutcome:
    order = orders.get(str(arguments.get("order_id")))
    if order is None:
        return ToolOutcome("error", f"No order found with id {arguments.get('order_id')!r}.")
    return ToolOutcome("ok", json.dumps(order))


def _issue_refund(orders: dict[str, Order], arguments: dict[str, Any]) -> ToolOutcome:
    order = orders.get(str(arguments.get("order_id")))
    amount = arguments.get("amount_eur")
    if order is None:
        return ToolOutcome("error", f"No order found with id {arguments.get('order_id')!r}.")
    if not isinstance(amount, int | float) or amount <= 0:
        return ToolOutcome("error", "amount_eur must be a positive number.")
    order["refunded_eur"] = float(order["refunded_eur"]) + float(amount)
    return ToolOutcome(
        "ok", f"Refund of {float(amount):.2f} EUR issued on {order['order_id']}."
    )


def _notify_customer(orders: dict[str, Order], arguments: dict[str, Any]) -> ToolOutcome:
    order = orders.get(str(arguments.get("order_id")))
    if order is None:
        return ToolOutcome("error", f"No order found with id {arguments.get('order_id')!r}.")
    return ToolOutcome("ok", f"Message sent to {order['customer']}.")


_HANDLERS = {
    "read_order": _read_order,
    "issue_refund": _issue_refund,
    "notify_customer": _notify_customer,
}


def execute(name: str, arguments: dict[str, Any], orders: dict[str, Order]) -> ToolOutcome:
    handler = _HANDLERS.get(name)
    if handler is None:
        return ToolOutcome("error", f"Unknown tool {name!r}.")
    return handler(orders, arguments)
