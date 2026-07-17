"""Minimal Block Kit structural validator for tests.

See tests/fixtures/block_kit_constraints.json and
docs/adr/0007-brique5-delivery-cli-design.md: Slack does not publish a
downloadable official JSON Schema for Block Kit, so this checks a payload
against a fixture of the documented constraints for the block types Alfred
emits, rather than pulling in a general-purpose JSON Schema validator for
one fixed shape.
"""

from __future__ import annotations

from typing import Any


class BlockKitValidationError(AssertionError):
    """Raised when a payload violates the Block Kit constraints fixture."""


def assert_valid_block_kit_payload(payload: dict[str, Any], constraints: dict[str, Any]) -> None:
    blocks = payload.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise BlockKitValidationError("payload must have a non-empty 'blocks' list")
    if len(blocks) > constraints["max_blocks"]:
        raise BlockKitValidationError(f"more than {constraints['max_blocks']} blocks")

    limits = constraints["block_text_limits"]
    for block in blocks:
        block_type = block.get("type")
        if block_type not in limits:
            raise BlockKitValidationError(f"unsupported block type: {block_type!r}")
        text = block.get("text")
        if not isinstance(text, dict):
            raise BlockKitValidationError(f"block of type {block_type!r} is missing 'text'")

        text_type = text.get("type")
        allowed_text_types = limits[block_type]["text_types"]
        if text_type not in allowed_text_types:
            raise BlockKitValidationError(
                f"block {block_type!r} text.type must be one of {allowed_text_types}, "
                f"got {text_type!r}"
            )

        text_value = text.get("text")
        max_length = limits[block_type]["max_length"]
        if not isinstance(text_value, str) or not text_value:
            raise BlockKitValidationError(
                f"block {block_type!r} text.text must be a non-empty string"
            )
        if len(text_value) > max_length:
            raise BlockKitValidationError(
                f"block {block_type!r} text.text exceeds {max_length} characters"
            )
