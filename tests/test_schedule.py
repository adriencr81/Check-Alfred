"""alfred.schedule — crontab line and GitHub Actions workflow generation.

See docs/adr/0007-brique5-delivery-cli-design.md §1 (cron-friendly single pass)
and docs/adr/0027-unattended-daily-digest.md (the workflow target).
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

import pytest
import yaml

from alfred.schedule import ScheduleError, build_cron_line, build_github_actions_workflow


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


def _parse(workflow: str) -> dict[str, Any]:
    parsed = yaml.safe_load(workflow)
    assert isinstance(parsed, dict)
    return parsed


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the workflow's `on:` block.

    PyYAML resolves the bare key `on` to the boolean True (YAML 1.1), which is
    exactly how GitHub's own parser does *not* read it. The generated file keeps
    the idiomatic bare `on:`, so the test looks under both spellings.
    """
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    return triggers


def _steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    return list(workflow["jobs"]["digest"]["steps"])


def _watch_step(workflow: dict[str, Any]) -> dict[str, Any]:
    matches = [s for s in _steps(workflow) if "alfred watch" in str(s.get("run", ""))]
    assert len(matches) == 1, f"expected exactly one `alfred watch` step, got {len(matches)}"
    return matches[0]


def test_github_actions_workflow_runs_watch_daily_at_the_given_time() -> None:
    workflow = _parse(build_github_actions_workflow("traces", hour=7, minute=15))
    assert _triggers(workflow)["schedule"] == [{"cron": "15 7 * * *"}]
    assert shlex.split(_watch_step(workflow)["run"]) == ["alfred", "watch", "traces"]


def test_github_actions_workflow_keeps_paths_relative_to_the_repo(tmp_path: Path) -> None:
    """A runner checks the repo out at a path unknown when the file is written,
    so an absolute path — what `build_cron_line` deliberately produces — would
    point at nothing. ADR 0027 decision 3."""
    rendered = build_github_actions_workflow("agent/traces", hour=9, minute=0)
    assert shlex.split(_watch_step(_parse(rendered))["run"])[-1] == "agent/traces"
    assert str(tmp_path.resolve()) not in rendered


def test_github_actions_workflow_rejects_an_absolute_traces_dir(tmp_path: Path) -> None:
    with pytest.raises(ScheduleError):
        build_github_actions_workflow(tmp_path.resolve(), hour=9, minute=0)


def test_github_actions_workflow_takes_the_webhook_from_a_repository_secret() -> None:
    """The webhook's path is its credential (ADR 0025 decision 7): it reaches the
    run through the environment, never through the committed file."""
    rendered = build_github_actions_workflow("traces", hour=9, minute=0)
    env = _watch_step(_parse(rendered))["env"]
    assert env["ALFRED_SLACK_WEBHOOK_URL"] == "${{ secrets.ALFRED_SLACK_WEBHOOK_URL }}"
    assert "hooks.slack.com" not in rendered


def test_github_actions_workflow_caches_state_between_runs() -> None:
    """Without this, `seen.json` and the baseline window restart empty on every
    run and the same digest is posted daily. ADR 0027 decision 5."""
    workflow = _parse(build_github_actions_workflow("traces", hour=9, minute=0))
    cache = [s for s in _steps(workflow) if "cache" in str(s.get("uses", ""))]
    assert len(cache) == 1
    assert cache[0]["with"]["path"] == ".alfred"
    assert cache[0]["with"]["restore-keys"]


def test_github_actions_workflow_bootstraps_config_when_the_cache_is_empty() -> None:
    """`.alfred/` is gitignored, so a cache miss leaves no project config and
    `watch` would exit. ADR 0027 decision 6."""
    workflow = _parse(build_github_actions_workflow("traces", hour=9, minute=0))
    bootstrap = [s for s in _steps(workflow) if "config.toml" in str(s.get("run", ""))]
    assert len(bootstrap) == 1
    assert "mandate.yaml" in bootstrap[0]["run"]


def test_github_actions_workflow_quotes_a_hostile_traces_dir() -> None:
    """`traces_dir` is user text crossing two layers — a YAML scalar, then a
    shell word. It must survive both as a single argument. ADR 0027 decision 8."""
    hostile = 'traces"; touch pwned; echo "'
    workflow = _parse(build_github_actions_workflow(hostile, hour=9, minute=0))
    assert shlex.split(_watch_step(workflow)["run"]) == ["alfred", "watch", hostile]


@pytest.mark.parametrize(("hour", "minute"), [(24, 0), (-1, 0), (9, 60), (9, -1)])
def test_github_actions_workflow_rejects_out_of_range_time(hour: int, minute: int) -> None:
    with pytest.raises(ScheduleError):
        build_github_actions_workflow("traces", hour=hour, minute=minute)
