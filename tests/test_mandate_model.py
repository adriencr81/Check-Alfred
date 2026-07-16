"""Mandate + Deviation invariants — the anchor contract for deviations."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from alfred.mandate.model import Deviation, DeviationType, EscalationRule, Mandate
from alfred.trace.model import EventId


def _mandate() -> Mandate:
    return Mandate(
        agent="refund-bot-v3",
        allowed_tools=frozenset({"read_order", "issue_refund", "notify_customer"}),
        daily_budget_eur=5.0,
        forbidden_actions=("issue_refund_above_100_eur", "send_marketing"),
        escalate_when=(EscalationRule("tool_error_rate", ">", 0.10),),
    )


def test_mandates_with_same_fields_are_equal() -> None:
    assert _mandate() == _mandate()


def test_mandate_is_immutable() -> None:
    mandate = _mandate()
    with pytest.raises(FrozenInstanceError):
        mandate.agent = "other-bot"  # type: ignore[misc]


def test_deviation_requires_at_least_one_event_id() -> None:
    """A deviation without an anchor is a bug to intercept, not data to accept."""
    with pytest.raises(ValueError, match="event_id"):
        Deviation(type=DeviationType.TOOL_NOT_ALLOWED, event_ids=(), message="x")


def test_deviation_carries_its_event_ids() -> None:
    deviation = Deviation(
        type=DeviationType.TOOL_NOT_ALLOWED,
        event_ids=(EventId("e1"),),
        message="tool 'read_pii' is not in allowed_tools",
    )
    assert deviation.event_ids == (EventId("e1"),)
