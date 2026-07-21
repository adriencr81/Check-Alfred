# Changelog

All notable changes to this project are documented in this file. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Nothing has shipped to PyPI yet — the package version is `0.1.0.dev0`. The
entries below are the work done so far towards the v0.1 roadmap
(PLAN.md §5).

### Added

- Brique 12 — native LangGraph connector (`alfred.integrations.langgraph`):
  attach `AlfredCallbackHandler` to a graph invocation and every model and
  tool call becomes an Alfred-ingestible span, no manual instrumentation
  (`pip install alfred-ai[langgraph]`). The handler drives the proven
  `AgentTracer` context managers from LangChain callbacks (keyed by
  `run_id`), so attribute keys and the event-ID anchoring guarantee are
  inherited, not re-implemented; `tracer.py` is unchanged and the core keeps
  its single `pyyaml` dependency. Runnable `examples/agents/langgraph_bot/`
  (real graph, fake model, no API key), "LangGraph connector" section in
  `docs/integrate.md`, falsifiable end-to-end test (zero network). See
  `docs/adr/0014-langgraph-native-connector.md`.
- Brique 1 — trace store: OTLP JSON ingest, `TraceEvent` model, SQLite
  persistence.
- Brique 2 — mandate engine: YAML mandate parsing, typed `Deviation`
  detection (`tool_not_allowed`, `budget_exceeded`, `forbidden_action`,
  `escalation_missed`).
- Brique 3 — report engine: `Digest` builder with per-line source event
  IDs, fixed-format text renderer.
- Brique 4 — verified NLG: optional LLM rewrite of a `Digest` into prose,
  with a hard guarantee (enforced by test) that no sentence cites an
  event ID outside its line's sources.
- Brique 5 — delivery: Slack Block Kit payloads, `alfred init` and
  `alfred watch` CLI commands.
- Brique 6 — `alfred demo`: instrumented fake agent that produces a real
  trace and a real digest with zero setup; CI (pytest/ruff/mypy matrix +
  CodeQL); CONTRIBUTING.md, issue templates,
  `docs/vcd/alfred-v0.1.md`.
- Brique 8 — public instrumentation SDK (`alfred.instrument`): any agent
  loop emits an Alfred-ingestible OTLP JSON trace in ~10 lines
  (`AgentTracer` with `session`/`llm_call`/`tool_call` context managers,
  `flush()` to a watchable file). The refund-bot example now consumes it
  and its example-only tracer is removed; quickstart in
  `docs/integrate.md`.
- Brique 9 — generic mandate + cost from tokens: `forbidden_actions`
  accepts structured rules (`tool:` + `when: args.<arg> <op> <number>`)
  on any tool argument, alongside the unchanged legacy string DSL
  (commented example in `examples/mandates/sql-analyst.yaml`); token
  pricing moves to a shared `alfred.trace.cost` module so budget checks
  (`budget_exceeded`, `budget_used`) and the digest cost line agree to
  the cent on traces without `gen_ai.usage.cost_eur`.
- Brique 11 — onboarding / "5-minute BYOA test": `examples/agents/minimal/`,
  a ~30-line agent with no LLM and no API key, instrumented with
  `alfred.instrument` and shipped with its own mandate — run it and
  `alfred watch` catches its over-cap approval as a `forbidden_action`
  deviation, entirely offline. A "Plug in your own agent" section in the
  README lays out the three honest paths (SDK today, OTel Collector bridge
  today, native connectors in v0.2), and `docs/integrate.md` now points at
  the minimal example as the fastest start. Network-free end-to-end test.
- Brique 10 — real-world ingestion: `ingest_otlp_file` reads the
  newline-delimited OTLP payloads the OTel Collector file exporter writes
  (as well as single-payload files), so the `agent → Collector →
  alfred watch` bridge works; the ingestion adaptation layer maps standard
  GenAI semconv onto the engine's home keys (`status.code` error →
  `tool.result.status`, `gen_ai.tool.call.arguments` JSON blob →
  `tool.arguments.<key>` scalars) without native keys ever being
  overwritten. Collector config in `docs/integrate.md`.
- Brique 7 — real-agent example (`examples/agents/refund_bot/`): a
  framework-free Claude tool loop handles support tickets with real tool
  executions, emits genuine OTLP traces, and `alfred watch` catches its
  over-limit refund as a `forbidden_action` deviation under the stock
  `examples/mandates/refund-bot.yaml` mandate. Scripted-client tests keep
  CI network-free.
