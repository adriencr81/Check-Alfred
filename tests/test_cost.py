"""alfred.cost — the single cost definition shared by digest and mandate engine.

Falsifiable spec for docs/plan-simplification-prod.md S1 (bug B2): before
the fix, an event priced via the token fallback appeared in the digest's
Cost line but was invisible to the budget check.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from alfred.cost import event_cost_eur
from alfred.mandate.engine import evaluate
from alfred.mandate.model import Mandate
from alfred.report.build import build_digest
from alfred.report.model import LineKind
from alfred.trace.model import EventId, SpanKind, TraceEvent


def _event(event_id: str, attributes: dict[str, object]) -> TraceEvent:
    return TraceEvent(
        event_id=EventId(event_id),
        trace_id="trace-1",
        parent_span_id=None,
        kind=SpanKind.LLM_CALL,
        name="chat",
        start_time=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 12, 0, 1, tzinfo=UTC),
        attributes=attributes,
    )


def test_explicit_cost_attribute_wins_over_tokens() -> None:
    event = _event(
        "e1",
        {
            "gen_ai.usage.cost_eur": 2.0,
            "gen_ai.response.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 1000,
            "gen_ai.usage.output_tokens": 1000,
        },
    )
    assert event_cost_eur(event) == pytest.approx(2.0)


def test_token_fallback_uses_pricing_table() -> None:
    event = _event(
        "e1",
        {
            "gen_ai.response.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 1000,
            "gen_ai.usage.output_tokens": 200,
        },
    )
    assert event_cost_eur(event) == pytest.approx(0.00015 + 0.2 * 0.00060)


def test_unknown_model_without_cost_attribute_is_zero() -> None:
    event = _event(
        "e1",
        {
            "gen_ai.response.model": "some-unknown-model",
            "gen_ai.usage.input_tokens": 1000,
            "gen_ai.usage.output_tokens": 200,
        },
    )
    assert event_cost_eur(event) == 0.0


def test_budget_check_sees_the_same_cost_as_the_digest_line() -> None:
    """B2 regression: token-priced spend must count toward the budget.

    gpt-4o at 100k in / 100k out ≈ 1.25 € — no explicit cost_eur attribute.
    With a 1 € budget, the digest's Cost line and a budget_exceeded
    deviation must both exist and carry the same amount.
    """
    events = [
        _event(
            "e1",
            {
                "gen_ai.response.model": "gpt-4o",
                "gen_ai.usage.input_tokens": 100_000,
                "gen_ai.usage.output_tokens": 100_000,
            },
        )
    ]
    mandate = Mandate(
        agent="refund-bot-v3",
        allowed_tools=frozenset(),
        daily_budget_eur=1.0,
        forbidden_actions=(),
        escalate_when=(),
    )

    digest = build_digest(mandate, events, date(2026, 8, 30))
    cost_lines = [line for line in digest.lines if line.kind is LineKind.COST_EUR]
    assert len(cost_lines) == 1

    deviations = evaluate(mandate, events)
    budget_deviations = [d for d in deviations if d.type.value == "budget_exceeded"]
    assert len(budget_deviations) == 1
    assert budget_deviations[0].details["cost_eur"] == pytest.approx(cost_lines[0].value)
    assert budget_deviations[0].event_ids == cost_lines[0].sources
