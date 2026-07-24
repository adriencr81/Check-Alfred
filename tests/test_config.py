"""alfred.config — project scaffolding + config roundtrip.

See PLAN.md §5 Brique 5 (`test_init_creates_config`) and
docs/adr/0007-brique5-delivery-cli-design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alfred.config import (
    LLM_API_KEY_ENV,
    ConfigError,
    build_llm_client,
    init_project,
    load_config,
)
from alfred.mandate.yaml_io import load_mandate
from alfred.narrate.llm import OpenAICompatibleClient


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
