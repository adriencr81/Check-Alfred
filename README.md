# Alfred

[![CI](https://github.com/adriencr81/Check-Alfred/actions/workflows/ci.yml/badge.svg)](https://github.com/adriencr81/Check-Alfred/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/alfred-ai.svg)](https://pypi.org/project/alfred-ai/)
[![Python versions](https://img.shields.io/pypi/pyversions/alfred-ai.svg)](https://pypi.org/project/alfred-ai/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> **Accountability layer for AI employees.** A Python package that turns raw
> agent traces into a daily stand-up your team can actually trust — every line
> anchored to a trace event ID.

**Status** — v0.1 core feature-complete, plus a "Bring Your Own Agent" sprint
landed: a public `alfred.instrument` SDK, native LangGraph and OpenAI Agents SDK
connectors, real-world OTel Collector ingestion, and a 5-minute example that
needs no API key. 393 tests green, mypy --strict on source *and* tests,
Python 3.11–3.14, CI + CodeQL. Public **v0.1 targeted for early August 2026**.
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

Tasks completed:          47   [evt:a1c, a1d, a1e, …]   (+7% vs 7-day avg)
Cost (tokens → €):     3.42 €   [evt:c0f, …]   (+185% vs 7-day avg ⚠️)
Escalations:               3   [evt:e01, e02, e03]   (+200% vs 7-day avg ⚠️)
Deviations (mandate):      1   [evt:d0a] — tool_not_allowed: `read_pii`
```

Each number reads against its own rolling 7-day average, so a manager sees not
just *what* happened but whether it's *normal* (⚠️ marks a doubling or more).
The comparison is itself computed from the prior days' trace events — never a
self-declared summary. See `docs/adr/0019-baseline-contextualized-digest.md`.

Delivered to Slack (v0.1), Teams (v0.2), or stdout / markdown (always) — or
exported as a self-contained, shareable HTML file (`alfred report --html`) whose
every line links to its source events.

## What counts as a deviation

Every deviation is a typed contradiction between the trace and the declared
mandate, anchored to the event(s) that prove it:

- **`tool_not_allowed`** — a tool call outside `allowed_tools`.
- **`forbidden_action`** — a call matching a `forbidden_actions` rule (an exact
  tool name, or a structured `tool:` / `when:` threshold on a call argument).
- **`budget_exceeded`** — the day's token → € cost passed `daily_budget_eur`.
- **`escalation_missed`** — an `escalate_when` threshold was breached over the
  day but the agent never raised a hand: no call to any tool listed in the
  mandate's `escalation_tools`. An escalation is proven by an action, never by
  a flag the agent sets on itself.
- **`required_action_missing`** — a triggered obligation left unmet: a
  `required_actions` rule's `when_tool` ran but its mandatory `require_tool`
  never did in the same trace (e.g. a refund issued without ever notifying the
  customer). Anchored to the `when_tool` event(s).
- **`loop_detected`** — the same tool called `loop_threshold` or more times in
  a row with identical arguments (default 3): an agent spinning without
  progress. Anchored to every event in the run.
- **`cost_mismatch`** — the cost the agent reported for the day contradicts the
  one priced from its own token counts. The digest always shows the priced
  figure; this says the trace tried to claim otherwise.
- **`tool_unidentified`** — a tool call that names no tool. It can't be checked
  against `allowed_tools`, so it is reported rather than skipped.

Stored evidence is append-only: an event whose `spanId` is already recorded
with different content is refused, the first version stands, and `alfred watch`
names the attempt on stderr and exits non-zero. Rewriting an anchor a past
digest already quoted is not something the audited agent gets to do.

The last two catch **silent failures** — the run completes with no error
status and looks successful, so nothing else flags them. Alfred only sees what
the trace records: a wrong-but-confident answer or a tool that returns garbage
with a 200 leaves no signal, and Alfred won't claim what it can't anchor.

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

See it work in one command, without installing anything — an instrumented fake
agent produces a real trace and a real digest, no virtualenv, no mandate file,
no Slack webhook, no network call:

```bash
uvx alfred-ai demo          # or: pipx run alfred-ai demo
```

Both run the package in a throwaway environment and leave nothing behind. To
keep it:

```bash
pip install alfred-ai
alfred demo
```

Then point it at your own agent:

```bash
alfred init --slack-webhook https://hooks.slack.com/…  # mandate.yaml + Slack config
alfred mandate init --from-traces traces/ > mandate.yaml  # seed a mandate from what the agent did
alfred mandate lint mandate.yaml                       # validate the mandate before you rely on it
alfred schedule traces/ --at 09:00 >> mycrontab        # one daily crontab line
alfred schedule traces/ --at 09:00 --github-actions \
  > .github/workflows/alfred.yml                       # …or a daily workflow, no host to keep up
alfred watch traces/                                   # one pass now (or --loop to keep running)
alfred report traces/ --html --out reports/            # shareable HTML report, one file per day
```

Install into a virtualenv — a distro-managed Python (e.g. Debian/Ubuntu system
`pip`) can fail with `Cannot uninstall … RECORD file not found`. On Windows the
activate step is `.venv\Scripts\activate`.

### Verify a real agent

`alfred demo` replays a scripted scenario. To watch Alfred catch a *real*
agent's deviation — a framework-free Claude tool loop that decides on its
own whether to grant an over-limit refund — see
[`examples/agents/refund_bot/`](examples/agents/refund_bot/). Nothing is
scripted there: the model decides, Alfred verifies.

Writing the first `mandate.yaml` is the onboarding cliff, so Alfred meets you
where the traces already are: `alfred mandate init --from-traces` proposes the
`allowed_tools` and `daily_budget_eur` it actually *observed* (policy fields stay
empty — those you declare, they aren't inferable from a trace), and
`alfred mandate lint` catches a typo'd `escalate_when` metric before it crashes a
`watch` run (exit 1 on error, so it drops into CI or pre-commit).

Handling customer data? A `redact:` list in the mandate masks named tool
arguments (`redact: [customer_email]`) **at ingestion, before they reach the
trace store** — the raw value never lands in SQLite, Slack, the HTML report, or
the narration LLM, replaced by a stable `redacted:sha256:…` token. Declarative
and deterministic: only the fields you list are touched. See
`docs/adr/0022-pii-redaction.md`.

`alfred watch` is a single pass by design (re-run via cron — `alfred schedule`
prints the line for you). For environments without cron, `alfred watch --loop`
re-scans on an interval until you stop it. Add `--alerts` (with a Slack webhook)
to also push a deviation the moment it's caught, instead of only in the daily
digest — pair it with `--loop` for near real-time.

A daily digest only becomes a habit if it keeps arriving, and both of those
paths assume a machine that stays up. If you don't have one,
`alfred schedule … --github-actions` prints a workflow you commit to
`.github/workflows/`: it runs the same single pass on GitHub's schedule, reads
the webhook from the `ALFRED_SLACK_WEBHOOK_URL` repository secret (never from
the committed file), and caches `.alfred/` between runs so a digest isn't
posted twice. The schedule is UTC, and a cache miss re-posts that day's digest
— both are stated in the generated file. See
`docs/adr/0027-unattended-daily-digest.md`.

By default the digest is the raw computed table. `--narrate` rewrites it as
verified LLM prose — the LLM only rephrases, and a sentence citing an event it
wasn't given fails the run instead of shipping. Declare the endpoint in config
(`alfred init --llm-base-url … --llm-model …`, any OpenAI-compatible endpoint)
and export `ALFRED_LLM_API_KEY`; without them `--narrate` exits 1 rather than
degrade silently. `alfred demo` stays LLM-free. See
[`docs/integrate.md`](docs/integrate.md#narrated-digest-verified-prose).

The Slack digest is ephemeral, so `alfred report traces/ --html` writes a
self-contained HTML file per day into `--out` (default the current directory) —
inline styles, zero JavaScript, no network — that a manager can forward. Each
report line and deviation links to an Evidence list of its source event IDs, so
the proof travels with the report. Unlike `watch`, it tracks no seen files and
re-renders on every run. It's a deliberately lighter cousin of the paid
evidence-dossier export (v0.4). See
`docs/adr/0020-shareable-html-report.md`.

## Plug in your own agent

Alfred verifies *your* agents. The floor is 5 minutes and no credentials:
[`examples/agents/minimal/`](examples/agents/minimal/) is a ~30-line agent
with no LLM and no API key — run it, `alfred watch` it, watch Alfred catch its
over-cap approval. Three honest paths get your real agent's runs to Alfred:

| Path | For agents that… | Status |
|---|---|---|
| **`alfred.instrument` SDK** | you can add ~10 lines to (wrap the loop, model call, tool call) | **works today** — [`docs/integrate.md`](docs/integrate.md) |
| **LangGraph connector** | run on LangGraph — attach one callback handler, no manual instrumentation | **works today** — `pip install alfred-ai[langgraph]` ([connector](docs/integrate.md#langgraph-connector)) |
| **OpenAI Agents SDK connector** | run on the OpenAI Agents SDK — register one tracing processor, no manual instrumentation | **works today** — `pip install alfred-ai[openai-agents]` ([connector](docs/integrate.md#openai-agents-sdk-connector)) |
| **OTel Collector bridge** | already emit OpenTelemetry GenAI spans | **works today** — point the Collector's file exporter at the watched folder ([bridge config](docs/integrate.md#otel-collector-bridge)) |
| **Other native connectors** | run on CrewAI or a managed platform | **v0.2** — not built yet |

Whatever the path, the guarantee is the same: every digest line is computed
from an identifiable trace event, never self-reported. What Alfred can't see in
the trace, it doesn't claim.

## Development

```bash
git clone https://github.com/adriencr81/Check-Alfred.git && cd Check-Alfred
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check . && mypy --strict src/ tests/
```

Layout:

```
src/alfred/trace/      # Brique 1 — OTLP ingest, TraceEvent, SQLite store
                       #   + B9 shared token→€ cost, B10 NDJSON / GenAI semconv adaptation
src/alfred/mandate/    # Brique 2 — YAML mandate → typed Deviations (+ B9 structured rules)
src/alfred/report/     # Brique 3 — computed Digest, sources per line (+ F4 shareable HTML render)
src/alfred/narrate/    # Brique 4 — verified LLM rewrite (the anchoring test lives here)
src/alfred/deliver/    # Brique 5 — Slack / stdout
src/alfred/demo/       # Brique 6 — instrumented fake agent
src/alfred/instrument/ # Brique 8 — public instrumentation SDK (AgentTracer)
src/alfred/integrations/ # Brique 12 — native connectors (LangGraph handler, OpenAI Agents processor)
examples/agents/       # B7 refund_bot (real LLM), B11 minimal (no LLM), B12 langgraph_bot, F5 openai_agents_bot
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

**Native connectors:**

- **Brique 12** ([ADR 0014](docs/adr/0014-langgraph-native-connector.md)) — LangGraph connector: attach one callback handler, get an anchored trace (`pip install alfred-ai[langgraph]`)
- **F5** ([ADR 0021](docs/adr/0021-openai-agents-native-connector.md)) — OpenAI Agents SDK connector: register one tracing processor, get an anchored trace (`pip install alfred-ai[openai-agents]`)

Post-v0.1: native connectors (v0.2 — CrewAI remaining), performance review — behavioral drift & cost-per-task (v0.3), evidence file export (v0.4 — the bridge to the closed-source engine).

## License

**Apache-2.0** for this package.

The advanced mandate engine (formal verdict semantics, verifiable policies,
multi-agent, retention, compliance features) is planned as **closed-source** —
open-core model announced up front. See [PLAN.md §1 D4](PLAN.md).
