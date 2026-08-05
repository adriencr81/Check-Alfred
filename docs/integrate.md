# Instrument your agent in 5 minutes

Alfred verifies what your agent *actually did* — not what it says it did.
For that it needs a trace: one OTLP JSON file per run, with a span for the
task, each model call, and each tool call. The `alfred.instrument` SDK
emits exactly that shape, with the exact attribute keys Alfred's mandate
engine and report builder read. Stdlib only, no OTel SDK required.

**Fastest start:** run [`examples/agents/minimal/`](../examples/agents/minimal/)
— a ~30-line agent with no LLM and no API key — to see the whole loop
(instrument → `alfred watch` → anchored digest) end to end before wiring in
your own code.

## 1. Wrap your loop

```python
from alfred.instrument import AgentTracer

tracer = AgentTracer(agent="support-bot", traces_dir="traces/")

with tracer.session(task_name="handle_ticket", task_id="TCK-42"):
    with tracer.llm_call(model="claude-opus-4-8") as llm:
        response = client.messages.create(...)   # your existing call
        llm.record_usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
    with tracer.tool_call("send_email", arguments={"to": "x@example.com"}) as tool:
        result = send_email(...)                 # your existing tool
        tool.record_result(status="ok")

tracer.flush()  # → traces/support-bot-<timestamp>.json
```

That's the whole integration:

- `session()` — one agent task. Opens a fresh trace; the span is emitted
  when the block exits, even on a crash.
- `llm_call()` — one model call. If you only know the model from the
  response, omit `model=` and pass
  `record_usage(..., response_model=response.model)` instead. Pass
  `cost_eur=` if you compute cost yourself — an explicit cost always wins;
  otherwise budget checks and the digest cost line price the call from its
  tokens when the model is in the pricing table
  (`alfred.trace.cost`).
- `tool_call(name, arguments={...})` — one tool execution. Scalar
  arguments are flattened to `tool.arguments.<key>` span attributes, which
  is what mandate rules like `issue_refund_above_100_eur` check. A clean
  exit without `record_result` records `status="ok"`; an exception records
  `"error"` and propagates.
- `flush()` — writes everything recorded so far (all sessions) to one
  file and returns its path.

For a complete, runnable integration see
[`examples/agents/refund_bot/`](../examples/agents/refund_bot/) — a real
Claude tool loop instrumented with this SDK.

## 2. Declare the mandate

```yaml
# mandate.yaml
agent: support-bot
allowed_tools: [send_email, read_ticket]
daily_budget_eur: 5.0
forbidden_actions:
  - send_marketing            # tool name
  - issue_refund_above_100_eur  # <tool>_above_<amount>_eur
escalate_when:
  - tool_error_rate > 0.10
  - budget_used > 0.80
escalation_tools: [escalate_to_human]
```

See [`examples/mandates/refund-bot.yaml`](../examples/mandates/refund-bot.yaml)
for the commented reference.

### Proving an escalation

`escalate_when` thresholds are excused only by a call to one of the tools in
`escalation_tools` — instrument your escalation path as a real tool call:

```python
with tracer.tool_call("escalate_to_human", arguments={"ticket": ticket_id}):
    page_the_on_call_human(ticket_id)
```

Alfred deliberately does **not** accept a self-declared `alfred.escalated`
attribute: an agent that can write its own escalation flag can switch off the
check watching it ([ADR 0023](adr/0023-mandate-control-hardening.md)). A mandate
that declares `escalate_when` without `escalation_tools` can never prove an
escalation, so every breach is reported — `alfred mandate lint` flags that
combination as an error.

### Redacting PII / secrets

Tool arguments often carry customer data — emails, names, order contents — or
secrets. By default they're stored as-is. Add a `redact:` list to the mandate to
mask named values **at ingestion, before they reach the trace store**, so the
raw value never lands in SQLite and never travels to Slack, the HTML report, or
the narration LLM ([ADR 0022](adr/0022-pii-redaction.md)):

```yaml
redact:
  - customer_email   # matches tool.arguments.customer_email
  - gen_ai.prompt    # or a full attribute key
```

Each masked value becomes a stable `redacted:hmac:<hash>` token — the content
is hidden, but identical values still compare equal, so `loop_detected` keeps
working on a masked field. The masking is deterministic and declarative: only
the fields you list are touched (nothing is guessed), and `alfred mandate lint`
warns if you redact a numeric field that a `forbidden_actions` rule checks (the
masked token can no longer be compared, so every call to that tool gets
reported as unverifiable). Fields packed into the standard
`gen_ai.tool.call.arguments` blob are masked inside it too, at any depth.

The token is an HMAC under a per-project key, generated on first use in
`.alfred/redaction-key` (mode 0600) — keep it with the project and out of
version control. Without a key the token was a plain digest, and an email
address or an order id was recoverable from it by dictionary
([ADR 0025](adr/0025-leak-containment.md)). Tokens are therefore comparable
within a project, not across projects.

## 3. Watch the traces

```bash
alfred init my-project --agent support-bot \
  --slack-webhook https://hooks.slack.com/services/T0/B0/xyz   # webhook is optional
cp mandate.yaml my-project/mandate.yaml
alfred watch traces/ --project my-project
```

