# Alfred

[![CI](https://github.com/adriencr81/check-alfred/actions/workflows/ci.yml/badge.svg)](https://github.com/adriencr81/check-alfred/actions/workflows/ci.yml)

> **Accountability layer for AI employees.** A Python package that turns raw
> agent traces into a daily stand-up your team can actually trust — every line
> anchored to a trace event ID.

**Status** — v0.1 core feature-complete, plus a "Bring Your Own Agent" sprint
landed: a public `alfred.instrument` SDK, real-world OTel Collector ingestion,
and a 5-minute example that needs no API key. 151 tests green, mypy --strict,
CI + CodeQL. Public **v0.1 targeted for early August 2026**. Full roadmap:
[PLAN.md](PLAN.md).

---

## The idea in two sentences

You wouldn't hire a human employee without a mandate and a daily stand-up. Alfred
is that layer for your AI employees — declarative mandate in YAML, evidence-anchored
digest in Slack, deviations flagged the moment they happen.

## The rule that makes it different

**Every line of an Alfred report is anchored to one or more trace event IDs.**
The LLM only rephrases what was already computed from the traces. No self-declared
summaries, no hallucinated numbers. A report line without a source event is a bug,
not a feature — and there's a test that says so (see [PLAN.md §5 Brique 4](PLAN.md)).

## What a digest looks like (v0.1 target)

```
Alfred · refund-bot-v3 · 2026-08-30

Tasks completed:          47   [evt:a1c, a1d, a1e, …]
Cost (tokens → €):     3.42 €   [evt:c0f, …]
Escalations:               3   [evt:e01, e02, e03]
Deviations (mandate):      1   [evt:d0a] — tool_not_allowed: `read_pii`
```

Delivered to Slack (v0.1), Teams (v0.2), or stdout / markdown (always).

## Positioning

| Neighbor | What it does | What Alfred does differently |
|---|---|---|
| Langfuse · AgentOps · LangSmith | Developer observability: traces, prompts, tokens, replay. | Manager reporting: mandate vs reality, typed deviations, daily digest legible without a dashboard. |
| Guardrails · NeMo Guardrails | Inline filters on LLM inputs / outputs. | Post-hoc control across the whole agent session, including tool calls and cost. |
| A homegrown Grafana / Datadog dashboard | Aggregated metrics, alerting. | Narrative, anchored, opinionated report — no dashboard design required. |

Alfred is **complementary, not a replacement**. It reads the same OpenTelemetry
GenAI traces your observability stack already emits, so if you run LangSmith,
Langfuse, or any OTel backend, pointing Alfred at those traces needs no
reinstrumentation. The split is the question and the reader: observability asks
*is my agent working?* for the developer debugging it; Alfred asks *did my agent
stay within its mandate?* for the person accountable for it.

## Quickstart

`alfred-ai` isn't on PyPI yet, but `alfred demo` already works today from
a clone — an instrumented fake agent produces a real trace and a real
digest, no mandate file, no Slack webhook, no network call:

```bash
git clone https://github.com/adriencr81/check-alfred.git && cd check-alfred
pip install -e ".[dev]"
alfred demo
```

### Verify a real agent

`alfred demo` replays a scripted scenario. To watch Alfred catch a *real*
agent's deviation — a framework-free Claude tool loop that decides on its
own whether to grant an over-limit refund — see
[`examples/agents/refund_bot/`](examples/agents/refund_bot/). Nothing is
scripted there: the model decides, Alfred verifies.

Once v0.1 ships to PyPI:

```bash
pip install alfred-ai
alfred init --slack-webhook https://hooks.slack.com/…  # mandate.yaml + Slack config
alfred schedule traces/ --at 09:00 >> mycrontab        # one daily crontab line
alfred watch traces/                                   # one pass now (or --loop to keep running)
alfred demo                                            # fake agent → real digest, no setup
```

`alfred watch` is a single pass by design (re-run via cron — `alfred schedule`
prints the line for you). For environments without cron, `alfred watch --loop`
re-scans on an interval until you stop it.

## Plug in your own agent

Alfred verifies *your* agents. The floor is 5 minutes and no credentials:
[`examples/agents/minimal/`](examples/agents/minimal/) is a ~30-line agent
with no LLM and no API key — run it, `alfred watch` it, watch Alfred catch its
over-cap approval. Three honest paths get your real agent's runs to Alfred:

| Path | For agents that… | Status |
|---|---|---|
| **`alfred.instrument` SDK** | you can add ~10 lines to (wrap the loop, model call, tool call) | **works today** — [`docs/integrate.md`](docs/integrate.md) |
| **LangGraph connector** | run on LangGraph — attach one callback handler, no manual instrumentation | **works today** — `pip install alfred-ai[langgraph]` ([connector](docs/integrate.md#langgraph-connector)) |
| **OTel Collector bridge** | already emit OpenTelemetry GenAI spans | **works today** — point the Collector's file exporter at the watched folder ([bridge config](docs/integrate.md#otel-collector-bridge)) |
| **Other native connectors** | run on CrewAI, OpenAI Agents, or a managed platform | **v0.2** — not built yet |

Whatever the path, the guarantee is the same: every digest line is computed
from an identifiable trace event, never self-reported. What Alfred can't see in
the trace, it doesn't claim.

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check . && mypy --strict src/
```

Layout:

```
src/alfred/trace/      # Brique 1 — OTLP ingest, TraceEvent, SQLite store
                       #   + B9 shared token→€ cost, B10 NDJSON / GenAI semconv adaptation
src/alfred/mandate/    # Brique 2 — YAML mandate → typed Deviations (+ B9 structured rules)
src/alfred/report/     # Brique 3 — computed Digest, sources per line
src/alfred/narrate/    # Brique 4 — verified LLM rewrite (the anchoring test lives here)
src/alfred/deliver/    # Brique 5 — Slack / stdout
src/alfred/demo/       # Brique 6 — instrumented fake agent
src/alfred/instrument/ # Brique 8 — public instrumentation SDK (AgentTracer)
src/alfred/integrations/ # Brique 12 — native connectors (LangGraph callback handler)
examples/agents/       # B7 refund_bot (real LLM), B11 minimal (no LLM), B12 langgraph_bot
```

The [`CLAUDE.md`](CLAUDE.md) file encodes the workflow rules for anyone (human or
agent) working on this repo: tests first, plan mode for multi-file changes,
proof-of-run required at each commit.

## Roadmap

Each brick is a signed contract with falsifiable tests and a definition-of-done.
See [PLAN.md §5](PLAN.md) for the v0.1 core and [§12](PLAN.md) for the
"Bring Your Own Agent" sprint.

**v0.1 core — done:**

- **Brique 1** — trace store: OTLP ingest, `TraceEvent`, SQLite
- **Brique 2** — mandate engine v0
- **Brique 3** — report engine
- **Brique 4** — verified NLG (the test that *is* the product)
- **Brique 5** — Slack delivery + CLI
- **Brique 6** — `alfred demo` + launch polish → **public v0.1 on PyPI**

**Bring Your Own Agent sprint — done:** make Alfred work for a dev who
downloads it for *their* agents
([ADR 0013](docs/adr/0013-byoa-bring-your-own-agent-plan.md)).

- **Brique 7** — real refund-bot example: a framework-free Claude tool loop whose over-limit refund Alfred catches
- **Brique 8** — public `alfred.instrument` SDK: any loop → an ingestible OTLP trace in ~10 lines
- **Brique 9** — generic mandate (structured `tool:` / `when:` rules) + cost computed from tokens
- **Brique 10** — real-world ingestion: OTel Collector NDJSON + standard GenAI semconv adaptation
- **Brique 11** — onboarding + the 5-minute BYOA example (no LLM, no API key)

**Native connectors (v1.3, [ADR 0014](docs/adr/0014-langgraph-native-connector.md)):**

- **Brique 12** — LangGraph connector: attach one callback handler, get an anchored trace (`pip install alfred-ai[langgraph]`)

Post-v0.1: native connectors (v0.2), performance review — behavioral drift & cost-per-task (v0.3), evidence file export (v0.4 — the bridge to the closed-source engine).

## License

**Apache-2.0** for this package.

The advanced mandate engine (formal verdict semantics, verifiable policies,
multi-agent, retention, compliance features) is planned as **closed-source** —
open-core model announced up front. See [PLAN.md §1 D4](PLAN.md).
