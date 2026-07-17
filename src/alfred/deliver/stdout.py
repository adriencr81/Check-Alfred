"""Digest delivery to stdout — the always-on sink alongside optional Slack."""

from __future__ import annotations

from alfred.report.model import Digest
from alfred.report.render import render


def deliver(digest: Digest) -> None:
    print(render(digest))
