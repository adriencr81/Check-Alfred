"""Packaging facts a release must not let drift.

`pyproject.toml` drives what PyPI serves, `alfred.__version__` drives what
`alfred --version` prints. Publishing a wheel whose CLI reports a different
number than the index is the kind of error that is only visible after the
upload is permanent. The console scripts are the same kind of fact: the
documented zero-install command names the *distribution*, so dropping the
`alfred-ai` alias breaks `uvx alfred-ai demo` while every installed
environment keeps working — a failure only a new user meets.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from alfred import __version__

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _project() -> dict[str, object]:
    return dict(tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"])


def test_declared_version_matches_package_version() -> None:
    assert _project()["version"] == __version__


def test_both_console_scripts_reach_the_same_cli() -> None:
    scripts = _project()["scripts"]
    assert isinstance(scripts, dict)
    # `alfred` is the name every doc uses once installed; `alfred-ai` is what
    # `uvx`/`pipx run` look for, since they derive it from the package name.
    assert scripts == {"alfred": "alfred.cli:main", "alfred-ai": "alfred.cli:main"}
