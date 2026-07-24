"""Falsifiable spec for token-priced cost of the multi-provider pricing table.

Brique — multi-provider cost. The pricing table in alfred.trace.cost only
knew a few OpenAI models, so an agent whose trace carries token counts but no
`gen_ai.usage.cost_eur` had its budget computed as 0.0 in silence — the exact
gap the S1 audit flagged. These tests pin the per-model rate the engine and
the digest both read through event_cost_eur, across Anthropic, OpenAI and
Google.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alfred.trace.cost import contributing_costs, event_cost_eur
from alfred.trace.model import EventId, SpanKind, TraceEvent

# (model, rate_in, rate_out) in the table's unit: currency per 1K tokens.
CLAUDE_RATES = [
    ("claude-opus-4-8", 0.005, 0.025),
    ("claude-opus-4-7", 0.005, 0.025),
    ("claude-opus-4-6", 0.005, 0.025),
    ("claude-sonnet-5", 0.003, 0.015),
    ("claude-sonnet-4-6", 0.003, 0.015),
    ("claude-haiku-4-5", 0.001, 0.005),
    ("claude-fable-5", 0.010, 0.050),
]

# OpenAI GPT-5.6 family (developers.openai.com); gpt-5.6 aliases to Sol.
OPENAI_RATES = [
    ("gpt-5.6-sol", 0.005, 0.030),
    ("gpt-5.6", 0.005, 0.030),
    ("gpt-5.6-terra", 0.0025, 0.015),
    ("gpt-5.6-luna", 0.001, 0.006),
]

# Google Gemini (ai.google.dev); flat under-200k rate, no context tiering here.
GEMINI_RATES = [
    ("gemini-3.1-pro-preview", 0.002, 0.012),
    ("gemini-3.5-flash", 0.0015, 0.009),
    ("gemini-3-flash-preview", 0.0005, 0.003),
    ("gemini-3.1-flash-lite", 0.00025, 0.0015),
]


def _llm_event(model: str, input_tokens: int, output_tokens: int) -> TraceEvent:
    return TraceEvent(
        event_id=EventId("e1"),
        trace_id="trace-1",
        parent_span_id=None,
        kind=SpanKind.LLM_CALL,
        name="chat",
        start_time=datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 21, 12, 0, 1, tzinfo=UTC),
        attributes={
            "gen_ai.response.model": model,
            "gen_ai.usage.input_tokens": input_tokens,
            "gen_ai.usage.output_tokens": output_tokens,
        },
    )


@pytest.mark.parametrize(("model", "rate_in", "rate_out"), CLAUDE_RATES)
def test_claude_model_priced_from_tokens(model: str, rate_in: float, rate_out: float) -> None:
    event = _llm_event(model, input_tokens=1000, output_tokens=500)
    expected = (1000 / 1000) * rate_in + (500 / 1000) * rate_out
    assert event_cost_eur(event) == pytest.approx(expected)


@pytest.mark.parametrize(("model", "rate_in", "rate_out"), OPENAI_RATES + GEMINI_RATES)
def test_openai_and_gemini_model_priced_from_tokens(
    model: str, rate_in: float, rate_out: float
) -> None:
    event = _llm_event(model, input_tokens=1000, output_tokens=500)
    expected = (1000 / 1000) * rate_in + (500 / 1000) * rate_out
    assert event_cost_eur(event) == pytest.approx(expected)


def test_explicit_cost_still_wins_over_claude_table() -> None:
    event = _llm_event("claude-opus-4-8", input_tokens=1000, output_tokens=500)
    event.attributes["gen_ai.usage.cost_eur"] = 0.99
    assert event_cost_eur(event) == pytest.approx(0.99)


def _free_event(event_id: str) -> TraceEvent:
    """A span with no priced tokens and no explicit cost — contributes 0.0."""
    return TraceEvent(
        event_id=EventId(event_id),
        trace_id="trace-1",
        parent_span_id=None,
        kind=SpanKind.TOOL_CALL,
        name="execute_tool",
        start_time=datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 21, 12, 0, 1, tzinfo=UTC),
        attributes={"gen_ai.tool.name": "read_order"},
    )


def test_contributing_costs_keeps_only_positive_cost_events() -> None:
    priced = _llm_event("claude-opus-4-8", input_tokens=1000, output_tokens=500)
    free = _free_event("t1")
    contributing = contributing_costs([priced, free])
    assert [event.event_id for event, _ in contributing] == ["e1"]
    assert contributing[0][1] == pytest.approx(event_cost_eur(priced))


def test_contributing_costs_empty_when_nothing_priced() -> None:
    assert contributing_costs([_free_event("t1"), _free_event("t2")]) == []
