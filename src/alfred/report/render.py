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

_LABELS: dict[LineKind, str] = {
    LineKind.TASKS_COMPLETED: "Tasks completed",
    LineKind.COST_EUR: "Cost (tokens → €)",
    LineKind.ESCALATIONS: "Escalations",
}


def _format_value(line: Line) -> str:
    if line.kind is LineKind.COST_EUR:
        return f"{line.value:.2f} €"
    return str(int(line.value))


def _format_sources(event_ids: tuple[EventId, ...]) -> str:
    return "[evt:" + ", ".join(event_ids) + "]"


def _render_line(line: Line) -> str:
    label = _LABELS[line.kind]
    return f"{label}: {_format_value(line):>10}   {_format_sources(line.sources)}"


def _render_deviations(deviations: tuple[Deviation, ...]) -> list[str]:
    if not deviations:
        return []
    rows = [f"Deviations (mandate): {len(deviations):>10}"]
    rows.extend(
        f"  - {deviation.type.value}: {deviation.message}   "
        f"{_format_sources(deviation.event_ids)}"
        for deviation in deviations
    )
    return rows


def render(digest: Digest) -> str:
    rows = [f"Alfred · {digest.agent} · {digest.date.isoformat()}", ""]
    rows.extend(_render_line(line) for line in digest.lines)
    rows.extend(_render_deviations(digest.deviations))
    return "\n".join(rows)
