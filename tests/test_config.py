"""alfred.config — project scaffolding + config roundtrip.

See PLAN.md §5 Brique 5 (`test_init_creates_config`) and
docs/adr/0007-brique5-delivery-cli-design.md.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

from alfred.config import (
    LLM_API_KEY_ENV,
    SLACK_WEBHOOK_ENV,
    ConfigError,
    build_llm_client,
    init_project,
    load_config,
)
from alfred.mandate.yaml_io import load_mandate
from alfred.narrate.llm import OpenAICompatibleClient

_WEBHOOK = "https://hooks.slack.com/services/T0/B0/xyz"


def test_init_creates_config(tmp_path: Path) -> None:
    init_project(tmp_path, agent="refund-bot-v3")
    assert (tmp_path / "mandate.yaml").is_file()
    assert (tmp_path / ".alfred" / "config.toml").is_file()


def test_init_scaffolds_a_loadable_mandate(tmp_path: Path) -> None:
    init_project(tmp_path, agent="refund-bot-v3")
    mandate = load_mandate(tmp_path / "mandate.yaml")
    assert mandate.agent == "refund-bot-v3"


def test_init_raises_if_mandate_already_exists(tmp_path: Path) -> None:
    (tmp_path / "mandate.yaml").write_text("agent: existing\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="already exists"):
        init_project(tmp_path, agent="refund-bot-v3")


def test_init_raises_if_config_already_exists(tmp_path: Path) -> None:
    config_dir = tmp_path / ".alfred"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text("mandate_path = \"mandate.yaml\"\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="already exists"):
        init_project(tmp_path, agent="refund-bot-v3")


def test_load_config_roundtrips_paths(tmp_path: Path) -> None:
    init_project(tmp_path, agent="refund-bot-v3")
    config = load_config(tmp_path)
    assert config.mandate_path == tmp_path / "mandate.yaml"
    assert config.trace_db_path == tmp_path / ".alfred" / "trace.db"
    assert config.slack_webhook_url is None


def test_init_writes_slack_webhook_from_arg(tmp_path: Path) -> None:
    url = "https://hooks.slack.com/services/T0/B0/xyz"
    init_project(tmp_path, agent="refund-bot-v3", slack_webhook=url)
    assert load_config(tmp_path).slack_webhook_url == url


def test_init_rejects_non_https_slack_webhook(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="https"):
        init_project(tmp_path, agent="refund-bot-v3", slack_webhook="http://insecure/hook")
    assert not (tmp_path / "mandate.yaml").exists()


def test_load_config_reads_slack_webhook_url(tmp_path: Path) -> None:
    init_project(tmp_path, agent="refund-bot-v3")
    config_path = tmp_path / ".alfred" / "config.toml"
    with config_path.open("a", encoding="utf-8") as handle:
        handle.write('slack_webhook_url = "https://hooks.slack.com/services/T0/B0/xyz"\n')
    config = load_config(tmp_path)
    assert config.slack_webhook_url == "https://hooks.slack.com/services/T0/B0/xyz"


def test_load_config_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="no Alfred project found"):
        load_config(tmp_path)


def test_load_config_raises_on_invalid_toml(tmp_path: Path) -> None:
    config_dir = tmp_path / ".alfred"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text("not = valid = toml\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid config TOML"):
        load_config(tmp_path)


def test_init_writes_and_load_reads_llm_endpoint(tmp_path: Path) -> None:
    init_project(
        tmp_path,
        agent="refund-bot-v3",
        llm_base_url="https://api.example.com/v1",
        llm_model="gpt-4o-mini",
    )
    config = load_config(tmp_path)
    assert config.llm_base_url == "https://api.example.com/v1"
    assert config.llm_model == "gpt-4o-mini"


def test_load_config_llm_endpoint_absent_is_none(tmp_path: Path) -> None:
    init_project(tmp_path, agent="refund-bot-v3")
    config = load_config(tmp_path)
    assert config.llm_base_url is None
    assert config.llm_model is None


def test_build_llm_client_none_when_endpoint_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LLM_API_KEY_ENV, "secret")  # key present, endpoint absent
    init_project(tmp_path, agent="refund-bot-v3")
    assert build_llm_client(load_config(tmp_path)) is None


def test_build_llm_client_none_without_api_key_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(LLM_API_KEY_ENV, raising=False)  # endpoint present, key absent
    init_project(
        tmp_path, agent="refund-bot-v3", llm_base_url="https://api.example.com/v1", llm_model="m"
    )
    assert build_llm_client(load_config(tmp_path)) is None


def test_build_llm_client_builds_client_when_fully_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LLM_API_KEY_ENV, "secret")
    init_project(
        tmp_path,
        agent="refund-bot-v3",
        llm_base_url="https://api.example.com/v1",
        llm_model="gpt-4o-mini",
    )
    client = build_llm_client(load_config(tmp_path))
    assert isinstance(client, OpenAICompatibleClient)
    assert client.base_url == "https://api.example.com/v1"
    assert client.model == "gpt-4o-mini"
    assert client.api_key == "secret"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes don't exist on Windows")
def test_config_file_is_owner_only(tmp_path: Path) -> None:
    """ADR 0025 decision 7: the webhook's path is the credential, and the file
    holding it used to be world-readable."""
    init_project(tmp_path, agent="bot", slack_webhook=_WEBHOOK)
    config_path = tmp_path / ".alfred" / "config.toml"
    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600


def test_env_webhook_wins_over_the_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So a deployer can keep the secret off disk entirely."""
    init_project(tmp_path, agent="bot", slack_webhook=_WEBHOOK)
    from_env = "https://hooks.slack.com/services/T9/B9/from-env"
    monkeypatch.setenv(SLACK_WEBHOOK_ENV, from_env)
    assert load_config(tmp_path).slack_webhook_url == from_env


def test_load_rejects_a_cleartext_webhook_added_by_hand(tmp_path: Path) -> None:
    """Validating only at init left a hand-edited http:// to be discovered by
    the request itself — in clear text."""
    init_project(tmp_path, agent="bot")
    config_path = tmp_path / ".alfred" / "config.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + 'slack_webhook_url = "http://hooks.slack.com/services/T0/B0/x"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="https://"):
        load_config(tmp_path)


def test_load_warns_on_a_non_slack_webhook_host(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A wrong host is an exfiltration channel; a compatible endpoint is a
    legitimate setup — so this warns rather than refuses (decision 8)."""
    init_project(tmp_path, agent="bot", slack_webhook="https://attacker.example/collect")
    config = load_config(tmp_path)
    assert config.slack_webhook_url == "https://attacker.example/collect"
    assert "attacker.example" in capsys.readouterr().err


def test_init_rejects_a_cleartext_llm_endpoint(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="https://"):
        init_project(tmp_path, agent="bot", llm_base_url="http://api.example/v1")


def test_init_accepts_a_loopback_llm_endpoint(tmp_path: Path) -> None:
    """The self-hosted-model case: the key never reaches a wire."""
    init_project(tmp_path, agent="bot", llm_base_url="http://127.0.0.1:11434/v1")
    assert load_config(tmp_path).llm_base_url == "http://127.0.0.1:11434/v1"
