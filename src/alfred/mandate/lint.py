"""Static validation of a mandate file — `alfred mandate lint`.

`load_mandate` already rejects malformed YAML and missing keys; `lint` adds
the *semantic* checks that would otherwise only surface at `watch` time. See
docs/adr/0018-mandate-bootstrap-and-lint.md and tests/test_mandate_lint.py for
the falsifiable specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from alfred.mandate.engine import KNOWN_ESCALATION_METRICS
from alfred.mandate.model import Mandate, MandateError
from alfred.mandate.yaml_io import load_mandate


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class LintFinding:
    severity: Severity
    message: str


def _check_escalation_metrics(mandate: Mandate) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for rule in mandate.escalate_when:
        if rule.metric not in KNOWN_ESCALATION_METRICS:
            findings.append(
                LintFinding(
                    Severity.ERROR,
                    f"unknown escalation metric {rule.metric!r} "
                    f"(known: {sorted(KNOWN_ESCALATION_METRICS)}) — it would crash `alfred watch`",
                )
            )
    return findings


def _check_allowed_tools(mandate: Mandate) -> list[LintFinding]:
    if not mandate.allowed_tools:
        return [
            LintFinding(
                Severity.WARNING,
                "allowed_tools is empty — every tool call will raise tool_not_allowed",
            )
        ]
    return []


def _check_budget(mandate: Mandate) -> list[LintFinding]:
    if mandate.daily_budget_eur <= 0:
        return [
            LintFinding(
                Severity.WARNING,
                f"daily_budget_eur is {mandate.daily_budget_eur} — any spend will raise "
                "budget_exceeded",
            )
        ]
    return []


def lint_mandate(path: Path | str) -> list[LintFinding]:
    """Validate a mandate file, returning every finding (empty when clean).

    A parse/load failure (malformed YAML, missing key, missing file) is a
    single `error` finding — the mandate cannot be inspected further. A valid
    mandate is then checked semantically: unknown escalation metric (error),
    empty allowed_tools (warning), non-positive budget (warning).
    """
    try:
        mandate = load_mandate(path)
    except MandateError as exc:
        return [LintFinding(Severity.ERROR, str(exc))]
    except OSError as exc:
        return [LintFinding(Severity.ERROR, f"cannot read {path}: {exc}")]

    return [
        *_check_escalation_metrics(mandate),
        *_check_allowed_tools(mandate),
        *_check_budget(mandate),
    ]
