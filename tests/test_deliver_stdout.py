"""alfred.deliver.stdout — the always-on delivery sink."""

from __future__ import annotations

from datetime import date

import pytest

from alfred.deliver.stdout import deliver
from alfred.report.model import Digest, Line, LineKind
from alfred.report.render import render
from alfred.trace.model import EventId


def test_deliver_prints_the_rendered_digest(capsys: pytest.CaptureFixture[str]) -> None:
    digest = Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(Line(kind=LineKind.TASKS_COMPLETED, value=1.0, sources=(EventId("e1"),)),),
    )
    deliver(digest)
    captured = capsys.readouterr()
    assert captured.out == render(digest) + "\n"
