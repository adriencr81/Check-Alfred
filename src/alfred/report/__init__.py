"""Report engine — trace events + mandate → anchored Digest (see PLAN.md §5 Brique 3)."""

from __future__ import annotations

from alfred.report.build import ReportError, build_digest
from alfred.report.model import Digest, Line, LineKind
from alfred.report.render import render

__all__ = [
    "Digest",
    "Line",
    "LineKind",
    "ReportError",
    "build_digest",
    "render",
]
