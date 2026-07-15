"""Alfred CLI entrypoint.

STUB — real commands land in Brique 5 (`init`, `watch`) and Brique 6 (`demo`).
"""

from __future__ import annotations

import argparse
import sys

from alfred import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alfred", description="Alfred — accountability layer for AI employees")
    parser.add_argument("--version", action="version", version=f"alfred {__version__}")
    parser.add_argument("command", nargs="?", help="init | watch | demo (Brique 5-6)")
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    print(f"alfred: command '{args.command}' is not yet implemented (see PLAN.md).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
