"""Single definition of an event's cost in EUR.

Both the digest's Cost line (`alfred.report.build`) and the mandate
engine's budget checks (`alfred.mandate.engine`) must see the same number
for the same event — two diverging cost definitions would let the digest
display a spend the budget check never sees. See
docs/plan-simplification-prod.md (S1) and ADR 0011.
"""

from __future__ import annotations

from alfred.trace.model import TraceEvent

_COST_ATTR = "gen_ai.usage.cost_eur"
_MODEL_ATTR = "gen_ai.response.model"
_INPUT_TOKENS_ATTR = "gen_ai.usage.input_tokens"
_OUTPUT_TOKENS_ATTR = "gen_ai.usage.output_tokens"

# €/1K-token rates (input, output), keyed by gen_ai.response.model. Public
# pricing snapshot, not tied to any date — extend as new models are seen.
# See docs/adr/0005-brique3-report-engine-design.md.
_PRICING_EUR_PER_1K_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.00060),
    "gpt-4o-mini-2024-07-18": (0.00015, 0.00060),
    "gpt-4o": (0.00250, 0.01000),
    "gpt-4o-2024-08-06": (0.00250, 0.01000),
}


def event_cost_eur(event: TraceEvent) -> float:
    """Cost of one event: explicit `gen_ai.usage.cost_eur` if present,
    otherwise tokens x pricing table, otherwise 0.0."""
    cost = event.attributes.get(_COST_ATTR)
    if isinstance(cost, int | float):
        return float(cost)
    model = event.attributes.get(_MODEL_ATTR)
    rates = _PRICING_EUR_PER_1K_TOKENS.get(model) if isinstance(model, str) else None
    input_tokens = event.attributes.get(_INPUT_TOKENS_ATTR)
    output_tokens = event.attributes.get(_OUTPUT_TOKENS_ATTR)
    if (
        rates is not None
        and isinstance(input_tokens, int | float)
        and isinstance(output_tokens, int | float)
    ):
        rate_in, rate_out = rates
        return (input_tokens / 1000) * rate_in + (output_tokens / 1000) * rate_out
    return 0.0
