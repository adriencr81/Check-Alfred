# Changelog

All notable changes to this project are documented in this file. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Nothing has shipped to PyPI yet — the package version is `0.1.0.dev0`. The
entries below are the work done so far towards the v0.1 roadmap
(PLAN.md §5).

### Security

- Auditor availability — the same pentest found two ways to **stop** Alfred
  rather than fool it, both reproduced by a PoC. See
  `docs/adr/0024-auditor-availability.md`.
  - A single malformed span killed `alfred watch` for good: the `ValueError`
    from a bad timestamp escaped as a traceback, and since `seen.json` was only
    written after the whole pass, every re-run crashed on the same file — a
    200-byte trace file switched the auditor off and hid every other trace in
    the directory. Ingestion now raises one typed error per malformed span, an
    unreadable file is **quarantined** instead of aborting the pass, and the
    state is written after each file.
  - The quarantine is reported on **every** run, naming the file, and
    `alfred watch` exits non-zero while one remains — having delivered the
    healthy days. Fixing the file clears it on the next pass.
  - `seen.json` recorded filenames, so rewriting an already-ingested file with
    new activity got a "no new trace files" and was never audited. Files are now
    recognized by the SHA-256 of their content. An existing v1 `seen.json` (a
    list of names) is still read and adopts the current digests without
    re-ingesting, so upgrading emits no duplicate digests.
  - In `--loop`, a `DeliverError` from an unreachable Slack webhook (or a
    `NarrateError`) ended the supervision; it is now reported and the next pass
    runs. A single pass keeps failing loudly.
- Mandate control hardening — a white-box pentest found five ways the **audited
  agent** could defeat its own mandate, each reproduced by a PoC. All five are
  closed, and with them the product rule they broke (a claim in the report, or
  the absence of a deviation, must never rest on something the agent declared
  about itself). See `docs/adr/0023-mandate-control-hardening.md`.
  - `daily_budget_eur` was evaluated **per trace**, and `AgentTracer.session()`
    opens a fresh trace per task: ten tasks just under the cap spent ten times
    the cap with no deviation. Budget and the `escalate_when` rates are now
    computed over the whole day (`evaluate_trace` / `evaluate_day`).
  - The cost line and the budget check read the agent-written
    `gen_ai.usage.cost_eur` in preference to the pricing table, so declaring
    `0.0` erased the spend from both. **Breaking**: the price computed from the
    event's own tokens now wins, and the declared value is only the fallback
    for an unknown model or missing token counts. A declared cost that
    contradicts the computed one raises the new **`cost_mismatch`**.
  - An escalation was proven by `alfred.escalated`, an attribute the surveilled
    agent wrote itself. **Breaking**: the attribute has no effect; an escalation
    is proven by a call to a tool listed in the mandate's new
    `escalation_tools`. A mandate with `escalate_when` and no `escalation_tools`
    can prove no escalation, so every breach is reported — `alfred mandate lint`
    raises an error on that combination.
  - A span whose `gen_ai.operation.name` was unrecognized, or a tool call
    without `gen_ai.tool.name`, escaped every tool check. Spans carrying
    `gen_ai.tool.name` or `tool.arguments.*` are now classified as tool calls
    whatever their operation name, and a nameless tool call raises the new
    **`tool_unidentified`**.
  - A `forbidden_actions` threshold only compared `int`/`float`, so sending
    `amount_eur` as the string `"9999"` walked past a `> 1000` rule. Numeric
    strings are now compared, and a value that cannot be compared raises an
    explicit `forbidden_action` instead of being skipped.

### Added

- PII/secret redaction — a `redact:` list in the mandate masks named attribute
  values (a bare tool-argument name like `customer_email`, or a full attribute
  key like `gen_ai.prompt`) **at ingestion, before the event reaches the trace
  store**, so the raw value never lands in SQLite and never travels to Slack,
  the HTML report, or the narration LLM. Masked values become a stable
  `redacted:sha256:<hash>` token that preserves equality, so `loop_detected`
  still works on a masked field. Declarative and deterministic (only listed
  fields are touched — nothing is guessed); `alfred mandate lint` warns when a
  redacted field shadows a `forbidden_actions` rule's numeric argument (masking
  it would silently disable that check). Promotes PLAN.md §13's "honorable
  mention" to shipped for real-client use. Falsifiable spec (including a
  "never in the store" test) in `tests/test_trace_redact.py`. See
  `docs/adr/0022-pii-redaction.md`.
- F5 (first half) — native OpenAI Agents SDK connector
  (`alfred.integrations.openai_agents`): register `AlfredTracingProcessor` once
  (`set_trace_processors([...])`) and every `Runner.run(...)` becomes an
  Alfred-ingestible span, no manual instrumentation
  (`pip install alfred-ai[openai-agents]`). The processor drives the proven
  `AgentTracer` context managers from the SDK's tracing events (the root run
  trace → one `invoke_agent` session; each generation/response span → an
  `llm_call` with the response's real token usage; each function span → a
  `tool_call` whose JSON arguments are flattened to `tool.arguments.<key>`), so
  it re-emits no attribute keys and inherits the "computed from a real trace
  event, never self-reported" guarantee (D5). A failing tool is non-fatal in
  this SDK and is recorded as `tool.result.status: error`. Optional extra; the
  core keeps its single `pyyaml` dependency. Falsifiable e2e test (real run,
  fake OpenAI client over a mock transport, zero network) in
  `tests/test_integration_openai_agents.py`; runnable example in
  `examples/agents/openai_agents_bot/`. Applies the LangGraph recipe (Brique 12)
  to the second dominant framework of PLAN.md §13 F5; CrewAI remains. See
  `docs/adr/0021-openai-agents-native-connector.md`.
- Shareable HTML report — `alfred report traces/ --html` writes a self-contained
  HTML file per calendar day (inline CSS, zero JavaScript, no external resource)
  where each report line and deviation links to an Evidence list of its source
  event IDs, so a manager can forward a navigable proof. It reuses the digest's
  labels, values and baselines (identical across sinks) and the `watch`
  day-grouping + baseline pipeline (`build_digests`); unlike `watch` it tracks no
  seen files and re-renders on demand. Deliberately lighter than the paid
  evidence-dossier export (v0.4). Fourth of the five post-launch product features
  (PLAN.md §13 F4). See `docs/adr/0020-shareable-html-report.md`.
- Baseline-contextualized digest — every digest number now reads against its
  own rolling 7-day average (`Cost 3.42 € — +185% vs 7-day avg ⚠️`), turning a
  raw figure into a judgment ("is this normal?"). The mean is computed over the
  active days of the window and, like every report assertion, is anchored to the
  historical event IDs that produced it — no self-declared summary. A ⚠️ marks a
  doubling or more (±100%); comparisons appear only from three active days.
  `alfred watch` loads the window from the trace store; the plain digest is
  unchanged when there's no history. Third of the five post-launch product
  features (PLAN.md §13 F3). See
  `docs/adr/0019-baseline-contextualized-digest.md`.
- Real-time deviation alerts — opt-in `alfred watch --alerts` pushes a focused
  Slack alert the moment a pass catches a deviation, instead of waiting for the
  daily digest (pair with `--loop` for near real-time). The alert reuses the
  digest's deviation section and anchors every line on the offending event IDs
  (D5 inherited, not re-stated); it shares the proven Slack transport, adds no
  dependency, and warns loudly if `--alerts` is set without a webhook. First of
  the five post-launch product features (PLAN.md §13). See
  `docs/adr/0017-realtime-deviation-alerts.md`.
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
