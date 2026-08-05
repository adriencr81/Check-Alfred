"""alfred.cli — `init`/`watch` (Brique 5) and `demo` (Brique 6) subcommand wiring.

See PLAN.md §5 Briques 5-6, docs/adr/0007-brique5-delivery-cli-design.md and
docs/adr/0008-brique6-demo-launch-polish-design.md.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from alfred.cli import main
from alfred.report.model import Digest


@pytest.mark.parametrize("args", [["--help"], ["demo"]])
def test_cli_output_survives_cp1252_stdout(args: list[str]) -> None:
    """Help and digest text contain non-cp1252 chars (e.g. `→`); piping the CLI
    on Windows encodes stdout as cp1252 and must not raise UnicodeEncodeError."""
    result = subprocess.run(
        [sys.executable, "-m", "alfred.cli", *args],
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert "alfred" in result.stdout.decode("utf-8").lower()


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


def test_cli_watch_loop_floors_tiny_interval(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # `--interval 0` would spin re-globbing the directory; it must be clamped to
    # the floor (and the user told), not honored verbatim.
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()

    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", fake_sleep)
    exit_code = main(
        ["watch", str(traces_dir), "--project", str(project_dir), "--loop", "--interval", "0"]
    )
    assert exit_code == 0
    assert slept == [1.0]  # clamped to the floor, not 0
    assert "too low" in capsys.readouterr().err


def _watch_with_recorded_slack(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[Digest], list[Digest]]:
    """Replace Slack delivery with in-memory recorders so `watch` tests never
    hit the network. Returns (digests_sent, alerts_sent)."""
    from alfred.deliver import slack

    digests_sent: list[Digest] = []
    alerts_sent: list[Digest] = []
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


class _EchoStubLLM:
    """Well-behaved narration stub: cites exactly the event IDs the prompt allows.

    Mirrors the stub in tests/test_narrate_llm.py so `watch --narrate` /
    `report --narrate` can be exercised without a network or API key.
    """

    def complete(self, prompt: str) -> str:
        allowed = prompt.rsplit(":", 1)[1].strip()
        value = re.search(r"with value (.+?)\. The sentence", prompt)
        assert value is not None
        return f"Narrated line, {value.group(1)}. [evt:{allowed}]"


def _stub_narration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make `build_llm_client` return the echo stub, so the CLI narrates without
    reaching for a real endpoint or the ALFRED_LLM_API_KEY env var."""
    import alfred.cli as cli

    monkeypatch.setattr(cli, "build_llm_client", lambda _config: _EchoStubLLM())


def test_cli_watch_narrate_renders_prose(
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
    _stub_narration(monkeypatch)

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir), "--narrate"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Narrated line," in out  # prose, not the raw metric row
    assert "Tasks completed" not in out  # raw digest labels are replaced
    assert "tool_not_allowed" in out  # deviations still reported


def test_cli_watch_narrate_without_endpoint_errors(
    tmp_path: Path, otlp_sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])  # no LLM endpoint
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir), "--narrate"])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "--narrate" in err
    assert "ALFRED_LLM_API_KEY" in err


def test_cli_init_writes_llm_endpoint(tmp_path: Path) -> None:
    from alfred.config import load_config

    exit_code = main(
        [
            "init",
            str(tmp_path),
            "--agent",
            "refund-bot-v3",
            "--llm-base-url",
            "https://api.example.com/v1",
            "--llm-model",
            "gpt-4o-mini",
        ]
    )
    assert exit_code == 0
    config = load_config(tmp_path)
    assert config.llm_base_url == "https://api.example.com/v1"
    assert config.llm_model == "gpt-4o-mini"


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


