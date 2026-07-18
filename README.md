# Alfred

[![CI](https://github.com/adriencr81/check-alfred/actions/workflows/ci.yml/badge.svg)](https://github.com/adriencr81/check-alfred/actions/workflows/ci.yml)

> **Accountability layer for AI employees.** A Python package that turns raw
> agent traces into a daily stand-up your team can actually trust — every line
> anchored to a trace event ID.

**Status** — pre-alpha, in active construction. Public **v0.1 targeted for ~30 August 2026**.
Full roadmap: [PLAN.md](PLAN.md).

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

## Quickstart

`alfred-ai` isn't on PyPI yet, but `alfred demo` already works today from
a clone — an instrumented fake agent produces a real trace and a real
digest, no mandate file, no Slack webhook, no network call:

```bash
git clone https://github.com/adriencr81/check-alfred.git && cd check-alfred
pip install -e ".[dev]"
alfred demo
```

Once v0.1 ships to PyPI:

```bash
pip install alfred-ai
alfred init          # generates mandate.yaml + Slack config
alfred watch         # ingests OTLP traces, posts the daily
alfred demo          # instrumented fake agent → real digest, no setup
```

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check . && mypy --strict src/
```

Layout:

```
src/alfred/trace/     # Brique 1 — OTLP ingest, TraceEvent, SQLite store
src/alfred/mandate/   # Brique 2 — YAML mandate → typed Deviations
src/alfred/report/    # Brique 3 — computed Digest, sources per line
src/alfred/narrate/   # Brique 4 — verified LLM rewrite (the anchoring test lives here)
src/alfred/deliver/   # Brique 5 — Slack / stdout
src/alfred/demo/      # Brique 6 — instrumented fake agent
```

The [`CLAUDE.md`](CLAUDE.md) file encodes the workflow rules for anyone (human or
agent) working on this repo: tests first, plan mode for multi-file changes,
proof-of-run required at each commit.

## Roadmap

Six bricks, one per week, launch at J+45. Each brick is a signed contract with
falsifiable tests and a definition-of-done. See [PLAN.md §5](PLAN.md).

- **Brique 1** — trace store (this repo currently)
- **Brique 2** — mandate engine v0
- **Brique 3** — report engine
- **Brique 4** — verified NLG (the test that *is* the product)
- **Brique 5** — Slack delivery + CLI
- **Brique 6** — `alfred demo` (done, see Quickstart above) + launch polish → **public v0.1 on PyPI**

Post-v0.1: native connectors (v0.2), performance review — behavioral drift & cost-per-task (v0.3), evidence file export (v0.4 — the bridge to the closed-source engine).

## License

**Apache-2.0** for this package.

The advanced mandate engine (formal verdict semantics, verifiable policies,
multi-agent, retention, compliance features) is planned as **closed-source** —
open-core model announced up front. See [PLAN.md §1 D4](PLAN.md).