The webhook URL is a credential — anyone holding it can post into your channel,
so `.alfred/config.toml` is written owner-only (as are `trace.db` and
`seen.json`, which carry tool arguments). To keep it off disk entirely, export
`ALFRED_SLACK_WEBHOOK_URL` instead; it wins over the config file. Both endpoint
URLs must be `https://` (cleartext is accepted only for `localhost`, so a
self-hosted model still works), and a webhook pointing somewhere other than
`hooks.slack.com` is reported as a warning.

Pass `--slack-webhook` to have `init` write the webhook into
`.alfred/config.toml` for you (validated as an `https://` URL); omit it and
the digest goes to stdout only until you add the webhook yourself.

Every line of the resulting digest is computed from identifiable trace
events (the `[evt:…]` IDs) — never self-reported by the agent, never
invented by an LLM. See [verified_nlg.md](verified_nlg.md) for the
guarantee.

### Several agents in one traces directory

`alfred watch` evaluates a trace against the project's mandate only when the
trace names that mandate's agent. The name is read from `gen_ai.agent.name` on
the `invoke_agent` span — the one `AgentTracer(agent=…)` and both native
connectors emit for you — so several agents can share a traces directory, each
with its own Alfred project and mandate, without polluting each other's digest.

A trace that names **no** agent is still evaluated: dropping it would empty the
digest of any pipeline that omits the attribute, an OTel Collector bridge
among them. Alfred cannot attest such events belong to your agent, so it says
so on stderr and carries on — the pass does not fail. If you see that notice
and you do run several agents into one directory, emit `gen_ai.agent.name` (or
instrument with `AgentTracer`) to make the scoping exact.

### When a trace file cannot be read

A file Alfred cannot parse is **quarantined**, not fatal: the pass still
ingests every other file and delivers their digests, the offending file is
named on stderr, and `alfred watch` exits `1` so a cron run surfaces the gap.
The warning repeats on every pass until you fix or remove the file — a
quarantined file is a hole in the audit, and it stays visible
([ADR 0024](adr/0024-auditor-availability.md)). Fixing the file is enough:
files are tracked by the SHA-256 of their content in `.alfred/seen.json`, so
the corrected version is picked up on the next pass. For the same reason, a
trace file rewritten after being ingested is audited again rather than
skipped by name.

## 4. Make it daily

`alfred watch` does one pass and exits — that's deliberate (no daemon, no
infra; [ADR 0007](adr/0007-brique5-delivery-cli-design.md)). To get a
*recurring* digest, pick one:

- **Cron (recommended).** `alfred schedule` prints a ready-to-use crontab
  line — no hand-rolled cron:

  ```bash
  alfred schedule traces/ --project my-project --at 09:00 >> mycrontab
  crontab mycrontab
  ```

- **Loop (containers / CI without cron).** `alfred watch --loop` keeps
  running, re-scanning every `--interval` seconds (default 60) until you stop
  it (Ctrl-C). Only newly-arrived trace files produce a digest, so nothing is
  re-delivered ([ADR 0015](adr/0015-watch-loop-opt-in.md)):

  ```bash
  alfred watch traces/ --project my-project --loop --interval 300
  ```

The digest is a daily review; a 250 € over-cap refund shouldn't wait until
tomorrow morning. Add `--alerts` (needs a Slack webhook) and every pass that
catches a deviation also pushes an immediate, focused Slack alert — anchored on
the offending event IDs, same as the digest ([ADR
0017](adr/0017-realtime-deviation-alerts.md)). Pair it with `--loop` for near
real-time:

```bash
alfred watch traces/ --project my-project --loop --interval 60 --alerts
```

Without a configured webhook `--alerts` warns and is a no-op (deviations still
appear in the digest); alerts are a Slack push channel, not a stdout one.

### Narrated digest (verified prose)

By default the digest is the raw computed table. Add `--narrate` and each
stdout digest is rewritten as short prose by an LLM — but the LLM only ever
rephrases what was computed: every sentence's `[evt:…]` citation is checked
against that line's source events, and a hallucinated citation fails the run
rather than shipping. `alfred report --html --narrate` prepends the same prose
above the HTML table.

Declare the endpoint once (the API key stays in the environment, never on
disk), then narrate:

```bash
alfred init my-project --agent my-agent \
  --llm-base-url https://api.openai.com/v1 --llm-model gpt-4o-mini
export ALFRED_LLM_API_KEY=sk-…
alfred watch traces/ --project my-project --narrate
```

Any OpenAI-compatible `/chat/completions` endpoint works. Without a resolvable
endpoint (missing config keys or `ALFRED_LLM_API_KEY`), `--narrate` fails loudly
with exit 1 — it never silently falls back to the raw digest. `alfred demo`
stays LLM-free.

## LangGraph connector

If your agent runs on **LangGraph**, you don't wrap anything by hand. Attach
`AlfredCallbackHandler` to the invocation and every model call and tool call in
the graph becomes a span — in the same OTLP shape as section 1, with the same
anchoring guarantee.

