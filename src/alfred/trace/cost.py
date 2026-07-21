"""Cost of a trace event in EUR, shared by the report and the mandate engine.

Priority: an explicit `gen_ai.usage.cost_eur` attribute always wins;
otherwise the cost is computed from tokens and the pricing table when the
model is known; otherwise 0.0. Extracted from `alfred.report.build` for
Brique 9 (PLAN.md §12, ADR 0013 decision 4) so budget checks and the digest
cost line always agree to the cent.
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
# Anthropic rates use each model's standard (non-introductory) list price so
# the table stays date-free; add new providers only with a sourced price.
_PRICING_EUR_PER_1K_TOKENS: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o-mini": (0.00015, 0.00060),
    "gpt-4o-mini-2024-07-18": (0.00015, 0.00060),
    "gpt-4o": (0.00250, 0.01000),
    "gpt-4o-2024-08-06": (0.00250, 0.01000),
    # Anthropic (Claude)
    "claude-opus-4-8": (0.005, 0.025),
    "claude-opus-4-7": (0.005, 0.025),
    "claude-opus-4-6": (0.005, 0.025),
    "claude-sonnet-5": (0.003, 0.015),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4-5": (0.001, 0.005),
    "claude-fable-5": (0.010, 0.050),
}


def event_cost_eur(event: TraceEvent) -> float:
    """EUR cost of one event: explicit cost_eur, else tokens priced by model, else 0.0."""
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
