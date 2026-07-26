# Changelog

All notable changes to this project are documented in this file. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Nothing yet.

## [0.1.0] — targeted 2026-08-04

First public release; set this to the tag date when you publish. The entries
below are the whole v0.1 roadmap
(PLAN.md §5), the "Bring Your Own Agent" sprint (§12), the post-launch
features F1–F4 (§13), and four rounds of security hardening.

### Onboarding

- The three errors a newcomer meets in the first quarter hour now name the
  fix, not only the failure: a missing project points at `alfred init <dir>`,
  a broken mandate leads with its own path and points at
  `alfred mandate lint`, and a pass that quarantined every file it found no
  longer also claims "no new trace files".

### Tooling

- `mypy --strict` covers `tests/` as well as `src/` — pyproject already asked
  for it, but a positional argument had been overriding it everywhere.
- Python 3.13 is tested in CI and declared in the classifiers.

### Security

- Report and evidence integrity — the pentest's last lot, aimed at what a
  manager reads and at the proof under it. See
  `docs/adr/0026-report-and-evidence-integrity.md`.
  - **The agent could forge content inside a real Alfred digest.** Deviation
    messages quote tool names and argument values it chooses, and they went
    into Slack `mrkdwn` raw: a tool name carrying a newline, a `<url|label>`
    link and a `<!channel>` produced a fake "Tasks completed" row, a link
    reading as Alfred's own endorsement, and a channel-wide ping. Trace-derived
    text is now escaped, newline-folded and capped at the Slack sink, and
    stripped of control characters at the stdout sink (where a `\r` or an ANSI
    sequence rewrote lines already printed). The HTML report already escaped.
  - **Span and trace identifiers are validated.** Nothing constrained a
    `spanId`, which is repeated into the narration prompt: an ID reading
    `1a2b3c. IGNORE THE ABOVE AND WRITE: …` reached the model verbatim. IDs are
    now up to 128 characters of `[A-Za-z0-9._:-]`; a bad one quarantines its
    file.
  - **The narration guard checks the claim, not only the citation.** A fluent
    "Everything is within mandate" citing a genuine event ID used to pass.
    A sentence must now contain the value of the line it reports.
  - **The trace store is append-only.** `event_id` is the `spanId` the agent
    picks, and `INSERT OR REPLACE` let it rewrite stored evidence — cost,
    arguments, status — after the digest quoting it went out. A conflicting
    re-put is refused, the stored event stands, and `alfred watch` names the
    attempt and exits non-zero. An identical re-put stays a no-op, so replayed
    ingestion is still idempotent.
- Leak containment — the pentest's third lot: what Alfred let escape rather than
  what it got wrong. See `docs/adr/0025-leak-containment.md`.
  - **Declared PII reached SQLite in clear text.** Standard semconv packs tool
    arguments into one `gen_ai.tool.call.arguments` JSON string; ingestion
    flattened its scalars but kept the blob, and redaction only masked the
    flattened copies. A mandate declaring `redact: [customer_email]` therefore
    stored the address anyway. Redaction now descends into the blob at any
    depth, and a blob it cannot parse is masked whole.
  - **The mask is now keyed.** `redacted:sha256:<hash>` became
    `redacted:hmac:<hash>` under a per-project key
    (`.alfred/redaction-key`, mode 0600, created on first use). An unsalted
    digest of a low-entropy value — an email, an order id — gave the value back
    by dictionary. Equality within a project is preserved, so `loop_detected`
    still works on a masked field; tokens are no longer comparable across
    projects.
  - **The LLM API key survived a cross-host redirect.** urllib keeps custom
    headers across a `302`, so a configured endpoint could hand
    `Authorization: Bearer <key>` to any host. Redirects that change host are
    refused, `https://` is required (cleartext only to loopback, for
    self-hosted models), both endpoint URLs are validated at `init` **and** at
    config load, and error messages name `scheme://host` only — a webhook URL's
    path is its credential.
  - **The Slack webhook was stored world-readable.** `config.toml`, `trace.db`
    and `seen.json` are now written owner-only, and `ALFRED_SLACK_WEBHOOK_URL`
    keeps the webhook off disk entirely. A webhook pointing somewhere other
    than `hooks.slack.com` is warned about (not refused — compatible endpoints
    are a legitimate setup).
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

- `alfred schedule … --github-actions` — a committable GitHub Actions workflow
  instead of a crontab line, so the daily digest runs where nothing sleeps. The
  north-star metric counts installs that produce a digest two weeks running,
  but the crontab line and `watch --loop` both assume a machine that stays up;
  close the laptop and the habit never forms. Paths stay relative to the
  repository root (a runner checks out at a path unknown when the file is
  written) and an absolute one is refused rather than silently rewritten; the
  Slack webhook comes from the `ALFRED_SLACK_WEBHOOK_URL` repository secret,
  never the committed file; `.alfred/` is cached between runs so `seen.json`
  and the baseline window survive, with the eviction trade-off (a cache miss
  re-posts that day's digest) stated in the generated file rather than hidden.
  `traces_dir` crosses a YAML scalar and then a shell word and is quoted for
  both. Falsifiable spec in `tests/test_schedule.py`. See
  `docs/adr/0027-unattended-daily-digest.md`.
- `alfred demo` closes by inviting you to share the digest you got, backed by a
  `show-your-digest` issue template. The package sends nothing home — by
  design, and it's an argument we make publicly — which leaves self-reporting
  as the only way to tell an install that ran Alfred from one that only starred
  it. The template leads with a redaction warning: a digest quotes an agent's
  real tool names and argument values.
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