def test_cli_watch_does_not_claim_no_new_files_when_one_was_quarantined(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unreadable file is not "no new trace files" — that reads as "all clear".

    The pass found a file and refused it; saying nothing arrived contradicts
    the quarantine notice printed right after it.
    """
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    (traces_dir / "broken.json").write_text("not json at all", encoding="utf-8")

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "no new trace files" not in captured.out
    assert "quarantined broken.json" in captured.err


def test_cli_watch_reports_unattributed_events_without_failing_the_pass(
    tmp_path: Path, otlp_sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same trace, from a pipeline that does not emit `gen_ai.agent.name`.

    It is still evaluated — dropping it would empty the digest of everyone whose
    Collector bridge omits the attribute — and the doubt is printed. But it does
    not fail the pass: unlike a quarantined file, no human action fixes it here,
    and an exit 1 on every run would train the operator to ignore it (ADR 0033).
    """
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    payload = json.loads(otlp_sample_path.read_text(encoding="utf-8"))
    for resource in payload["resourceSpans"]:
        for scope in resource["scopeSpans"]:
            for span in scope["spans"]:
                span["attributes"] = [
                    attribute
                    for attribute in span["attributes"]
                    if attribute["key"] != "gen_ai.agent.name"
                ]
    (traces_dir / "day1.json").write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Tasks completed" in captured.out  # evaluated, not dropped
    assert "gen_ai.agent.name" in captured.err
    assert "refund-bot-v3" in captured.err


def test_cli_watch_reports_missing_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    exit_code = main(["watch", str(traces_dir), "--project", str(tmp_path / "nope")])
    assert exit_code == 1
    assert "no Alfred project found" in capsys.readouterr().err


def test_cli_watch_missing_project_names_the_command_that_fixes_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The first-quarter-hour errors must say what to do, not only what happened."""
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    missing = tmp_path / "nope"
    exit_code = main(["watch", str(traces_dir), "--project", str(missing)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "alfred init" in err
    assert str(missing) in err


def test_cli_watch_broken_mandate_names_file_and_lint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A YAML parse error must name the file it came from and the way to check it."""
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    (project_dir / "mandate.yaml").write_text("agent: x\nallowed_tools: [a\n", encoding="utf-8")
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert str(project_dir / "mandate.yaml") in err
    assert "alfred mandate lint" in err


def test_cli_watch_reports_missing_traces_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A typo'd traces path must fail loudly, not silently look like "nothing new".
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    exit_code = main(["watch", str(tmp_path / "typo"), "--project", str(project_dir)])
    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


def test_cli_watch_quarantines_a_malformed_trace_and_delivers_the_rest(
    tmp_path: Path, otlp_sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A half-written JSON file must not take the whole pass down with it
    (ADR 0024): the healthy file's digest is still delivered, the bad one is
    named on stderr without a traceback, and the exit code flags the gap."""
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    (traces_dir / "broken.json").write_text("{ not valid json", encoding="utf-8")
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "quarantined broken.json" in captured.err
    assert "Traceback" not in captured.err
    assert "Alfred · refund-bot-v3" in captured.out  # the healthy day was reported


def test_cli_watch_repeats_the_quarantine_warning_on_a_later_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The hole stays visible in the cron log until a human clears it."""
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    (traces_dir / "broken.json").write_text("{ not valid json", encoding="utf-8")
    main(["watch", str(traces_dir), "--project", str(project_dir)])
    capsys.readouterr()

    exit_code = main(["watch", str(traces_dir), "--project", str(project_dir)])
    assert exit_code == 1
    assert "quarantined broken.json" in capsys.readouterr().err


def test_cli_report_writes_html_file(tmp_path: Path, otlp_sample_path: Path) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")
    out_dir = tmp_path / "out"

    exit_code = main(
        ["report", str(traces_dir), "--project", str(project_dir), "--html", "--out", str(out_dir)]
    )
    assert exit_code == 0
    written = list(out_dir.glob("alfred-refund-bot-v3-*.html"))
    assert len(written) == 1
    html = written[0].read_text(encoding="utf-8")
    assert "refund-bot-v3" in html
    assert 'href="#evt-' in html  # lines are clickable to their source events


def test_cli_report_points_the_forwarder_at_teams(
    tmp_path: Path, otlp_sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The dev who renders a report is the one who forwards it (ADR 0030 decision 1).
    They are told once, on stdout, where to go when the open package stops being
    enough — the person they forward it to has no other way to find out."""
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")
    out_dir = tmp_path / "out"

    assert (
        main(
            [
                "report",
                str(traces_dir),
                "--project",
                str(project_dir),
                "--html",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "/teams/" in out
    # It follows the written-file lines; it is a footnote, not a result.
    assert out.index("wrote ") < out.index("/teams/")


def test_cli_report_pointer_stays_out_of_the_evidence_file(
    tmp_path: Path, otlp_sample_path: Path
) -> None:
    """ADR 0020 decision 2 keeps the HTML free of any external reference, and ADR
    0030 decision 5 declines to relax it: this artifact gets filed for audit, so
    the pointer lives on stdout and never in the file."""
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")
    out_dir = tmp_path / "out"

    main(
        ["report", str(traces_dir), "--project", str(project_dir), "--html", "--out", str(out_dir)]
    )
    html = next(iter(out_dir.glob("*.html"))).read_text(encoding="utf-8")
    assert "teams" not in html
    assert "http" not in html


def test_cli_report_narrate_embeds_prose(
    tmp_path: Path, otlp_sample_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")
    out_dir = tmp_path / "out"
    _stub_narration(monkeypatch)

    exit_code = main(
        [
            "report", str(traces_dir), "--project", str(project_dir),
            "--html", "--out", str(out_dir), "--narrate",
        ]
    )
    assert exit_code == 0
    html = next(out_dir.glob("*.html")).read_text(encoding="utf-8")
    assert 'class="narrative"' in html
    assert "Narrated line," in html


def test_cli_report_narrate_without_endpoint_errors(
    tmp_path: Path, otlp_sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])  # no LLM endpoint
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")

    exit_code = main(
        ["report", str(traces_dir), "--project", str(project_dir), "--html", "--narrate"]
    )
    assert exit_code == 1
    assert "ALFRED_LLM_API_KEY" in capsys.readouterr().err


def test_cli_report_is_rerunnable(tmp_path: Path, otlp_sample_path: Path) -> None:
    # Unlike `watch`, `report` tracks no seen files — a second run over the same
    # directory still produces the report (falsifies any seen.json coupling).
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")
    out_dir = tmp_path / "out"
    argv = [
        "report", str(traces_dir), "--project", str(project_dir), "--html", "--out", str(out_dir)
    ]

    assert main(argv) == 0
    assert main(argv) == 0
    assert len(list(out_dir.glob("*.html"))) == 1


def test_cli_report_requires_html_flag(
    tmp_path: Path, otlp_sample_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")

    exit_code = main(["report", str(traces_dir), "--project", str(project_dir)])
    assert exit_code == 1
    assert "--html" in capsys.readouterr().err


def test_cli_report_reports_empty_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    empty = tmp_path / "traces"
    empty.mkdir()

    exit_code = main(
        ["report", str(empty), "--project", str(project_dir), "--html", "--out", str(tmp_path)]
    )
    assert exit_code == 1
    assert "no trace events" in capsys.readouterr().err


def test_cli_report_reports_malformed_trace_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_dir = tmp_path / "project"
    main(["init", str(project_dir), "--agent", "refund-bot-v3"])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    (traces_dir / "broken.json").write_text('{"foo": "bar"}', encoding="utf-8")

    exit_code = main(
        ["report", str(traces_dir), "--project", str(project_dir), "--html", "--out", str(tmp_path)]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "cannot read traces" in err
    assert "broken.json" in err
    assert "Traceback" not in err


def test_cli_report_reports_missing_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    exit_code = main(["report", str(traces_dir), "--project", str(tmp_path / "nope"), "--html"])
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


def test_cli_schedule_prints_github_actions_workflow(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["schedule", "traces", "--at", "07:15", "--github-actions"])
    assert exit_code == 0
    workflow = yaml.safe_load(capsys.readouterr().out)
    assert workflow["jobs"]["digest"]["steps"][0]["uses"].startswith("actions/checkout")


def test_cli_schedule_refuses_project_with_github_actions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A workflow runs from the repository root, so --project cannot be honoured
    there — saying so beats ignoring it (ADR 0027)."""
    exit_code = main(
        ["schedule", "traces", "--project", str(tmp_path), "--at", "09:00", "--github-actions"]
    )
    assert exit_code == 1
    assert "--project does not apply" in capsys.readouterr().err


def test_cli_schedule_rejects_absolute_traces_dir_for_github_actions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["schedule", str(tmp_path.resolve()), "--at", "09:00", "--github-actions"])
    assert exit_code == 1
    assert "must be relative" in capsys.readouterr().err


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


def test_cli_demo_invites_the_first_digest_to_be_shared(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The package carries no telemetry, so an install that produced a digest is
    invisible unless its owner says so. ADR 0027 decision 9."""
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "show_your_digest.md" in out
    # The invitation follows the digest; it must never be mistaken for a line of it.
    assert out.index("Tasks completed") < out.index("Show us what it caught")


def test_cli_demo_invitation_points_at_a_template_that_exists() -> None:
    """A dead link in the one line asking for feedback is worse than no line."""
    template = Path(__file__).resolve().parent.parent / ".github/ISSUE_TEMPLATE/show_your_digest.md"
    assert template.is_file()


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


def test_cli_mandate_init_reports_malformed_trace_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    (traces_dir / "broken.json").write_text("{ not valid json", encoding="utf-8")

    exit_code = main(["mandate", "init", "--from-traces", str(traces_dir)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "cannot read traces" in err
    assert "broken.json" in err
    assert "Traceback" not in err


def test_cli_init_scaffold_mandate_carries_guidance(tmp_path: Path) -> None:
    # The scaffolded mandate must warn that empty allowed_tools flags every tool
    # and point at the seed-from-traces path, and stay a loadable mandate.
    from alfred.mandate.yaml_io import load_mandate

    main(["init", str(tmp_path), "--agent", "refund-bot-v3"])
    text = (tmp_path / "mandate.yaml").read_text(encoding="utf-8")
    assert "allowed_tools is empty" in text
    assert "--from-traces" in text
    assert load_mandate(tmp_path / "mandate.yaml").agent == "refund-bot-v3"


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


def test_cli_watch_loop_survives_a_delivery_failure(
    tmp_path: Path,
    otlp_sample_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0024 decision 7: an outage at Slack must not end the supervision.

    The first pass fails to deliver; the loop must reach a second pass rather
    than let DeliverError escape and stop `alfred watch`.
    """
    from alfred.deliver import slack

    project_dir = tmp_path / "project"
    url = "https://hooks.slack.com/services/T000/B000/XXX"
    main(["init", str(project_dir), "--agent", "refund-bot-v3", "--slack-webhook", url])
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    shutil.copy(otlp_sample_path, traces_dir / "day1.json")

    def exploding_send(digest: object, webhook_url: str) -> None:
        raise slack.DeliverError("Slack webhook unreachable: connection refused")

    monkeypatch.setattr(slack, "send", exploding_send)

    passes = 0

    def fake_sleep(_seconds: float) -> None:
        nonlocal passes
        passes += 1
        if passes == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", fake_sleep)
    exit_code = main(
        ["watch", str(traces_dir), "--project", str(project_dir), "--loop", "--interval", "1"]
    )

    assert exit_code == 0
    assert passes == 2  # the loop kept going after the failed delivery
    assert "connection refused" in capsys.readouterr().err
