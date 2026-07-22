"""alfred.cli — `init`/`watch` (Brique 5) and `demo` (Brique 6) subcommand wiring.

See PLAN.md §5 Briques 5-6, docs/adr/0007-brique5-delivery-cli-design.md and
docs/adr/0008-brique6-demo-launch-polish-design.md.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from alfred.cli import main


def test_cli_init_creates_project(tmp_path: Path) -> None:
    exit_code = main(["init", str(tmp_path), "--agent", "refund-bot-v3"])
    assert exit_code == 0
    assert (tmp_path / "mandate.yaml").is_file()
    assert (tmp_path / ".alfred" / "config.toml").is_file()


def test_cli_init_writes_slack_webhook(tmp_path: Path) -> None:
    url = "https://hooks.slack.com/services/T0/B0/xyz"
    exit_code = main(
        ["init", str(tmp_path), "--agent", "refund-bot-v3", "--slack-webhook", url]
    )
    assert exit_code == 0
    from alfred.config import load_config

    assert load_config(tmp_path).slack_webhook_url == url


def test_cli_init_reports_error_on_invalid_slack_webhook(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        ["init", str(tmp_path), "--agent", "refund-bot-v3", "--slack-webhook", "ftp://nope"]
    )
    assert exit_code == 1
    assert "https" in capsys.readouterr().err


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


def test_cli_watch_loop_stops_on_keyboard_interrupt(
    tmp_path: Path,
    otlp_sample_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")

    def fake_sleep(_seconds: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", fake_sleep)
    exit_code = main(
        ["watch", str(traces_dir), "--project", str(project_dir), "--loop", "--interval", "0"]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "refund-bot-v3" in out  # first pass delivered before the interrupt
    assert "stopped" in out


def _watch_with_recorded_slack(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[object], list[object]]:
    """Replace Slack delivery with in-memory recorders so `watch` tests never
    hit the network. Returns (digests_sent, alerts_sent)."""
    from alfred.deliver import slack

    digests_sent: list[object] = []
    alerts_sent: list[object] = []
    monkeypatch.setattr(slack, "send", lambda digest, url: digests_sent.append(digest))
    monkeypatch.setattr(slack, "send_alert", lambda digest, url: alerts_sent.append(digest))
    return digests_sent, alerts_sent


def test_cli_watch_alerts_pushes_alert_on_deviation(
    tmp_path: Path, otlp_sample_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_path / "project"
    url = "https://hooks.slack.com/services/T0/B0/xyz"
    main(["init", str(project_dir), "--agent", "refund-bot-v3", "--slack-webhook", url])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")
    digests_sent, alerts_sent = _watch_with_recorded_slack(monkeypatch)

    exit_code = main(
        ["watch", str(traces_dir), "--project", str(project_dir), "--alerts"]
    )
    assert exit_code == 0
    # The scaffolded mandate has no allowed_tools, so issue_refund trips a
    # tool_not_allowed deviation → digest posted AND one alert pushed.
    assert len(digests_sent) == 1
    assert len(alerts_sent) == 1
    assert alerts_sent[0].deviations  # the alert carries the offending deviation


def test_cli_watch_without_alerts_flag_pushes_no_alert(
    tmp_path: Path, otlp_sample_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_path / "project"
    url = "https://hooks.slack.com/services/T0/B0/xyz"
    main(["init", str(project_dir), "--agent", "refund-bot-v3", "--slack-webhook", url])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")
    digests_sent, alerts_sent = _watch_with_recorded_slack(monkeypatch)

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir)])
    assert exit_code == 0
    assert len(digests_sent) == 1
    assert alerts_sent == []


def test_cli_watch_alerts_without_webhook_warns(
    tmp_path: Path, otlp_sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])  # no webhook
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")

    exit_code = main(
        ["watch", str(traces_dir), "--project", str(project_dir), "--alerts"]
    )
    assert exit_code == 0
    err = capsys.readouterr().err
    assert "--alerts" in err
    assert "webhook" in err


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


def test_cli_schedule_prints_cron_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    traces = tmp_path / "traces"
    exit_code = main(["schedule", str(traces), "--project", str(tmp_path), "--at", "07:15"])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("15 7 * * * alfred watch ")
    assert f"--project {tmp_path.resolve()}" in out


def test_cli_schedule_rejects_bad_time(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["schedule", str(tmp_path), "--at", "9am"])
    assert exit_code == 1
    assert "HH:MM" in capsys.readouterr().err


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


EXAMPLE_MANDATE = Path(__file__).parent.parent / "examples" / "mandates" / "refund-bot.yaml"


def test_cli_mandate_lint_accepts_valid_mandate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["mandate", "lint", str(EXAMPLE_MANDATE)])
    assert exit_code == 0
    assert "is valid" in capsys.readouterr().out


def test_cli_mandate_lint_errors_on_unknown_metric(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "mandate.yaml"
    path.write_text(
        "agent: bot\n"
        "allowed_tools: [read_order]\n"
        "daily_budget_eur: 5.0\n"
        "forbidden_actions: []\n"
        "escalate_when: [tool_errors > 0.1]\n",
        encoding="utf-8",
    )
    exit_code = main(["mandate", "lint", str(path)])
    assert exit_code == 1
    assert "tool_errors" in capsys.readouterr().err


def test_cli_mandate_init_from_traces_prints_reparsable_yaml(
    tmp_path: Path, otlp_sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from alfred.mandate.yaml_io import load_mandate

    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")

    exit_code = main(["mandate", "init", "--from-traces", str(traces_dir)])
    assert exit_code == 0

    out = capsys.readouterr().out
    written = tmp_path / "suggested.yaml"
    written.write_text(out, encoding="utf-8")
    mandate = load_mandate(written)
    assert mandate.agent == "refund-bot-v3"  # observed gen_ai.agent.name
    assert mandate.allowed_tools == frozenset({"issue_refund"})  # the only tool called
    assert mandate.daily_budget_eur == 1.0  # ceil of the observed sub-euro cost


def test_cli_mandate_init_from_traces_reports_empty_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "traces"
    empty.mkdir()
    exit_code = main(["mandate", "init", "--from-traces", str(empty)])
    assert exit_code == 1
    assert "no trace events" in capsys.readouterr().err


def test_cli_mandate_without_subcommand_prints_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["mandate"])
    assert exit_code == 0
    assert "lint" in capsys.readouterr().out


def test_cli_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    assert exit_code == 0
    assert "usage" in capsys.readouterr().out
