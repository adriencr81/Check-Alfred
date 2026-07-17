"""Alfred CLI entrypoint.

`init` and `watch` land in Brique 5 (see PLAN.md §5 and
docs/adr/0007-brique5-delivery-cli-design.md); `demo` remains a stub for
Brique 6.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from alfred import __version__
from alfred.config import ConfigError, init_project, load_config
from alfred.deliver import slack, stdout
from alfred.mandate.model import MandateError
from alfred.mandate.yaml_io import load_mandate
from alfred.trace.store import TraceStore
from alfred.watch import watch_once


def _cmd_init(args: argparse.Namespace) -> int:
    try:
        init_project(args.directory, agent=args.agent)
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


def _cmd_demo_stub(args: argparse.Namespace) -> int:
    print("alfred: command 'demo' is not yet implemented (see PLAN.md).", file=sys.stderr)
    return 2


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
    init_parser.set_defaults(func=_cmd_init)

    watch_parser = subparsers.add_parser(
        "watch", help="Ingest new OTLP JSON trace files and deliver a digest"
    )
    watch_parser.add_argument("traces_dir")
    watch_parser.add_argument("--project", default=".")
    watch_parser.set_defaults(func=_cmd_watch)

    demo_parser = subparsers.add_parser("demo", help="Run a fake instrumented agent (Brique 6)")
    demo_parser.set_defaults(func=_cmd_demo_stub)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handler: Callable[[argparse.Namespace], int] = args.func
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
