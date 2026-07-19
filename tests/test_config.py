"""alfred.config — project scaffolding + config roundtrip.

See PLAN.md §5 Brique 5 (`test_init_creates_config`) and
docs/adr/0007-brique5-delivery-cli-design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alfred.config import ConfigError, init_project, load_config
from alfred.mandate.yaml_io import load_mandate


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


def test_load_config_reads_slack_webhook_url(tmp_path: Path) -> None:
    init_project(tmp_path, agent="refund-bot-v3")
    config_path = tmp_path / ".alfred" / "config.toml"
    with config_path.open("a", encoding="utf-8") as handle:
        handle.write('slack_webhook_url = "https://hooks.slack.com/services/T0/B0/xyz"\n')
    config = load_config(tmp_path)
    assert config.slack_webhook_url == "https://hooks.slack.com/services/T0/B0/xyz"


def test_webhook_env_var_wins_over_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B11: the webhook is a secret — the env var overrides the file, so it
    never has to be committed to config.toml at all."""
    init_project(tmp_path, agent="refund-bot-v3")
    config_path = tmp_path / ".alfred" / "config.toml"
    with config_path.open("a", encoding="utf-8") as handle:
        handle.write('slack_webhook_url = "https://hooks.slack.com/services/OLD"\n')
    monkeypatch.setenv("ALFRED_SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/ENV")
    config = load_config(tmp_path)
    assert config.slack_webhook_url == "https://hooks.slack.com/services/ENV"


def test_webhook_env_var_works_without_config_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init_project(tmp_path, agent="refund-bot-v3")
    monkeypatch.setenv("ALFRED_SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/ENV")
    config = load_config(tmp_path)
    assert config.slack_webhook_url == "https://hooks.slack.com/services/ENV"


def test_load_config_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="no Alfred project found"):
        load_config(tmp_path)


def test_load_config_raises_on_invalid_toml(tmp_path: Path) -> None:
    config_dir = tmp_path / ".alfred"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text("not = valid = toml\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid config TOML"):
        load_config(tmp_path)
