"""Static mandate validation — `alfred mandate lint`.

See docs/adr/0018-mandate-bootstrap-and-lint.md.
"""

from __future__ import annotations

from pathlib import Path

from alfred.mandate.lint import Severity, lint_mandate

EXAMPLE_MANDATE = Path(__file__).parent.parent / "examples" / "mandates" / "refund-bot.yaml"

_VALID_MANDATE = (
    "agent: refund-bot-v3\n"
    "allowed_tools: [read_order]\n"
    "daily_budget_eur: 5.0\n"
    "forbidden_actions: []\n"
    "escalate_when: [tool_error_rate > 0.10]\n"
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "mandate.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_lint_clean_example_mandate_has_no_findings() -> None:
    assert lint_mandate(EXAMPLE_MANDATE) == []


def test_lint_unknown_escalation_metric_is_error(tmp_path: Path) -> None:
    path = _write(tmp_path, _VALID_MANDATE.replace("tool_error_rate", "tool_errors"))
    findings = lint_mandate(path)
    assert [f.severity for f in findings] == [Severity.ERROR]
    assert "tool_errors" in findings[0].message


def test_lint_empty_allowed_tools_is_warning(tmp_path: Path) -> None:
    path = _write(tmp_path, _VALID_MANDATE.replace("[read_order]", "[]"))
    findings = lint_mandate(path)
    assert [f.severity for f in findings] == [Severity.WARNING]
    assert "allowed_tools" in findings[0].message


def test_lint_nonpositive_budget_is_warning(tmp_path: Path) -> None:
    path = _write(tmp_path, _VALID_MANDATE.replace("daily_budget_eur: 5.0", "daily_budget_eur: 0"))
    findings = lint_mandate(path)
    assert [f.severity for f in findings] == [Severity.WARNING]
    assert "daily_budget_eur" in findings[0].message


def test_lint_redact_shadowing_forbidden_arg_warns(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "agent: sql-analyst\n"
        "allowed_tools: [execute_sql]\n"
        "daily_budget_eur: 5.0\n"
        "forbidden_actions:\n"
        "  - tool: execute_sql\n"
        "    when: args.rows_affected > 1000\n"
        "escalate_when: []\n"
        "redact: [rows_affected]\n",
    )
    findings = lint_mandate(path)
    assert [f.severity for f in findings] == [Severity.WARNING]
    assert "rows_affected" in findings[0].message


def test_lint_redact_without_shadow_is_clean(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "agent: sql-analyst\n"
        "allowed_tools: [execute_sql]\n"
        "daily_budget_eur: 5.0\n"
        "forbidden_actions:\n"
        "  - tool: execute_sql\n"
        "    when: args.rows_affected > 1000\n"
        "escalate_when: []\n"
        "redact: [customer_email]\n",
    )
    assert lint_mandate(path) == []


def test_lint_malformed_mandate_is_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "agent: [unterminated\n")
    findings = lint_mandate(path)
    assert [f.severity for f in findings] == [Severity.ERROR]


def test_lint_missing_file_is_error(tmp_path: Path) -> None:
    findings = lint_mandate(tmp_path / "does-not-exist.yaml")
    assert [f.severity for f in findings] == [Severity.ERROR]
