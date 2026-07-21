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
alfred init my-project --agent support-bot
cp mandate.yaml my-project/mandate.yaml
alfred watch traces/ --project my-project
```

Every line of the resulting digest is computed from identifiable trace
events (the `[evt:…]` IDs) — never self-reported by the agent, never
invented by an LLM. See [verified_nlg.md](verified_nlg.md) for the
guarantee.

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

## Native connectors (v0.2)

If your agent runs on a managed platform and you can't add either the SDK or a
Collector, native connectors that pull traces for you are on the roadmap for
v0.2 — not built yet. Until then, one of the two paths above is required: for
Alfred to verify a run, that run has to leave a trace it can read.
