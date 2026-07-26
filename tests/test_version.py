"""The package version is declared twice; a release must not let them drift.

`pyproject.toml` drives what PyPI serves, `alfred.__version__` drives what
`alfred --version` prints. Publishing a wheel whose CLI reports a different
number than the index is the kind of error that is only visible after the
upload is permanent.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from alfred import __version__

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_declared_version_matches_package_version() -> None:
    declared = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert declared == __version__
