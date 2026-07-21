"""`alfred schedule` — emit a ready-to-use crontab line for `alfred watch`.

The product is a *daily* digest, but `alfred.watch.watch_once` is a single
pass by design (ADR 0007 §1: no daemon, "cron-friendly", re-run via cron).
This module makes that promise concrete without adding any infra: it builds
one crontab entry that runs `alfred watch` at a fixed time each day. Pure
string generation — no scheduling process, trivially testable.

See docs/adr/0007-brique5-delivery-cli-design.md §1.
"""

from __future__ import annotations

from pathlib import Path


class ScheduleError(Exception):
    """Raised when a schedule cannot be built (e.g. an out-of-range time)."""


def build_cron_line(
    project_dir: Path | str,
    traces_dir: Path | str,
    *,
    hour: int,
    minute: int,
    alfred_bin: str = "alfred",
) -> str:
    """Return one crontab line running `alfred watch` daily at `hour:minute`.

    Paths are resolved to absolute so the line works from cron's bare
    environment (whose working directory is not the project). Raises
    `ScheduleError` if the time is out of range — fail loudly rather than
    emit a crontab line cron would silently reject.
    """
    if not 0 <= hour < 24:
        raise ScheduleError(f"hour must be in 0..23, got {hour}")
    if not 0 <= minute < 60:
        raise ScheduleError(f"minute must be in 0..59, got {minute}")

    project_abs = Path(project_dir).resolve()
    traces_abs = Path(traces_dir).resolve()
    command = f"{alfred_bin} watch {traces_abs} --project {project_abs}"
    return f"{minute} {hour} * * * {command}"
