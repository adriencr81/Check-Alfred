"""NarratedDigest → fixed-format text for stdout delivery.

The prose counterpart to `alfred.report.render.render`: it prints the LLM's
verified sentences (each already carrying its own `[evt:…]` citation) in place
of the raw metric rows, then the same deviations block. Reuses
`report.render.render_deviations` so the deviation lines stay identical to the
non-narrated digest — the prose only ever replaces the metric lines, never the
computed deviations.
"""

from __future__ import annotations

from alfred.narrate.model import NarratedDigest
from alfred.report.render import render_deviations


def render_text(narrated: NarratedDigest) -> str:
    digest = narrated.digest
    rows = [f"Alfred · {digest.agent} · {digest.date.isoformat()}", ""]
    rows.extend(sentence.text for sentence in narrated.sentences)
    rows.extend(render_deviations(digest.deviations))
    return "\n".join(rows)
