"""Minimal Block Kit structural validator for tests.

See tests/fixtures/block_kit_constraints.json and
docs/adr/0007-brique5-delivery-cli-design.md: Slack does not publish a
downloadable official JSON Schema for Block Kit, so this checks a payload
against a fixture of the documented constraints for the block types Alfred
emits (header, section with text or fields, context), rather than pulling
in a general-purpose JSON Schema validator for one fixed shape.
"""

from __future__ import annotations

from typing import Any


class BlockKitValidationError(AssertionError):
    """Raised when a payload violates the Block Kit constraints fixture."""


def _check_text_object(
    owner: str, text: Any, allowed_text_types: list[str], max_length: int
) -> None:
    if not isinstance(text, dict):
        raise BlockKitValidationError(f"{owner} text must be an object, got {text!r}")
    text_type = text.get("type")
    if text_type not in allowed_text_types:
        raise BlockKitValidationError(
            f"{owner} text.type must be one of {allowed_text_types}, got {text_type!r}"
        )
    text_value = text.get("text")
    if not isinstance(text_value, str) or not text_value:
        raise BlockKitValidationError(f"{owner} text.text must be a non-empty string")
    if len(text_value) > max_length:
        raise BlockKitValidationError(f"{owner} text.text exceeds {max_length} characters")


def _check_header(block: dict[str, Any], limits: dict[str, Any]) -> None:
    _check_text_object("header", block.get("text"), limits["text_types"], limits["max_length"])


def _check_section(block: dict[str, Any], limits: dict[str, Any]) -> None:
    text = block.get("text")
    fields = block.get("fields")
    if text is None and fields is None:
        raise BlockKitValidationError("section must have 'text' or 'fields'")
    if text is not None:
        _check_text_object("section", text, limits["text_types"], limits["max_length"])
    if fields is not None:
        if not isinstance(fields, list) or not fields:
            raise BlockKitValidationError("section 'fields' must be a non-empty list")
        if len(fields) > limits["max_fields"]:
            raise BlockKitValidationError(f"section has more than {limits['max_fields']} fields")
        for field in fields:
            _check_text_object(
                "section field", field, limits["text_types"], limits["field_max_length"]
            )


def _check_context(block: dict[str, Any], limits: dict[str, Any]) -> None:
    elements = block.get("elements")
    if not isinstance(elements, list) or not elements:
        raise BlockKitValidationError("context 'elements' must be a non-empty list")
    if len(elements) > limits["max_elements"]:
        raise BlockKitValidationError(f"context has more than {limits['max_elements']} elements")
    for element in elements:
        _check_text_object(
            "context element", element, limits["element_text_types"], limits["element_max_length"]
        )


def assert_valid_block_kit_payload(payload: dict[str, Any], constraints: dict[str, Any]) -> None:
    blocks = payload.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise BlockKitValidationError("payload must have a non-empty 'blocks' list")
    if len(blocks) > constraints["max_blocks"]:
        raise BlockKitValidationError(f"more than {constraints['max_blocks']} blocks")

    limits = constraints["block_limits"]
    for block in blocks:
        block_type = block.get("type")
        if block_type not in limits:
            raise BlockKitValidationError(f"unsupported block type: {block_type!r}")
        if block_type == "header":
            _check_header(block, limits["header"])
        elif block_type == "section":
            _check_section(block, limits["section"])
        elif block_type == "context":
            _check_context(block, limits["context"])
