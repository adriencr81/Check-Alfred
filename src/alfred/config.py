"""Project configuration — `.alfred/config.toml` created by `alfred init`,
read back by `alfred watch`.

See PLAN.md §5 Brique 5 and docs/adr/0007-brique5-delivery-cli-design.md for
the design decisions recorded here (minimal hand-rolled TOML writer instead
of a new dependency, mandate scaffold reuse via `dump_mandate`).
"""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from alfred.mandate.model import Mandate
from alfred.mandate.yaml_io import dump_mandate

_MANDATE_FILENAME = "mandate.yaml"
_CONFIG_RELATIVE_PATH = Path(".alfred") / "config.toml"
_DEFAULT_TRACE_DB_RELATIVE_PATH = ".alfred/trace.db"
_WEBHOOK_ENV_VAR = "ALFRED_SLACK_WEBHOOK_URL"


class ConfigError(Exception):
    """Raised when a project cannot be initialized or its config cannot be loaded."""


@dataclass(frozen=True, slots=True)
class AlfredConfig:
    mandate_path: Path
    trace_db_path: Path
    slack_webhook_url: str | None = None


def _scaffold_mandate(agent: str) -> Mandate:
    return Mandate(
        agent=agent,
        allowed_tools=frozenset(),
        daily_budget_eur=5.00,
        forbidden_actions=(),
        escalate_when=(),
    )


def _dump_toml(data: dict[str, str]) -> str:
    """Serialize flat string key-values to TOML.

    TOML basic strings share JSON's escaping rules, so `json.dumps` produces
    a valid TOML string literal — sufficient for the flat, string-only
    config this project writes. Not a general TOML writer.
    """
    return "".join(f"{key} = {json.dumps(value)}\n" for key, value in data.items())


def init_project(directory: Path | str, agent: str) -> None:
    """Scaffold a new Alfred project: `mandate.yaml` + `.alfred/config.toml`.

    Raises `ConfigError` if either file already exists — `init` never
    silently overwrites an existing project.
    """
    root = Path(directory)
    mandate_path = root / _MANDATE_FILENAME
    config_path = root / _CONFIG_RELATIVE_PATH
    if mandate_path.exists():
        raise ConfigError(f"{mandate_path} already exists — refusing to overwrite")
    if config_path.exists():
        raise ConfigError(f"{config_path} already exists — refusing to overwrite")

    root.mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    mandate_path.write_text(dump_mandate(_scaffold_mandate(agent)), encoding="utf-8")
    config_path.write_text(
        _dump_toml(
            {
                "mandate_path": _MANDATE_FILENAME,
                "trace_db_path": _DEFAULT_TRACE_DB_RELATIVE_PATH,
            }
        ),
        encoding="utf-8",
    )


def load_config(directory: Path | str) -> AlfredConfig:
    """Load `.alfred/config.toml` relative to `directory` (the project root).

    The Slack webhook is a secret: the `ALFRED_SLACK_WEBHOOK_URL`
    environment variable takes priority over the `slack_webhook_url` key in
    config.toml, so it never has to be written to a file at all.

    Raises `ConfigError` if no project is initialized there, or the config
    is malformed / missing a required key.
    """
    root = Path(directory)
    config_path = root / _CONFIG_RELATIVE_PATH
    try:
        text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"no Alfred project found at {root} (missing {config_path})") from exc
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid config TOML at {config_path}: {exc}") from exc

    try:
        mandate_path = root / str(raw["mandate_path"])
        trace_db_path = root / str(raw["trace_db_path"])
    except KeyError as exc:
        raise ConfigError(f"config at {config_path} is missing required key {exc}") from exc

    webhook = os.environ.get(_WEBHOOK_ENV_VAR) or raw.get("slack_webhook_url")
    return AlfredConfig(
        mandate_path=mandate_path,
        trace_db_path=trace_db_path,
        slack_webhook_url=str(webhook) if webhook else None,
    )
