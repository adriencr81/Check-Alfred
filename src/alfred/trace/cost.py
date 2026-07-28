"""Cost of a trace event in EUR, shared by the report and the mandate engine.

Priority: the cost computed from the event's token counts and the pricing
table wins; the agent-declared `gen_ai.usage.cost_eur` is only the fallback
when nothing is computable (unknown model, missing tokens); otherwise 0.0.
The order was the reverse until ADR 0023 decision 2 — a self-reported cost
outranking the computed one let an agent erase its own spend from the digest
and from the budget check. Extracted from `alfred.report.build` for
Brique 9 (PLAN.md §12, ADR 0013 decision 4) so budget checks and the digest
cost line always agree to the cent.
"""

from __future__ import annotations

from collections.abc import Iterable

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
    # OpenAI (GPT-5.6 family; gpt-5.6 is the alias for Sol)
    "gpt-5.6": (0.005, 0.030),
    "gpt-5.6-sol": (0.005, 0.030),
    "gpt-5.6-terra": (0.0025, 0.015),
    "gpt-5.6-luna": (0.001, 0.006),
    # Google (Gemini; flat under-200k rate — the table carries no context tier)
    "gemini-3.1-pro-preview": (0.002, 0.012),
    "gemini-3.5-flash": (0.0015, 0.009),
    "gemini-3-flash-preview": (0.0005, 0.003),
    "gemini-3.1-flash-lite": (0.00025, 0.0015),
    # DeepSeek (api-docs.deepseek.com/quick_start/pricing; unified V3.2 list
    # price of $0.28/1M input, $0.42/1M output, converted at 1 USD ≈ 0.90 EUR)
    "deepseek-chat": (0.00025, 0.00038),
    "deepseek-reasoner": (0.00025, 0.00038),
}


def contributing_costs(events: Iterable[TraceEvent]) -> list[tuple[TraceEvent, float]]:
    """Each event with a positive EUR cost, paired with that cost.

    The single definition of "what contributes to spend", shared by the report
    cost line and the engine's budget checks so the displayed cost and the
    budget deviation can never disagree on which events count.
    """
    return [(event, cost) for event in events if (cost := event_cost_eur(event)) > 0.0]


def declared_cost_eur(event: TraceEvent) -> float | None:
    """The `gen_ai.usage.cost_eur` the agent wrote, or None if it wrote none.

    Self-reported: never trusted over a computable price (`event_cost_eur`),
    and compared against it by the engine's `cost_mismatch` check.
    """
    cost = event.attributes.get(_COST_ATTR)
    return float(cost) if isinstance(cost, int | float) else None


def computed_cost_eur(event: TraceEvent) -> float | None:
    """The cost priced from the event's own token counts, or None if it cannot
    be computed (model absent from the pricing table, or missing token counts)."""
    model = event.attributes.get(_MODEL_ATTR)
    rates = _PRICING_EUR_PER_1K_TOKENS.get(model) if isinstance(model, str) else None
    input_tokens = event.attributes.get(_INPUT_TOKENS_ATTR)
    output_tokens = event.attributes.get(_OUTPUT_TOKENS_ATTR)
    if (
        rates is None
        or not isinstance(input_tokens, int | float)
        or not isinstance(output_tokens, int | float)
    ):
        return None
    rate_in, rate_out = rates
    return (input_tokens / 1000) * rate_in + (output_tokens / 1000) * rate_out


def event_cost_eur(event: TraceEvent) -> float:
    """EUR cost of one event: tokens priced by model, else declared cost, else 0.0.

    The computed price wins (ADR 0023 decision 2): `gen_ai.usage.cost_eur` is
    written by the audited agent, so letting it win turned the digest's cost
    line — and the budget check reading the same function — into a
    self-reported claim. The declared value remains the fallback when nothing
    is computable, which keeps an unknown model priced rather than free.
    """
    computed = computed_cost_eur(event)
    if computed is not None:
        return computed
    declared = declared_cost_eur(event)
    return declared if declared is not None else 0.0
