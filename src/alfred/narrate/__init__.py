"""Verified NLG — Digest → prose, anchored to event IDs (see PLAN.md §5 Brique 4)."""

from __future__ import annotations

from alfred.narrate.llm import (
    HTTPRequest,
    LLMClient,
    NarrateError,
    OpenAICompatibleClient,
    Transport,
    extract_event_ids,
    narrate,
)
from alfred.narrate.model import NarratedDigest, Sentence

__all__ = [
    "HTTPRequest",
    "LLMClient",
    "NarrateError",
    "NarratedDigest",
    "OpenAICompatibleClient",
    "Sentence",
    "Transport",
    "extract_event_ids",
    "narrate",
]
