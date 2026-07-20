"""Mandate YAML (de)serialization.

See PLAN.md §5 Brique 2 for the target mandate format and
tests/test_mandate_yaml.py for the falsifiable specification.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml

from alfred.mandate.model import EscalationRule, ForbiddenRule, Mandate, MandateError

# Shared `<op> <number>` tail of every condition string (escalate_when
# metrics and structured-rule `when:` conditions use the same grammar).
_CONDITION_TAIL = r"\s*(?P<op>>=|<=|==|>|<)\s*(?P<threshold>[\d.]+)\s*$"

_ESCALATION_PATTERN = re.compile(r"^\s*(?P<metric>[a-z_]+)" + _CONDITION_TAIL)

_WHEN_PATTERN = re.compile(r"^\s*args\.(?P<arg>[A-Za-z_][A-Za-z0-9_]*)" + _CONDITION_TAIL)

_REQUIRED_KEYS = (
    "agent",
    "allowed_tools",
    "daily_budget_eur",
    "forbidden_actions",
    "escalate_when",
)


def _parse_forbidden_action(raw: object) -> str | ForbiddenRule:
    """One `forbidden_actions` entry: legacy string, or `tool:`/`when:` mapping."""
    if not isinstance(raw, dict):
        return str(raw)
    if set(raw) != {"tool", "when"}:
        raise MandateError(
            f"Structured forbidden_actions entry must have exactly 'tool' and 'when' keys: {raw!r}"
        )
    when = str(raw["when"])
    match = _WHEN_PATTERN.match(when)
    if match is None:
        raise MandateError(
            f"Malformed 'when' condition (expected 'args.<arg> <op> <number>'): {when!r}"
        )
    return ForbiddenRule(
        tool=str(raw["tool"]),
        arg=match["arg"],
        operator=match["op"],
        threshold=float(match["threshold"]),
    )


def _dump_forbidden_action(action: str | ForbiddenRule) -> str | dict[str, str]:
    if isinstance(action, ForbiddenRule):
        return {"tool": action.tool, "when": action.when}
    return action


def _parse_escalation_rule(raw: str) -> EscalationRule:
    match = _ESCALATION_PATTERN.match(raw)
    if match is None:
        raise MandateError(f"Malformed escalate_when entry: {raw!r}")
    return EscalationRule(
        metric=match["metric"],
        operator=match["op"],
        threshold=float(match["threshold"]),
    )


def _mandate_from_dict(raw: dict[str, Any]) -> Mandate:
    missing = [key for key in _REQUIRED_KEYS if key not in raw]
    if missing:
        raise MandateError(f"Mandate is missing required keys: {missing}")
    try:
        return Mandate(
            agent=str(raw["agent"]),
            allowed_tools=frozenset(str(tool) for tool in raw["allowed_tools"]),
            daily_budget_eur=float(raw["daily_budget_eur"]),
            forbidden_actions=tuple(
                _parse_forbidden_action(action) for action in raw["forbidden_actions"]
            ),
            escalate_when=tuple(
                _parse_escalation_rule(str(rule)) for rule in raw["escalate_when"]
            ),
        )
    except (TypeError, ValueError) as exc:
        raise MandateError(f"Malformed mandate: {exc}") from exc


def load_mandate(path: Path | str) -> Mandate:
    """Parse a mandate YAML file into a `Mandate`.

    Raises `MandateError` on malformed YAML or a missing/invalid required key.
    """
    text = Path(path).read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise MandateError(f"Invalid mandate YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise MandateError("Mandate YAML must be a mapping at the top level")
    return _mandate_from_dict(cast("dict[str, Any]", raw))


def dump_mandate(mandate: Mandate) -> str:
    """Serialize a `Mandate` back to YAML text (inverse of `load_mandate`)."""
    raw: dict[str, Any] = {
        "agent": mandate.agent,
        "allowed_tools": sorted(mandate.allowed_tools),
        "daily_budget_eur": mandate.daily_budget_eur,
        "forbidden_actions": [
            _dump_forbidden_action(action) for action in mandate.forbidden_actions
        ],
        "escalate_when": [
            f"{rule.metric} {rule.operator} {rule.threshold}" for rule in mandate.escalate_when
        ],
    }
    return yaml.safe_dump(raw, sort_keys=False)
