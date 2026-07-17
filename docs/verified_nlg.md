# Verified NLG — how Alfred stops its LLM from hallucinating reports

## The rule

CLAUDE.md states it as the absolute product rule, and PLAN.md §1 codifies it
as decision D5:

> Chaque affirmation d'un rapport DOIT être calculée depuis un événement de
> trace identifiable (event ID). Le LLM ne sert QU'À la mise en langage.

`alfred.narrate` is the module that lets a `Digest` (already computed,
already anchored — see [`alfred.report`](../src/alfred/report)) be
optionally reformulated in prose by an LLM, while holding that rule as a
hard, mechanically-checked invariant rather than a hope:

> For every `Sentence` in a `NarratedDigest.sentences`, the event IDs cited
> in `sentence.text` are a non-empty subset of `sentence.line.sources`.

## How it's mechanically enforced

This is not "hopefully verified by a passing test." `alfred.narrate.llm.narrate`
checks the property itself, immediately after every LLM call:

```python
cited = extract_event_ids(text)
if not cited:
    raise NarrateError(...)
if cited - set(line.sources):
    raise NarrateError(...)
```

There is no code path in `narrate()` that can hand back a `NarratedDigest`
containing a `Sentence` that wasn't checked this way — the check runs inline,
per line, before the `Sentence` is ever constructed. Tests
(`tests/test_narrate_llm.py`) exist to prove the checker actually rejects bad
output, not to *be* the checker.

## Fail loudly, never degrade silently

If any line's LLM output fails the guarantee, `narrate()` raises `NarrateError`
immediately and the **whole call aborts** — no partial `NarratedDigest`, no
fallback to unverified prose, no silently dropped line. This mirrors
CLAUDE.md's instruction for the codebase as a whole: *"Si une implémentation
viole [la règle produit] : STOP, replanifier."* A caller that wants a digest
even when narration fails should catch `NarrateError` and fall back to
`alfred.report.render.render(digest)` — the always-available, deterministic,
already-anchored text form — rather than Alfred silently emitting
half-narrated or unverified output.

## Scope: lines, not deviations

Only `Digest.lines` (tasks completed, cost, escalations) go through
`narrate()`. `Digest.deviations` are `Deviation` objects that already carry a
deterministic, code-generated `.message` string anchored to `event_ids` (see
`alfred.mandate.model.Deviation`) — there is no LLM step and therefore no
hallucination risk to guard against, so wrapping them in `narrate()` would
add surface without adding safety. See
[`docs/adr/0006-brique4-verified-nlg-design.md`](adr/0006-brique4-verified-nlg-design.md)
for the record of this decision.

## Citation format

An LLM cites the event IDs backing a sentence with a trailing bracket, in the
same `[evt:id1, id2]` convention already used by
[`alfred.report.render`](../src/alfred/report/render.py) for the deterministic
digest — one format, one regex (`extract_event_ids`), reused across both
verified and narrated output.

## LLM configurability

`narrate(digest, llm_client)` takes any `LLMClient` — a `Protocol` with a
single `complete(prompt: str) -> str` method. Tests use a stub. Production
code can use `alfred.narrate.llm.OpenAICompatibleClient`, a minimal client
(stdlib `urllib.request` only, no new dependency) configurable with
`base_url`, `api_key`, and `model`, that speaks the standard
`POST /chat/completions` shape used by OpenAI and OpenAI-compatible gateways.
Its HTTP transport is an injectable field, so the whole test suite verifies
request/response handling against a fake transport — zero real network calls.

## A concrete failure

Given a `Line(kind=TASKS_COMPLETED, value=2.0, sources=("a1", "a2"))`, if the
configured LLM returns:

```
"The agent completed 2 tasks today. [evt:a1, a3]"
```

`narrate()` raises:

```
NarrateError: LLM cited events not in source ['a3'] for line 'tasks_completed':
'The agent completed 2 tasks today. [evt:a1, a3]'
```

`a3` was never in `line.sources` — the LLM invented (or mixed up) a citation,
and Alfred refuses to ship that sentence.

## See also

- PLAN.md §3 "Contrats internes" and §5 "Brique 4 — Verified NLG" — the
  product spec this module implements.
- `docs/adr/0006-brique4-verified-nlg-design.md` — implementation decisions
  left open by PLAN.md.
- `tests/test_narrate_llm.py` — the falsifiable test suite, including the
  literal PLAN.md test that "embodies the product thesis."
