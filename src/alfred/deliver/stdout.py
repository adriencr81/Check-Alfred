"""Digest delivery to stdout — the always-on sink alongside optional Slack."""

from __future__ import annotations

import sys

from alfred.report.model import Digest
from alfred.report.render import render


def deliver(digest: Digest) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(render(digest))
