"""Mandate YAML (de)serialization — see PLAN.md §5 Brique 2."""

from __future__ import annotations

from pathlib import Path

import pytest

from alfred.mandate.model import EscalationRule, Mandate, MandateError
from alfred.mandate.yaml_io import dump_mandate, load_mandate

EXAMPLE_MANDATE = Path(__file__).parent.parent / "examples" / "mandates" / "refund-bot.yaml"


def _mandate() -> Mandate:
    return Mandate(
        agent="refund-bot-v3",
        allowed_tools=frozenset({"read_order", "issue_refund", "notify_customer"}),
        daily_budget_eur=5.0,
        forbidden_actions=("issue_refund_above_100_eur", "send_marketing"),
        escalate_when=(
            EscalationRule("tool_error_rate", ">", 0.10),
            EscalationRule("budget_used", ">", 0.80),
        ),
    )


def test_mandate_yaml_roundtrip(tmp_path: Path) -> None:
    mandate = _mandate()
    path = tmp_path / "mandate.yaml"
    path.write_text(dump_mandate(mandate), encoding="utf-8")
    assert load_mandate(path) == mandate


def test_load_example_mandate_matches_plan_spec() -> None:
    mandate = load_mandate(EXAMPLE_MANDATE)
    assert mandate == _mandate()


def test_load_mandate_missing_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "mandate.yaml"
    path.write_text("agent: refund-bot-v3\n", encoding="utf-8")
    with pytest.raises(MandateError):
        load_mandate(path)


def test_load_mandate_malformed_escalation_raises(tmp_path: Path) -> None:
    path = tmp_path / "mandate.yaml"
    path.write_text(
        "agent: refund-bot-v3\n"
        "allowed_tools: [read_order]\n"
        "daily_budget_eur: 5.0\n"
        "forbidden_actions: []\n"
        'escalate_when: ["not a valid rule"]\n',
        encoding="utf-8",
    )
    with pytest.raises(MandateError):
        load_mandate(path)


def test_load_mandate_invalid_yaml_raises(tmp_path: Path) -> None:
    path = tmp_path / "mandate.yaml"
    path.write_text("agent: [unterminated\n", encoding="utf-8")
    with pytest.raises(MandateError):
        load_mandate(path)
