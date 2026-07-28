"""Declarative PII/secret redaction, applied at the ingestion boundary.

See docs/adr/0022-pii-redaction.md (revised by docs/adr/0025-leak-containment.md)
and tests/test_trace_redact.py for the falsifiable specification. A
`Mandate.redact` set names the attribute values to mask; a `Redactor` replaces
each with a keyed token *before* the event reaches the trace store, so the raw
value never lands in SQLite and never travels to Slack, the HTML report, or the
narration LLM.

The mask is `redacted:hmac:<12 hex>` — an HMAC-SHA256 under a per-project key
(`.alfred/redaction-key`, mode 0600, created on first use). It hides the content
but preserves equality *within a project* (identical values → identical token,
distinct values → distinct tokens), so `loop_detected` and repeated-call
detection stay correct on a masked argument. The key is what an unsalted digest
lacked: without it, a low-entropy value like an email address was recoverable
from the token by dictionary attack (ADR 0025 decision 3).
"""

from __future__ import annotations

import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alfred._fs import write_private

_TOOL_ARGS_PREFIX = "tool.arguments."
# Standard semconv packs every argument into one JSON string; `ingest` flattens
# its scalars but keeps the blob, so redaction has to descend into it.
_TOOL_ARGS_JSON_ATTR = "gen_ai.tool.call.arguments"

_KEY_FILENAME = "redaction-key"
_KEY_BYTES = 32
_TOKEN_HEX = 12


def redaction_key_path(project_dir: Path | str) -> Path:
    return Path(project_dir) / ".alfred" / _KEY_FILENAME


def load_or_create_key(project_dir: Path | str) -> bytes:
    """The project's redaction key, generated on first use.

    Written with owner-only permissions: it is the secret that keeps a masked
    value from being brute-forced back. Callers only reach here when a mandate
    actually declares `redact`, so a project that redacts nothing never grows a
    key file.
    """
    path = redaction_key_path(project_dir)
    if path.exists():
        return bytes.fromhex(path.read_text(encoding="utf-8").strip())
    key = os.urandom(_KEY_BYTES)
    write_private(path, key.hex())
    return key


@dataclass(frozen=True, slots=True)
class Redactor:
    """The names to mask and the key to mask them under.

    Carrying both together is deliberate: the key cannot be forgotten at a call
    site the way a separate parameter could.
    """

    names: frozenset[str]
    key: bytes

    def value(self, value: object) -> str:
        """The stable mask for one value under this project's key."""
        digest = hmac.new(self.key, str(value).encode("utf-8"), "sha256").hexdigest()
        return f"redacted:hmac:{digest[:_TOKEN_HEX]}"

    def apply(self, attributes: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of `attributes` with every named value masked.

        Empty `names` → the same mapping is returned unchanged (the common,
        zero-cost path). Never mutates its input.
        """
        if not self.names:
            return attributes
        redacted: dict[str, Any] = {}
        for key, item in attributes.items():
            if self._is_named(key):
                redacted[key] = self.value(item)
            elif key == _TOOL_ARGS_JSON_ATTR:
                redacted[key] = self._arguments_blob(item)
            else:
                redacted[key] = item
        return redacted

    def _is_named(self, key: str) -> bool:
        """An attribute is redacted if its key is named directly, or if it is a
        `tool.arguments.<name>` whose `<name>` is named — so a mandate can list a
        bare argument name (`customer_email`) or a full attribute key
        (`gen_ai.prompt`).
        """
        if key in self.names:
            return True
        return key.startswith(_TOOL_ARGS_PREFIX) and key[len(_TOOL_ARGS_PREFIX) :] in self.names

    def _arguments_blob(self, raw: Any) -> Any:
        """Mask named fields inside the `gen_ai.tool.call.arguments` JSON string.

        `alfred.trace.ingest` copies the blob's scalars out to
        `tool.arguments.<name>` but keeps the blob itself, so masking only the
        copies left the declared PII in clear text all the way into SQLite (ADR
        0025 decision 1). A blob that cannot be parsed is masked whole: what
        cannot be inspected cannot be cleared (decision 2).
        """
        if not isinstance(raw, str):
            return self.value(raw)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return self.value(raw)
        return json.dumps(self._walk(parsed))

    def _walk(self, value: Any) -> Any:
        """Mask every named key inside a parsed JSON structure, at any depth."""
        if isinstance(value, dict):
            return {
                key: self.value(item) if key in self.names else self._walk(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._walk(item) for item in value]
        return value


def redactor_for(project_dir: Path | str, names: frozenset[str]) -> Redactor | None:
    """The `Redactor` for a project, or None when the mandate redacts nothing.

    Returning None (rather than an empty `Redactor`) keeps the no-redaction
    path from creating a key file for a project that has no secret to protect.
    """
    if not names:
        return None
    return Redactor(names=names, key=load_or_create_key(project_dir))
