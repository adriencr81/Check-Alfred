"""Alfred CLI entrypoint.

`init` and `watch` land in Brique 5 (see PLAN.md §5 and
docs/adr/0007-brique5-delivery-cli-design.md); `demo` lands in Brique 6
(see docs/adr/0008-brique6-demo-launch-polish-design.md).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

from alfred import __version__
from alfred.config import AlfredConfig, ConfigError, init_project, load_config
from alfred.deliver import slack, stdout
from alfred.demo import build_demo_payload, demo_mandate
from alfred.mandate.bootstrap import suggest_mandate
from alfred.mandate.lint import Severity, lint_mandate
from alfred.mandate.model import MandateError
from alfred.mandate.yaml_io import dump_mandate, load_mandate
from alfred.report.build import build_digest
from alfred.report.html import render_html
from alfred.report.model import Digest
from alfred.schedule import ScheduleError, build_cron_line
from alfred.trace.ingest import ingest_otlp_file, ingest_otlp_json
from alfred.trace.model import TraceEvent
from alfred.trace.store import TraceStore
from alfred.watch import build_digests, watch_loop, watch_once


def _cmd_init(args: argparse.Namespace) -> int:
    try:
        init_project(args.directory, agent=args.agent, slack_webhook=args.slack_webhook)
    except ConfigError as exc:
        print(f"alfred init: {exc}", file=sys.stderr)
        return 1
    print(f"Initialized Alfred project in {Path(args.directory).resolve()}")
    return 0


def _deliver(digests: list[Digest], config: AlfredConfig, *, alerts: bool = False) -> None:
    """Deliver each digest to stdout and, if configured, to Slack.

    Shared by the single-pass and `--loop` paths. When empty (no new trace
    files) it prints one notice; in loop mode that keeps each idle pass quiet
    but visible. With `alerts` set, a digest that carries deviations also
    triggers an immediate Slack alert (ADR 0017) alongside the digest.
    """
    if not digests:
        print("alfred watch: no new trace files.")
        return
    for digest in digests:
        stdout.deliver(digest)
        if config.slack_webhook_url:
            slack.send(digest, config.slack_webhook_url)
            if alerts and digest.deviations:
                slack.send_alert(digest, config.slack_webhook_url)


def _cmd_watch(args: argparse.Namespace) -> int:
    project_dir = Path(args.project)
    try:
        config = load_config(project_dir)
        mandate = load_mandate(config.mandate_path)
    except (ConfigError, MandateError) as exc:
        print(f"alfred watch: {exc}", file=sys.stderr)
        return 1

    if args.alerts and not config.slack_webhook_url:
        print(
            "alfred watch: --alerts needs a Slack webhook; none configured — run "
            "`alfred init --slack-webhook URL`. Deviations still show in the digest.",
            file=sys.stderr,
        )

    traces_dir = Path(args.traces_dir)
    config.trace_db_path.parent.mkdir(parents=True, exist_ok=True)
    store = TraceStore(config.trace_db_path)
    try:
        if args.loop:
            watch_loop(
                project_dir,
                traces_dir,
                mandate,
                store,
                lambda digests: _deliver(digests, config, alerts=args.alerts),
                interval_s=args.interval,
            )
        else:
            digests = watch_once(project_dir, traces_dir, mandate, store)
            _deliver(digests, config, alerts=args.alerts)
    except KeyboardInterrupt:
        print("\nalfred watch: stopped.")
    finally:
        store.close()
    return 0


def _read_trace_events(traces_dir: Path) -> list[TraceEvent]:
    """Ingest every OTLP JSON file in `traces_dir`, in filename order.

    Raises `OSError` if a file cannot be read — each caller frames its own
    message. Shared by `report` and `mandate init`.
    """
    events: list[TraceEvent] = []
    for file_path in sorted(traces_dir.glob("*.json")):
        events.extend(ingest_otlp_file(file_path))
    return events


def _slug(text: str) -> str:
    """A filesystem-safe slug for a report filename (keeps alnum, '-' and '_')."""
    return re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-") or "agent"


def _cmd_report(args: argparse.Namespace) -> int:
    if not args.html:
        print(
            "alfred report: choose an output format — only --html is available.",
            file=sys.stderr,
        )
        return 1

    project_dir = Path(args.project)
    try:
        config = load_config(project_dir)
        mandate = load_mandate(config.mandate_path)
    except (ConfigError, MandateError) as exc:
        print(f"alfred report: {exc}", file=sys.stderr)
        return 1

    traces_dir = Path(args.traces_dir)
    try:
        events = _read_trace_events(traces_dir)
    except OSError as exc:
        print(f"alfred report: cannot read traces: {exc}", file=sys.stderr)
        return 1
    if not events:
        print(
            f"alfred report: no trace events found in {traces_dir} (expected *.json)",
            file=sys.stderr,
        )
        return 1

    # Ingest into the store (idempotent) so each day's digest carries its rolling
    # baseline (F3); unlike `watch`, `report` tracks no seen files, so it always
    # re-renders — a shareable report is meant to be regenerated on demand.
    config.trace_db_path.parent.mkdir(parents=True, exist_ok=True)
    store = TraceStore(config.trace_db_path)
    try:
        store.put_many(events)
        digests = build_digests(mandate, events, store)
    finally:
        store.close()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for digest in digests:
        path = out_dir / f"alfred-{_slug(digest.agent)}-{digest.date.isoformat()}.html"
        path.write_text(render_html(digest), encoding="utf-8")
        print(f"alfred report: wrote {path}")
    return 0


def _cmd_schedule(args: argparse.Namespace) -> int:
    try:
        hour_str, minute_str = args.at.split(":", 1)
        hour, minute = int(hour_str), int(minute_str)
    except ValueError:
        print(f"alfred schedule: --at must be HH:MM, got {args.at!r}", file=sys.stderr)
        return 1
    try:
        line = build_cron_line(args.project, args.traces_dir, hour=hour, minute=minute)
    except ScheduleError as exc:
        print(f"alfred schedule: {exc}", file=sys.stderr)
        return 1
    print(line)
    return 0


def _cmd_mandate_lint(args: argparse.Namespace) -> int:
    findings = lint_mandate(args.path)
    for finding in findings:
        stream = sys.stderr if finding.severity is Severity.ERROR else sys.stdout
        print(f"alfred mandate lint: {finding.severity}: {finding.message}", file=stream)
    if any(finding.severity is Severity.ERROR for finding in findings):
        return 1
    warnings = len(findings)
    tail = f" ({warnings} warning{'s' if warnings != 1 else ''})" if warnings else ""
    print(f"alfred mandate lint: {args.path} is valid{tail}")
    return 0


_SUGGESTED_HEADER = (
    "# Suggested mandate — observed from your traces.\n"
    "# Review before use: allowed_tools and daily_budget_eur are what the agent\n"
    "# DID, not what it MAY do. Add headroom to the budget, and fill in\n"
    "# forbidden_actions / escalate_when — policy the human declares, never\n"
    "# inferred from a trace.\n"
)


def _cmd_mandate_init(args: argparse.Namespace) -> int:
    traces_dir = Path(args.from_traces)
    try:
        events = _read_trace_events(traces_dir)
    except OSError as exc:
        print(f"alfred mandate init: cannot read traces: {exc}", file=sys.stderr)
        return 1
    if not events:
        print(
            f"alfred mandate init: no trace events found in {traces_dir} (expected *.json)",
            file=sys.stderr,
        )
        return 1
    mandate = suggest_mandate(events, agent=args.agent)
    print(_SUGGESTED_HEADER + dump_mandate(mandate), end="")
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    payload = build_demo_payload(args.agent)
    events = ingest_otlp_json(payload)
    mandate = demo_mandate(args.agent)
    digest = build_digest(mandate, events, events[0].start_time.date())
    stdout.deliver(digest)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="alfred", description="Alfred — accountability layer for AI employees"
    )
    parser.add_argument("--version", action="version", version=f"alfred {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init", help="Scaffold mandate.yaml + .alfred/config.toml in a project directory"
    )
    init_parser.add_argument("directory", nargs="?", default=".")
    init_parser.add_argument("--agent", default="your-agent")
    init_parser.add_argument(
        "--slack-webhook",
        default=None,
        metavar="URL",
        help="Slack incoming webhook (https://…); written to config so `watch` posts the digest",
    )
    init_parser.set_defaults(func=_cmd_init)

    watch_parser = subparsers.add_parser(
        "watch", help="Ingest new OTLP JSON trace files and deliver a digest"
    )
    watch_parser.add_argument("traces_dir")
    watch_parser.add_argument("--project", default=".")
    watch_parser.add_argument(
        "--loop",
        action="store_true",
        help="keep running, re-scanning every --interval seconds (Ctrl-C to stop)",
    )
    watch_parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        metavar="SECONDS",
        help="seconds between passes when --loop is set (default 60)",
    )
    watch_parser.add_argument(
        "--alerts",
        action="store_true",
        help="also push an immediate Slack alert whenever a pass finds a deviation "
        "(needs a configured webhook; pair with --loop for near real-time)",
    )
    watch_parser.set_defaults(func=_cmd_watch)

    report_parser = subparsers.add_parser(
        "report", help="Render a shareable, self-contained HTML report from OTLP trace files"
    )
    report_parser.add_argument("traces_dir")
    report_parser.add_argument("--project", default=".")
    report_parser.add_argument(
        "--html",
        action="store_true",
        help="write a self-contained HTML report, one file per day (currently required)",
    )
    report_parser.add_argument(
        "--out",
        default=".",
        metavar="DIR",
        help="output directory for alfred-<agent>-<date>.html files (default: current dir)",
    )
    report_parser.set_defaults(func=_cmd_report)

    schedule_parser = subparsers.add_parser(
        "schedule", help="Print a crontab line that runs `alfred watch` daily"
    )
    schedule_parser.add_argument("traces_dir")
    schedule_parser.add_argument("--project", default=".")
    schedule_parser.add_argument(
        "--at", default="09:00", metavar="HH:MM", help="daily run time (24h), default 09:00"
    )
    schedule_parser.set_defaults(func=_cmd_schedule)

    mandate_parser = subparsers.add_parser(
        "mandate", help="Bootstrap or validate a mandate.yaml (see `mandate lint`/`init`)"
    )
    mandate_sub = mandate_parser.add_subparsers(dest="mandate_command")

    def _print_mandate_help(_args: argparse.Namespace) -> int:
        mandate_parser.print_help()
        return 0

    mandate_parser.set_defaults(func=_print_mandate_help)

    lint_parser = mandate_sub.add_parser(
        "lint", help="Validate a mandate.yaml (exit 1 on error, 0 otherwise)"
    )
    lint_parser.add_argument("path", nargs="?", default="mandate.yaml")
    lint_parser.set_defaults(func=_cmd_mandate_lint)

    mandate_init_parser = mandate_sub.add_parser(
        "init", help="Print a suggested mandate.yaml observed from OTLP trace files"
    )
    mandate_init_parser.add_argument(
        "--from-traces",
        required=True,
        metavar="DIR",
        help="directory of OTLP JSON trace files to observe tools and cost from",
    )
    mandate_init_parser.add_argument(
        "--agent",
        default=None,
        help="agent name to write (default: observed gen_ai.agent.name, else 'your-agent')",
    )
    mandate_init_parser.set_defaults(func=_cmd_mandate_init)

    demo_parser = subparsers.add_parser(
        "demo", help="Run a fake instrumented agent → real digest, zero setup"
    )
    demo_parser.add_argument("--agent", default="demo-bot")
    demo_parser.set_defaults(func=_cmd_demo)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handler: Callable[[argparse.Namespace], int] = args.func
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
