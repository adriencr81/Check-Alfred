# Changelog

All notable changes to this project are documented in this file. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Nothing has shipped to PyPI yet — the package version is `0.1.0.dev0`. The
entries below are the work done so far towards the v0.1 roadmap
(PLAN.md §5).

### Added

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
- Brique 7 — real-agent example (`examples/agents/refund_bot/`): a
  framework-free Claude tool loop handles support tickets with real tool
  executions, emits genuine OTLP traces, and `alfred watch` catches its
  over-limit refund as a `forbidden_action` deviation under the stock
  `examples/mandates/refund-bot.yaml` mandate. Scripted-client tests keep
  CI network-free.
