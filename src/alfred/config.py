"""Project configuration — `.alfred/config.toml` created by `alfred init`,
read back by `alfred watch`.

See PLAN.md §5 Brique 5 and docs/adr/0007-brique5-delivery-cli-design.md for
the design decisions recorded here (minimal hand-rolled TOML writer instead
of a new dependency, mandate scaffold reuse via `dump_mandate`).
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from alfred._fs import write_private
from alfred._http import endpoint_error
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
# The webhook URL is itself a credential; this env var lets a deployer keep it
# out of the config file entirely, like the API key above (ADR 0025 decision 7).
SLACK_WEBHOOK_ENV = "ALFRED_SLACK_WEBHOOK_URL"
_SLACK_WEBHOOK_HOST = "hooks.slack.com"


class ConfigError(Exception):
    """Raised when a project cannot be initialized or its config cannot be loaded."""


@dataclass(frozen=True, slots=True)
class AlfredConfig:
    mandate_path: Path
    trace_db_path: Path
    slack_webhook_url: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None


# Prepended to the scaffolded mandate.yaml so a first-time user isn't left with
# a bare file of empty lists. `allowed_tools: []` means "no tool is allowed", so
# every tool the agent calls is flagged as a deviation until it's filled in —
# the header says so, and points at the zero-effort way to seed it from traces.
_SCAFFOLD_HEADER = (
    "# Alfred mandate — what your agent MAY do. Edit before you rely on it.\n"
    "#\n"
    "# allowed_tools is empty, which means EVERY tool call is flagged as a\n"
    "# deviation. List the tools the agent is allowed to use, or seed the whole\n"
    "# file from real traces:  alfred mandate init --from-traces traces/ > mandate.yaml\n"
    "#\n"
    "# daily_budget_eur, forbidden_actions and escalate_when are policy YOU\n"
    "# declare — see the examples in examples/mandates/ and docs/integrate.md.\n"
)


def _scaffold_mandate(agent: str) -> Mandate:
    return Mandate(
        agent=agent,
        allowed_tools=frozenset(),
        daily_budget_eur=5.00,
        forbidden_actions=(),
        escalate_when=(),
    )


def _validate_endpoint(url: str, *, what: str) -> str:
    """Return `url` if it is fit to carry a credential, else raise.

    One rule for both endpoints (`alfred._http.endpoint_error`): HTTPS, or
    cleartext to loopback for a self-hosted model. Checked at `init` *and* at
    load — validating only at `init` left a hand-edited `http://` to be
    discovered by the request itself, in clear text (ADR 0025 decision 4). The
    message never repeats the URL's path: a webhook's path is its credential.
    """
    unfit = endpoint_error(url)
    if unfit is not None:
        raise ConfigError(f"{what} {unfit}")
    return url


def _webhook_host_warning(url: str) -> str | None:
    """Warn when a webhook does not point at Slack — the digest carries the
    day's activity, so a wrong host is an exfiltration channel. A warning, not
    an error: Slack-compatible endpoints (Mattermost, internal proxies) are a
    legitimate setup (ADR 0025 decision 8)."""
    host = urllib.parse.urlsplit(url).hostname or ""
    if host.lower() == _SLACK_WEBHOOK_HOST:
        return None
    return (
        f"slack_webhook_url points at {host!r}, not {_SLACK_WEBHOOK_HOST} — "
        "the digest will be sent there"
    )


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
    overwrites an existing project — or if an endpoint URL is unfit to carry a
    credential. The config file is written owner-only.
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
        config_values["slack_webhook_url"] = _validate_endpoint(
            slack_webhook, what="slack webhook"
        )
    if llm_base_url is not None:
        config_values["llm_base_url"] = _validate_endpoint(llm_base_url, what="llm_base_url")
    if llm_model is not None:
        config_values["llm_model"] = llm_model

    root.mkdir(parents=True, exist_ok=True)
    mandate_path.write_text(
        _SCAFFOLD_HEADER + dump_mandate(_scaffold_mandate(agent)), encoding="utf-8"
    )
    # Owner-only: this file carries the Slack webhook, whose path is the
    # credential (ADR 0025 decision 7).
    write_private(config_path, _dump_toml(config_values))


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

    # The env var wins, so a deployer can keep the webhook off disk entirely.
    webhook = os.environ.get(SLACK_WEBHOOK_ENV) or raw.get("slack_webhook_url")
    llm_base_url = raw.get("llm_base_url")
    llm_model = raw.get("llm_model")

    webhook_url = str(webhook) if webhook else None
    if webhook_url is not None:
        _validate_endpoint(webhook_url, what="slack webhook")
        warning = _webhook_host_warning(webhook_url)
        if warning is not None:
            print(f"alfred: warning: {warning}", file=sys.stderr)
    base_url = str(llm_base_url) if llm_base_url else None
    if base_url is not None:
        _validate_endpoint(base_url, what="llm_base_url")

    return AlfredConfig(
        mandate_path=mandate_path,
        trace_db_path=trace_db_path,
        slack_webhook_url=webhook_url,
        llm_base_url=base_url,
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
