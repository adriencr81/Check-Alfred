"""alfred.narrate.render — NarratedDigest → stdout text.

The prose render replaces the metric rows with the LLM's verified sentences but
keeps the computed deviations block (shared with `report.render`).
"""

from __future__ import annotations

from datetime import date

from alfred.mandate.model import Deviation, DeviationType
from alfred.narrate.model import NarratedDigest, Sentence
from alfred.narrate.render import render_text
from alfred.report.model import Digest, Line, LineKind
from alfred.trace.model import EventId


def _line(kind: LineKind, value: float, *sources: str) -> Line:
    return Line(kind=kind, value=value, sources=tuple(EventId(s) for s in sources))


def test_render_text_shows_sentences_header_and_deviations() -> None:
    line = _line(LineKind.TASKS_COMPLETED, 2.0, "a1", "a2")
    digest = Digest(
        agent="refund-bot-v3",
        date=date(2026, 8, 30),
        lines=(line,),
        deviations=(
            Deviation(
                type=DeviationType.TOOL_NOT_ALLOWED,
                event_ids=(EventId("b1"),),
                message="tool 'read_pii' is not in allowed_tools",
            ),
        ),
    )
    narrated = NarratedDigest(
        digest=digest,
        sentences=(Sentence(text="Completed 2 tasks. [evt:a1, a2]", line=line),),
    )

    text = render_text(narrated)

    assert "Alfred · refund-bot-v3 · 2026-08-30" in text
    assert "Completed 2 tasks. [evt:a1, a2]" in text  # the prose sentence
    assert "tool_not_allowed" in text  # deviation block preserved
    assert "read_pii" in text
