"""Declarative PII/secret redaction, applied at the ingestion boundary.

See docs/adr/0022-pii-redaction.md and tests/test_trace_redact.py for the
falsifiable specification. A `Mandate.redact` set names the attribute values to
mask; `redact_attributes` replaces each with a stable hash *before* the event
reaches the trace store, so the raw value never lands in SQLite and never
travels to Slack, the HTML report, or the narration LLM.

The mask is `redacted:sha256:<12 hex>` — it hides the content but preserves
equality (identical values → identical token, distinct values → distinct
tokens), so `loop_detected` and repeated-call detection stay correct on a
masked argument.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_TOOL_ARGS_PREFIX = "tool.arguments."
# Standard semconv packs every argument into one JSON string; `ingest` flattens
# its scalars but keeps the blob, so redaction has to descend into it.
_TOOL_ARGS_JSON_ATTR = "gen_ai.tool.call.arguments"


def redact_value(value: object) -> str:
    """The stable mask for one value: `redacted:sha256:` + 12 hex of its SHA-256.

    Deterministic and unsalted (see ADR 0022 limits): the same value always
    masks to the same token, so equality-based checks survive redaction.
    """
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
    return f"redacted:sha256:{digest}"


def _is_redacted(key: str, names: frozenset[str]) -> bool:
    """An attribute is redacted if its key is named directly, or if it is a
    `tool.arguments.<name>` whose `<name>` is named — so a mandate can list a
    bare argument name (`customer_email`) or a full attribute key (`gen_ai.prompt`).
    """
    if key in names:
        return True
    return key.startswith(_TOOL_ARGS_PREFIX) and key[len(_TOOL_ARGS_PREFIX) :] in names


def _redact_json(value: Any, names: frozenset[str]) -> Any:
    """Mask every named key inside a parsed JSON structure, at any depth."""
    if isinstance(value, dict):
        return {
            key: redact_value(item) if key in names else _redact_json(item, names)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_json(item, names) for item in value]
    return value


def _redact_arguments_blob(raw: Any, names: frozenset[str]) -> Any:
    """Mask named fields inside the `gen_ai.tool.call.arguments` JSON string.

    `alfred.trace.ingest` copies the blob's scalars out to
    `tool.arguments.<name>` but keeps the blob itself, so masking only the
    copies left the declared PII in clear text all the way into SQLite (ADR
    0025 decision 1). A blob that cannot be parsed is masked whole: what
    cannot be inspected cannot be cleared (decision 2).
    """
    if not isinstance(raw, str):
        return redact_value(raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return redact_value(raw)
    return json.dumps(_redact_json(parsed, names))


def redact_attributes(attributes: dict[str, Any], names: frozenset[str]) -> dict[str, Any]:
    """Return a copy of `attributes` with every named value replaced by its mask.

    `names` empty → the same mapping is returned unchanged (the common,
    zero-cost path). Never mutates its input.
    """
    if not names:
        return attributes
    redacted: dict[str, Any] = {}
    for key, value in attributes.items():
        if _is_redacted(key, names):
            redacted[key] = redact_value(value)
        elif key == _TOOL_ARGS_JSON_ATTR:
            redacted[key] = _redact_arguments_blob(value, names)
        else:
            redacted[key] = value
    return redacted