```bash
pip install alfred-ai[langgraph]
```

```python
from alfred.instrument import AgentTracer
from alfred.integrations.langgraph import AlfredCallbackHandler

tracer = AgentTracer(agent="support-bot", traces_dir="traces/")
graph.invoke(inputs, config={"callbacks": [AlfredCallbackHandler(tracer)]})
tracer.flush()  # → traces/support-bot-<timestamp>.json
```

- One **session** spans the root graph run (`invoke_agent`); each
  `on_chat_model_*` becomes an `llm_call` span with the response's real token
  usage, and each `on_tool_*` becomes a `tool_call` span whose `inputs` are
  flattened to `tool.arguments.<key>` — exactly what mandate rules read.
- The handler drives the same `AgentTracer` context managers the SDK uses, so
  it never re-emits attribute keys: the "computed from a real trace event, never
  self-reported" guarantee is inherited, not re-implemented.
- In production the handler never raises into your graph (LangChain swallows
  callback errors). Successive `graph.invoke(...)` calls with the same tracer
  accumulate; call `flush()` once when you're done.

Declare the mandate and watch the traces exactly as in sections 2–3. Runnable
example (real graph, fake model, no API key):
[`examples/agents/langgraph_bot/`](../examples/agents/langgraph_bot/). Design
rationale: [ADR 0014](adr/0014-langgraph-native-connector.md).

## OpenAI Agents SDK connector

If your agent runs on the **OpenAI Agents SDK** (`openai-agents`), you don't wrap
anything by hand either. Register `AlfredTracingProcessor` once and every
`Runner.run(...)` becomes a trace — same OTLP shape as section 1, same anchoring
guarantee.

```bash
pip install alfred-ai[openai-agents]
```

```python
from agents import Agent, Runner, set_trace_processors
from alfred.instrument import AgentTracer
from alfred.integrations.openai_agents import AlfredTracingProcessor

tracer = AgentTracer(agent="support-bot", traces_dir="traces/")
set_trace_processors([AlfredTracingProcessor(tracer)])   # Alfred only, fully offline
Runner.run_sync(agent, "handle the ticket")
tracer.flush()  # → traces/support-bot-<timestamp>.json
```

- One **session** spans the root run trace (`invoke_agent`); each model-call span
  (`GenerationSpanData`/`ResponseSpanData`, the Chat Completions and Responses API
  paths) becomes an `llm_call` with the response's real token usage, and each
  function span becomes a `tool_call` whose JSON arguments are flattened to
  `tool.arguments.<key>` — exactly what mandate rules read.
- The processor drives the same `AgentTracer` context managers the SDK uses, so
  it never re-emits attribute keys: the "computed from a real trace event, never
  self-reported" guarantee is inherited, not re-implemented.
- `set_trace_processors([...])` makes Alfred the only processor (nothing is sent
  to OpenAI's trace backend); use `add_trace_processor(...)` to keep the SDK's own
  export alongside Alfred's. In this SDK a failing tool is non-fatal — the run
  continues and the tool span carries the error, which Alfred records as
  `tool.result.status: error`.

Declare the mandate and watch the traces exactly as in sections 2–3. Runnable
example (real run, fake client, no API key):
[`examples/agents/openai_agents_bot/`](../examples/agents/openai_agents_bot/).
Design rationale: [ADR 0021](adr/0021-openai-agents-native-connector.md).

## OTel Collector bridge

If your agent is already instrumented with the OpenTelemetry SDK, you don't
need `alfred.instrument` — point your spans at an OTel Collector and let its
file exporter write the trace Alfred watches. Alfred reads what the file
exporter emits (one OTLP payload per line, NDJSON) as well as the
single-payload files `AgentTracer.flush()` writes; both land in the same
`alfred watch` folder.

Minimal Collector config (`otel-collector.yaml`):

```yaml
receivers:
  otlp:
    protocols:
      grpc:                       # your agent's OTLP exporter → localhost:4317
      http:                       # or localhost:4318

exporters:
  file:
    path: traces/agent-traces.json  # one JSON payload per line (NDJSON)

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [file]
```

```bash
otelcol --config otel-collector.yaml   # run the Collector
alfred watch traces/ --project my-project
```

For the bridge to yield anchored deviations, your tool spans need
`gen_ai.operation.name: execute_tool` and `gen_ai.tool.name`. Alfred adapts
the rest of the standard GenAI semconv on ingestion, so you don't have to
emit Alfred-specific keys:

- a span `status.code` of `STATUS_CODE_ERROR` becomes `tool.result.status:
  error` (used by `tool_error_rate`) unless the span already sets it;
- the `gen_ai.tool.call.arguments` JSON blob is flattened to
  `tool.arguments.<key>` scalars, which is what mandate rules like
  `issue_refund_above_100_eur` check.

## Other native connectors (v0.2)

Beyond LangGraph and the OpenAI Agents SDK (both above), a connector for CrewAI
and managed platforms is on the roadmap for v0.2 — not built yet. Until then, one
of the paths above is required: for Alfred to verify a run, that run has to
leave a trace it can read.
