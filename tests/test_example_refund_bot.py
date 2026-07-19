"""Falsifiable specification for the real refund-bot example (Brique 7).

The example lives in examples/agents/refund_bot/ — a framework-free Claude
tool loop whose traces are emitted directly in the OTLP JSON shape that
`alfred.trace.ingest` reads. These tests drive the loop with a scripted
LLM client (no network, per docs/adr/0006 test philosophy) and prove the
brique's contract: a run's trace is ingestible by Alfred, tool calls carry
the exact attributes `alfred.mandate.engine` reads, and an over-limit
refund decided by the (scripted) model surfaces as a `forbidden_action`
deviation under the stock examples/mandates/refund-bot.yaml mandate.

See docs/adr/0010-brique7-real-agent-example.md.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "examples" / "agents"))

from refund_bot.agent import LLMResponse, run_ticket  # noqa: E402
from refund_bot.tools import load_orders  # noqa: E402
from refund_bot.tracer import TraceRecorder  # noqa: E402

from alfred.mandate.engine import evaluate  # noqa: E402
from alfred.mandate.model import DeviationType  # noqa: E402
from alfred.mandate.yaml_io import load_mandate  # noqa: E402
from alfred.trace.ingest import ingest_otlp_json  # noqa: E402
from alfred.trace.model import SpanKind, TraceEvent  # noqa: E402

MANDATE_PATH = REPO_ROOT / "examples" / "mandates" / "refund-bot.yaml"
SCRIPT_MODEL = "claude-opus-4-8"


class ScriptedClient:
    """LLMClient whose responses are fixed in advance — zero network."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        return self._responses.pop(0)


def _tool_use(tool_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": arguments}


def _response(
    content: list[dict[str, Any]],
    *,
    stop_reason: str = "tool_use",
    input_tokens: int = 900,
    output_tokens: int = 120,
) -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason=stop_reason,
        model=SCRIPT_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _run_scripted_ticket(responses: list[LLMResponse], ticket: dict[str, str]) -> list[TraceEvent]:
    recorder = TraceRecorder(agent="refund-bot-v3")
    run_ticket(ScriptedClient(responses), recorder, ticket, load_orders())
    return ingest_otlp_json(recorder.payload())


def _conform_run() -> list[TraceEvent]:
    """Ticket 1 scenario: legitimate 40 € refund on ORD-1001."""
    responses = [
        _response([_tool_use("tu-1", "read_order", {"order_id": "ORD-1001"})]),
        _response(
            [
                _tool_use("tu-2", "issue_refund", {"order_id": "ORD-1001", "amount_eur": 40.0}),
                _tool_use(
                    "tu-3",
                    "notify_customer",
                    {"order_id": "ORD-1001", "message": "Refund of 40 EUR issued."},
                ),
            ]
        ),
        _response([{"type": "text", "text": "Ticket handled."}], stop_reason="end_turn"),
    ]
    ticket = {"id": "TCK-1", "order_id": "ORD-1001", "message": "Mug arrived broken."}
    return _run_scripted_ticket(responses, ticket)


def _overlimit_run() -> list[TraceEvent]:
    """Ticket 2 scenario: the model grants a 250 € refund (mandate cap: 100 €)."""
    responses = [
        _response([_tool_use("tu-1", "read_order", {"order_id": "ORD-1002"})]),
        _response(
            [_tool_use("tu-2", "issue_refund", {"order_id": "ORD-1002", "amount_eur": 250.0})]
        ),
        _response([{"type": "text", "text": "Full refund issued."}], stop_reason="end_turn"),
    ]
    ticket = {"id": "TCK-2", "order_id": "ORD-1002", "message": "Machine broke, refund me."}
    return _run_scripted_ticket(responses, ticket)


def test_run_emits_ingestible_otlp() -> None:
    events = _conform_run()
    kinds = [event.kind for event in events]
    assert kinds.count(SpanKind.AGENT_TASK) == 1
    assert kinds.count(SpanKind.LLM_CALL) == 3
    assert kinds.count(SpanKind.TOOL_CALL) == 3
    assert len({event.event_id for event in events}) == len(events)
    assert len({event.trace_id for event in events}) == 1
    task = next(event for event in events if event.kind is SpanKind.AGENT_TASK)
    assert task.attributes["gen_ai.agent.name"] == "refund-bot-v3"


def test_issue_refund_span_carries_amount_eur() -> None:
    events = _conform_run()
    refund = next(
        event for event in events if event.attributes.get("gen_ai.tool.name") == "issue_refund"
    )
    assert refund.attributes["tool.arguments.amount_eur"] == 40.0
    assert refund.attributes["tool.result.status"] == "ok"


def test_llm_spans_carry_real_usage() -> None:
    events = _conform_run()
    llm_calls = [event for event in events if event.kind is SpanKind.LLM_CALL]
    for event in llm_calls:
        assert event.attributes["gen_ai.usage.input_tokens"] == 900
        assert event.attributes["gen_ai.usage.output_tokens"] == 120
        assert event.attributes["gen_ai.response.model"] == SCRIPT_MODEL
        cost = event.attributes["gen_ai.usage.cost_eur"]
        assert isinstance(cost, float) and cost > 0.0


def test_overlimit_refund_yields_forbidden_action() -> None:
    events = _overlimit_run()
    mandate = load_mandate(MANDATE_PATH)
    deviations = evaluate(mandate, events)
    assert len(deviations) == 1
    deviation = deviations[0]
    assert deviation.type is DeviationType.FORBIDDEN_ACTION
    refund = next(
        event for event in events if event.attributes.get("gen_ai.tool.name") == "issue_refund"
    )
    assert deviation.event_ids == (refund.event_id,)


def test_conform_run_yields_no_deviations() -> None:
    events = _conform_run()
    mandate = load_mandate(MANDATE_PATH)
    assert evaluate(mandate, events) == []


def test_tool_error_recorded_as_status() -> None:
    responses = [
        _response([_tool_use("tu-1", "read_order", {"order_id": "ORD-9999"})]),
        _response([{"type": "text", "text": "Order not found."}], stop_reason="end_turn"),
    ]
    ticket = {"id": "TCK-9", "order_id": "ORD-9999", "message": "Where is my order?"}
    events = _run_scripted_ticket(responses, ticket)
    tool = next(event for event in events if event.kind is SpanKind.TOOL_CALL)
    assert tool.attributes["tool.result.status"] == "error"
