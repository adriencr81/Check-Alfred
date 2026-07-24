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
from alfred.narrate.llm import LLMClient, OpenAICompatibleClient

_MANDATE_FILENAME = "mandate.yaml"
_CONFIG_RELATIVE_PATH = Path(".alfred") / "config.toml"
_DEFAULT_TRACE_DB_RELATIVE_PATH = ".alfred/trace.db"

# The narration API key is read from the environment, never written to disk or
# passed as a CLI flag — only the non-secret endpoint (base URL + model) lives
# in config.toml. See `build_llm_client` and docs/adr/0007.
LLM_API_KEY_ENV = "ALFRED_LLM_API_KEY"


class ConfigError(Exception):
    """Raised when a project cannot be initialized or its config cannot be loaded."""


@dataclass(frozen=True, slots=True)
class AlfredConfig:
    mandate_path: Path
    trace_db_path: Path
    slack_webhook_url: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None


def _scaffold_mandate(agent: str) -> Mandate:
    return Mandate(
        agent=agent,
        allowed_tools=frozenset(),
        daily_budget_eur=5.00,
        forbidden_actions=(),
        escalate_when=(),
    )


def _validate_webhook(url: str) -> str:
    """Return `url` if it is a plausible Slack incoming webhook, else raise.

    Slack incoming webhooks are always HTTPS. Reject anything else loudly at
    `init` time rather than writing a config that `alfred watch` would only
    fail on later — same "fail loudly" stance as the existing overwrite guard
    and `deliver.slack._urllib_transport`'s scheme check.
    """
    if not url.startswith("https://"):
        raise ConfigError(f"slack webhook must be an https:// URL, got {url!r}")
    return url


def _dump_toml(data: dict[str, str]) -> str:
    """Serialize flat string key-values to TOML.

    TOML basic strings share JSON's escaping rules, so `json.dumps` produces
    a valid TOML string literal — sufficient for the flat, string-only
    config this project writes. Not a general TOML writer.
    """
    return "".join(f"{key} = {json.dumps(value)}\n" for key, value in data.items())


def init_project(
    directory: Path | str,
    agent: str,
    slack_webhook: str | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
) -> None:
    """Scaffold a new Alfred project: `mandate.yaml` + `.alfred/config.toml`.

    When `slack_webhook` is given it is validated and written as
    `slack_webhook_url` so `alfred watch` posts the digest to Slack with no
    hand-editing of the config. `llm_base_url` / `llm_model`, when given, are
    written as the narration endpoint read back by `alfred watch --narrate`
    (the API key stays in env `ALFRED_LLM_API_KEY`, never on disk). Raises
    `ConfigError` if either file already exists — `init` never silently
    overwrites an existing project — or if the webhook is not an https:// URL.
    """
    root = Path(directory)
    mandate_path = root / _MANDATE_FILENAME
    config_path = root / _CONFIG_RELATIVE_PATH
    if mandate_path.exists():
        raise ConfigError(f"{mandate_path} already exists — refusing to overwrite")
    if config_path.exists():
        raise ConfigError(f"{config_path} already exists — refusing to overwrite")

    config_values = {
        "mandate_path": _MANDATE_FILENAME,
        "trace_db_path": _DEFAULT_TRACE_DB_RELATIVE_PATH,
    }
    if slack_webhook is not None:
        config_values["slack_webhook_url"] = _validate_webhook(slack_webhook)
    if llm_base_url is not None:
        config_values["llm_base_url"] = llm_base_url
    if llm_model is not None:
        config_values["llm_model"] = llm_model

    root.mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    mandate_path.write_text(dump_mandate(_scaffold_mandate(agent)), encoding="utf-8")
    config_path.write_text(_dump_toml(config_values), encoding="utf-8")


def load_config(directory: Path | str) -> AlfredConfig:
    """Load `.alfred/config.toml` relative to `directory` (the project root).

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

    webhook = raw.get("slack_webhook_url")
    llm_base_url = raw.get("llm_base_url")
    llm_model = raw.get("llm_model")
    return AlfredConfig(
        mandate_path=mandate_path,
        trace_db_path=trace_db_path,
        slack_webhook_url=str(webhook) if webhook else None,
        llm_base_url=str(llm_base_url) if llm_base_url else None,
        llm_model=str(llm_model) if llm_model else None,
    )


def build_llm_client(config: AlfredConfig) -> LLMClient | None:
    """Build the narration LLM client from config + env, or None if unconfigured.

    Returns a client only when the endpoint (`llm_base_url` + `llm_model`, from
    `.alfred/config.toml`) and the API key (env `ALFRED_LLM_API_KEY`, never
    written to disk) are all present. A missing piece yields None so the caller
    can fail loudly with a precise message rather than half-configure narration.
    """
    api_key = os.environ.get(LLM_API_KEY_ENV)
    if not (config.llm_base_url and config.llm_model and api_key):
        return None
    return OpenAICompatibleClient(
        base_url=config.llm_base_url, api_key=api_key, model=config.llm_model
    )
