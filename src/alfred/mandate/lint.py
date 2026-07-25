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
from alfred.mandate.model import ForbiddenRule, Mandate, MandateError
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


def _check_escalation_tools(mandate: Mandate) -> list[LintFinding]:
    """Error when `escalate_when` is declared without any `escalation_tools`.

    An escalation is proven by a call to one of those tools (ADR 0023 decision
    4), so a mandate that names none can never satisfy its own thresholds:
    every breach reports `escalation_missed`. That is the intended fail-closed
    behavior, but it must be a deliberate choice — caught here, before `watch`.
    """
    if mandate.escalate_when and not mandate.escalation_tools:
        return [
            LintFinding(
                Severity.ERROR,
                "escalate_when is declared without escalation_tools — no escalation can "
                "ever be proven, so every breach will raise escalation_missed. List the "
                "tool(s) the agent calls to escalate, e.g. `escalation_tools: [notify_human]`",
            )
        ]
    return []


def _check_escalation_tools_are_allowed(mandate: Mandate) -> list[LintFinding]:
    """Warn when an escalation tool is missing from `allowed_tools` — calling it
    would prove the escalation and raise `tool_not_allowed` in the same breath."""
    if not mandate.allowed_tools:
        return []  # already reported by _check_allowed_tools
    orphans = sorted(mandate.escalation_tools - mandate.allowed_tools)
    return [
        LintFinding(
            Severity.WARNING,
            f"escalation tool {tool!r} is not in allowed_tools — calling it would "
            "raise tool_not_allowed",
        )
        for tool in orphans
    ]


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


def _check_redact_shadows_policy(mandate: Mandate) -> list[LintFinding]:
    """Warn when a redacted field is also a structured forbidden rule's argument.

    Masking a value replaces it with a `redacted:sha256:…` token, which no
    longer compares to a numeric threshold: since ADR 0023 decision 6 the rule
    does not stop firing silently — every call to that tool is reported as
    unverifiable instead. Redacting a policy signal is a footgun, not an error
    — the deployer may intend it — so this stays a warning.
    """
    findings: list[LintFinding] = []
    for action in mandate.forbidden_actions:
        if isinstance(action, ForbiddenRule) and action.arg in mandate.redact:
            findings.append(
                LintFinding(
                    Severity.WARNING,
                    f"redact lists {action.arg!r}, which forbidden_actions rule "
                    f"'{action.tool}' checks ({action.when}) — the masked value cannot be "
                    "compared, so every call to that tool is reported as unverifiable",
                )
            )
    return findings


def lint_mandate(path: Path | str) -> list[LintFinding]:
    """Validate a mandate file, returning every finding (empty when clean).

    A parse/load failure (malformed YAML, missing key, missing file) is a
    single `error` finding — the mandate cannot be inspected further. A valid
    mandate is then checked semantically: unknown escalation metric (error),
    `escalate_when` without `escalation_tools` (error), empty allowed_tools
    (warning), non-positive budget (warning), an escalation tool missing from
    allowed_tools (warning), a redacted field that shadows a forbidden rule's
    argument (warning).
    """
    try:
        mandate = load_mandate(path)
    except MandateError as exc:
        return [LintFinding(Severity.ERROR, str(exc))]
    except OSError as exc:
        return [LintFinding(Severity.ERROR, f"cannot read {path}: {exc}")]

    return [
        *_check_escalation_metrics(mandate),
        *_check_escalation_tools(mandate),
        *_check_allowed_tools(mandate),
        *_check_budget(mandate),
        *_check_escalation_tools_are_allowed(mandate),
        *_check_redact_shadows_policy(mandate),
    ]
