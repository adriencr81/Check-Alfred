"""alfred.cli — `init` and `watch` subcommand wiring (Brique 5).

See PLAN.md §5 Brique 5 and docs/adr/0007-brique5-delivery-cli-design.md.
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


def test_cli_demo_is_still_a_stub(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["demo"])
    assert exit_code == 2
    assert "not yet implemented" in capsys.readouterr().err


def test_cli_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    assert exit_code == 0
    assert "usage" in capsys.readouterr().out
