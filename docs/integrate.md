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
```

See [`examples/mandates/refund-bot.yaml`](../examples/mandates/refund-bot.yaml)
for the commented reference.

## 3. Watch the traces

```bash
alfred init my-project --agent support-bot \
  --slack-webhook https://hooks.slack.com/services/T0/B0/xyz   # webhook is optional
cp mandate.yaml my-project/mandate.yaml
alfred watch traces/ --project my-project
```

Pass `--slack-webhook` to have `init` write the webhook into
`.alfred/config.toml` for you (validated as an `https://` URL); omit it and
the digest goes to stdout only until you add the webhook yourself.

Every line of the resulting digest is computed from identifiable trace
events (the `[evt:…]` IDs) — never self-reported by the agent, never
invented by an LLM. See [verified_nlg.md](verified_nlg.md) for the
guarantee.

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

Beyond LangGraph (above), connectors for CrewAI, the OpenAI Agents SDK, and
managed platforms are on the roadmap for v0.2 — not built yet. Until then, one
of the paths above is required: for Alfred to verify a run, that run has to
leave a trace it can read.
