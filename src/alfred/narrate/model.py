"""Narrated digest model — prose sentences anchored to a `Line`.

Invariant (see PLAN.md §3 and docs/verified_nlg.md): a `NarratedDigest` must
only ever contain `Sentence`s whose citations are a verified subset of their
originating `Line.sources`. Unlike `Line`/`Deviation`, this contract is not
enforced by a `__post_init__` here — it is enforced actively by
`alfred.narrate.llm.narrate`, so this module stays pure data with no
dependency on the LLM/citation-extraction logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from alfred.report.model import Digest, Line


@dataclass(frozen=True, slots=True)
class Sentence:
    text: str
    line: Line


@dataclass(frozen=True, slots=True)
class NarratedDigest:
    digest: Digest
    sentences: tuple[Sentence, ...]
