"""Alfred CLI entrypoint.

`init` and `watch` land in Brique 5 (see PLAN.md §5 and
docs/adr/0007-brique5-delivery-cli-design.md); `demo` lands in Brique 6
(see docs/adr/0008-brique6-demo-launch-polish-design.md).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from alfred import __version__
from alfred.config import ConfigError, init_project, load_config
from alfred.deliver import slack, stdout
from alfred.demo import build_demo_payload, demo_mandate
from alfred.mandate.model import MandateError
from alfred.mandate.yaml_io import load_mandate
from alfred.report.build import build_digest
from alfred.schedule import ScheduleError, build_cron_line
from alfred.trace.ingest import ingest_otlp_json
from alfred.trace.store import TraceStore
from alfred.watch import watch_once


def _cmd_init(args: argparse.Namespace) -> int:
    try:
        init_project(args.directory, agent=args.agent, slack_webhook=args.slack_webhook)
    except ConfigError as exc:
        print(f"alfred init: {exc}", file=sys.stderr)
        return 1
    print(f"Initialized Alfred project in {Path(args.directory).resolve()}")
    return 0


def _cmd_watch(args: argparse.Namespace) -> int:
    project_dir = Path(args.project)
    try:
        config = load_config(project_dir)
        mandate = load_mandate(config.mandate_path)
    except (ConfigError, MandateError) as exc:
        print(f"alfred watch: {exc}", file=sys.stderr)
        return 1

    config.trace_db_path.parent.mkdir(parents=True, exist_ok=True)
    store = TraceStore(config.trace_db_path)
    try:
        digests = watch_once(project_dir, Path(args.traces_dir), mandate, store)
    finally:
        store.close()

    if not digests:
        print("alfred watch: no new trace files.")
        return 0

    for digest in digests:
        stdout.deliver(digest)
        if config.slack_webhook_url:
            slack.send(digest, config.slack_webhook_url)
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
    watch_parser.set_defaults(func=_cmd_watch)

    schedule_parser = subparsers.add_parser(
        "schedule", help="Print a crontab line that runs `alfred watch` daily"
    )
    schedule_parser.add_argument("traces_dir")
    schedule_parser.add_argument("--project", default=".")
    schedule_parser.add_argument(
        "--at", default="09:00", metavar="HH:MM", help="daily run time (24h), default 09:00"
    )
    schedule_parser.set_defaults(func=_cmd_schedule)

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
