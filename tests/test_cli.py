"""alfred.cli — `init`/`watch` (Brique 5) and `demo` (Brique 6) subcommand wiring.

See PLAN.md §5 Briques 5-6, docs/adr/0007-brique5-delivery-cli-design.md and
docs/adr/0008-brique6-demo-launch-polish-design.md.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from alfred.cli import main


def test_cli_init_creates_project(tmp_path: Path) -> None:
    exit_code = main(["init", str(tmp_path), "--agent", "refund-bot-v3"])
    assert exit_code == 0
    assert (tmp_path / "mandate.yaml").is_file()
    assert (tmp_path / ".alfred" / "config.toml").is_file()


def test_cli_init_reports_error_on_existing_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["init", str(tmp_path), "--agent", "refund-bot-v3"])
    exit_code = main(["init", str(tmp_path), "--agent", "refund-bot-v3"])
    assert exit_code == 1
    assert "already exists" in capsys.readouterr().err


def test_cli_watch_ingests_and_prints_digest(
    tmp_path: Path, otlp_sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])

    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "refund-bot-v3" in out
    assert "Tasks completed" in out


def test_cli_watch_reports_no_new_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    empty_traces_dir = tmp_path / "traces"
    empty_traces_dir.mkdir()

    exit_code = main(["watch", str(empty_traces_dir), "--project", str(project_dir)])
    assert exit_code == 0
    assert "no new trace files" in capsys.readouterr().out


def test_cli_watch_reports_missing_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    exit_code = main(["watch", str(traces_dir), "--project", str(tmp_path / "nope")])
    assert exit_code == 1
    assert "no Alfred project found" in capsys.readouterr().err


def test_cli_watch_reports_corrupt_file_and_still_delivers(
    tmp_path: Path, otlp_sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """B3 regression: a corrupt file yields a clean stderr line and exit 1,
    while the valid files' digest is still delivered — no traceback."""
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])

    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")
    (traces_dir / "corrupt.json").write_text("{not json", encoding="utf-8")

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "corrupt.json" in captured.err
    assert "Tasks completed" in captured.out


def test_cli_watch_reports_slack_failure_cleanly(
    tmp_path: Path,
    otlp_sample_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alfred.deliver.slack import DeliverError
    from alfred.report.model import Digest

    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    config_path = project_dir / ".alfred" / "config.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + 'slack_webhook_url = "https://hooks.slack.com/services/T0/B0/xyz"\n',
        encoding="utf-8",
    )

    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")

    def failing_send(digest: Digest, webhook_url: str) -> None:
        raise DeliverError("Slack webhook returned HTTP 404: Not Found")

    monkeypatch.setattr("alfred.deliver.slack.send", failing_send)

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir)])
    assert exit_code == 1
    assert "404" in capsys.readouterr().err


def test_cli_demo_runs_fake_agent_and_prints_digest(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["demo"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "demo-bot" in out
    assert "Tasks completed" in out
    assert "Deviations (mandate)" in out
    assert "read_pii" in out


def test_cli_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    assert exit_code == 0
    assert "usage" in capsys.readouterr().out
