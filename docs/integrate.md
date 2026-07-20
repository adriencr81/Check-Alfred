# Instrument your agent in 5 minutes

Alfred verifies what your agent *actually did* — not what it says it did.
For that it needs a trace: one OTLP JSON file per run, with a span for the
task, each model call, and each tool call. The `alfred.instrument` SDK
emits exactly that shape, with the exact attribute keys Alfred's mandate
engine and report builder read. Stdlib only, no OTel SDK required.

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

## Emitting from OTel directly

If your agent is already instrumented with the OpenTelemetry SDK, an
OTel Collector file-exporter bridge is planned (PLAN.md §12, Brique 10) —
today Alfred reads single-payload OTLP JSON files like the ones
`AgentTracer.flush()` writes.
