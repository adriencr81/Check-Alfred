"""alfred.schedule — crontab line generation for `alfred watch`.

See docs/adr/0007-brique5-delivery-cli-design.md §1 (cron-friendly single pass).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alfred.schedule import ScheduleError, build_cron_line


def test_build_cron_line_default_shape(tmp_path: Path) -> None:
    project = tmp_path / "project"
    traces = tmp_path / "traces"
    line = build_cron_line(project, traces, hour=9, minute=0)
    assert line == (
        f"0 9 * * * alfred watch {traces.resolve()} --project {project.resolve()}"
    )


def test_build_cron_line_custom_time_and_bin(tmp_path: Path) -> None:
    line = build_cron_line(tmp_path, tmp_path / "t", hour=18, minute=30, alfred_bin="/opt/alfred")
    assert line.startswith("30 18 * * * /opt/alfred watch ")


@pytest.mark.parametrize(("hour", "minute"), [(24, 0), (-1, 0), (9, 60), (9, -1)])
def test_build_cron_line_rejects_out_of_range_time(hour: int, minute: int, tmp_path: Path) -> None:
    with pytest.raises(ScheduleError):
        build_cron_line(tmp_path, tmp_path, hour=hour, minute=minute)
