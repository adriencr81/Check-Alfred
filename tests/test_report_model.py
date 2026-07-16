"""Digest + Line invariants — the anchor contract for report lines."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from alfred.report.model import Digest, Line, LineKind
from alfred.trace.model import EventId


def test_line_requires_at_least_one_event_id() -> None:
    """A line without an anchor is a bug to intercept, not data to accept."""
    with pytest.raises(ValueError, match="event_id"):
        Line(kind=LineKind.TASKS_COMPLETED, value=1.0, sources=())


def test_line_carries_its_event_ids() -> None:
    line = Line(kind=LineKind.TASKS_COMPLETED, value=2.0, sources=(EventId("e1"), EventId("e2")))
    assert line.sources == (EventId("e1"), EventId("e2"))


def test_line_is_immutable() -> None:
    line = Line(kind=LineKind.TASKS_COMPLETED, value=1.0, sources=(EventId("e1"),))
    with pytest.raises(FrozenInstanceError):
        line.value = 2.0  # type: ignore[misc]


def test_digest_is_immutable() -> None:
    digest = Digest(agent="refund-bot-v3", date=date(2026, 8, 30), lines=())
    with pytest.raises(FrozenInstanceError):
        digest.agent = "other-bot"  # type: ignore[misc]


def test_digest_defaults_to_no_deviations() -> None:
    digest = Digest(agent="refund-bot-v3", date=date(2026, 8, 30), lines=())
    assert digest.deviations == ()


def test_digests_with_same_fields_are_equal() -> None:
    line = Line(kind=LineKind.TASKS_COMPLETED, value=1.0, sources=(EventId("e1"),))
    first = Digest(agent="refund-bot-v3", date=date(2026, 8, 30), lines=(line,))
    second = Digest(agent="refund-bot-v3", date=date(2026, 8, 30), lines=(line,))
    assert first == second
