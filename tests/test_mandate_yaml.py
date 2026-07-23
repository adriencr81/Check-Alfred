"""Mandate YAML (de)serialization — see PLAN.md §5 Brique 2."""

from __future__ import annotations

from pathlib import Path

import pytest

from alfred.mandate.model import (
    EscalationRule,
    ForbiddenRule,
    Mandate,
    MandateError,
    RequiredAction,
)
from alfred.mandate.yaml_io import dump_mandate, load_mandate

EXAMPLES_DIR = Path(__file__).parent.parent / "examples" / "mandates"
EXAMPLE_MANDATE = EXAMPLES_DIR / "refund-bot.yaml"
EXAMPLE_STRUCTURED_MANDATE = EXAMPLES_DIR / "sql-analyst.yaml"


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
        required_actions=(RequiredAction("issue_refund", "notify_customer"),),
    )


def test_mandate_yaml_roundtrip(tmp_path: Path) -> None:
    mandate = _mandate()
    path = tmp_path / "mandate.yaml"
    path.write_text(dump_mandate(mandate), encoding="utf-8")
    assert load_mandate(path) == mandate


def test_load_example_mandate_matches_plan_spec() -> None:
    mandate = load_mandate(EXAMPLE_MANDATE)
    assert mandate == _mandate()


def test_structured_rule_yaml_roundtrip(tmp_path: Path) -> None:
    mandate = Mandate(
        agent="sql-analyst",
        allowed_tools=frozenset({"execute_sql", "send_report"}),
        daily_budget_eur=3.0,
        forbidden_actions=(
            "drop_table",
            ForbiddenRule("execute_sql", "rows_affected", ">", 1000.0),
        ),
        escalate_when=(EscalationRule("tool_error_rate", ">", 0.10),),
    )
    path = tmp_path / "mandate.yaml"
    path.write_text(dump_mandate(mandate), encoding="utf-8")
    assert load_mandate(path) == mandate


def test_load_example_structured_mandate() -> None:
    mandate = load_mandate(EXAMPLE_STRUCTURED_MANDATE)
    assert mandate.forbidden_actions == (
        "drop_table",
        ForbiddenRule("execute_sql", "rows_affected", ">", 1000.0),
    )


def test_load_mandate_malformed_structured_rule_raises(tmp_path: Path) -> None:
    path = tmp_path / "mandate.yaml"
    path.write_text(
        "agent: sql-analyst\n"
        "allowed_tools: [execute_sql]\n"
        "daily_budget_eur: 3.0\n"
        "forbidden_actions:\n"
        "  - tool: execute_sql\n"
        '    when: "rows_affected above 1000"\n'
        "escalate_when: []\n",
        encoding="utf-8",
    )
    with pytest.raises(MandateError):
        load_mandate(path)


def test_load_mandate_structured_rule_unknown_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "mandate.yaml"
    path.write_text(
        "agent: sql-analyst\n"
        "allowed_tools: [execute_sql]\n"
        "daily_budget_eur: 3.0\n"
        "forbidden_actions:\n"
        "  - tool: execute_sql\n"
        "    unless: never\n"
        "escalate_when: []\n",
        encoding="utf-8",
    )
    with pytest.raises(MandateError):
        load_mandate(path)


def test_load_mandate_malformed_required_action_raises(tmp_path: Path) -> None:
    path = tmp_path / "mandate.yaml"
    path.write_text(
        "agent: refund-bot-v3\n"
        "allowed_tools: [issue_refund, notify_customer]\n"
        "daily_budget_eur: 5.0\n"
        "forbidden_actions: []\n"
        "escalate_when: []\n"
        "required_actions:\n"
        "  - when_tool: issue_refund\n",
        encoding="utf-8",
    )
    with pytest.raises(MandateError):
        load_mandate(path)


def test_load_mandate_loop_threshold_defaults_to_3(tmp_path: Path) -> None:
    path = tmp_path / "mandate.yaml"
    path.write_text(
        "agent: refund-bot-v3\n"
        "allowed_tools: [read_order]\n"
        "daily_budget_eur: 5.0\n"
        "forbidden_actions: []\n"
        "escalate_when: []\n",
        encoding="utf-8",
    )
    assert load_mandate(path).loop_threshold == 3


def test_load_mandate_loop_threshold_override(tmp_path: Path) -> None:
    path = tmp_path / "mandate.yaml"
    path.write_text(
        "agent: refund-bot-v3\n"
        "allowed_tools: [read_order]\n"
        "daily_budget_eur: 5.0\n"
        "forbidden_actions: []\n"
        "escalate_when: []\n"
        "loop_threshold: 5\n",
        encoding="utf-8",
    )
    assert load_mandate(path).loop_threshold == 5


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
