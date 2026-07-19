"""Digest → fixed-format text.

Format frozen by PLAN.md §5 Brique 3 (see also README's digest example) — do
not vary the layout per output sink. The same string serves both the stdout
and markdown outputs called for by Brique 3's objective; delivery (writing
it to a file vs. printing it) is out of scope here (Brique 5).
"""

from __future__ import annotations

from alfred.mandate.model import Deviation
from alfred.report.model import Digest, Line, LineKind
from alfred.trace.model import EventId

LABELS: dict[LineKind, str] = {
    LineKind.TASKS_COMPLETED: "Tasks completed",
    LineKind.COST_EUR: "Cost (tokens → €)",
    LineKind.ESCALATIONS: "Escalations",
}

_MAX_DISPLAYED_SOURCES = 3
_TRUNCATE_IDS_LONGER_THAN = 12
_DISPLAYED_ID_PREFIX = 8


def format_value(line: Line) -> str:
    if line.kind is LineKind.COST_EUR:
        return f"{line.value:.2f} €"
    return str(int(line.value))


def _format_event_id(event_id: EventId) -> str:
    if len(event_id) > _TRUNCATE_IDS_LONGER_THAN:
        return event_id[:_DISPLAYED_ID_PREFIX] + "…"
    return event_id


def format_sources(event_ids: tuple[EventId, ...]) -> str:
    """Display form of a line's evidence — never its source of truth.

    Full IDs stay in `Line.sources` / `Deviation.event_ids`; this truncates
    long IDs to an 8-char prefix and shows at most 3, then ` +N`, so the
    proof stays visible without drowning the facts.
    """
    shown = [_format_event_id(event_id) for event_id in event_ids[:_MAX_DISPLAYED_SOURCES]]
    hidden = len(event_ids) - _MAX_DISPLAYED_SOURCES
    suffix = f" +{hidden}" if hidden > 0 else ""
    return "[evt:" + ", ".join(shown) + suffix + "]"


def _render_line(line: Line) -> str:
    label = LABELS[line.kind]
    return f"{label}: {format_value(line):>10}   {format_sources(line.sources)}"


def _render_deviations(deviations: tuple[Deviation, ...]) -> list[str]:
    if not deviations:
        return []
    if len(deviations) == 1:
        deviation = deviations[0]
        return [
            f"Deviations (mandate): {1:>10}   {format_sources(deviation.event_ids)} "
            f"— {deviation.type.value}: {deviation.message}"
        ]
    rows = [f"Deviations (mandate): {len(deviations):>10}"]
    rows.extend(
        f"  - {deviation.type.value}: {deviation.message}   "
        f"{format_sources(deviation.event_ids)}"
        for deviation in deviations
    )
    return rows


def render(digest: Digest) -> str:
    rows = [f"Alfred · {digest.agent} · {digest.date.isoformat()}", ""]
    rows.extend(_render_line(line) for line in digest.lines)
    rows.extend(_render_deviations(digest.deviations))
    return "\n".join(rows)
