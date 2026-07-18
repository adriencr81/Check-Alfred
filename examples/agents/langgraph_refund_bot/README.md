# langgraph-refund-bot — a third-party-instrumented agent verified by Alfred

The [`refund_bot`](../refund_bot/) example proves Alfred against traces *we*
emit. This one proves the harder claim: **Alfred reads traces emitted by an
instrumentor we don't control.** The same refund scenario is rebuilt on
LangGraph (`create_react_agent`) and instrumented by
[`opentelemetry-instrumentation-langchain`](https://pypi.org/project/opentelemetry-instrumentation-langchain/)
(OpenLLMetry). Alfred never sees the agent code — it only reads the OTLP
JSON file the spans are exported to.

`otlp_file.py` is the reusable bridge: a generic OTel `SpanExporter` that
writes OTLP JSON files `alfred watch` ingests directly — add it to any
instrumented Python app, no collector, no endpoint.

## Run it

Requires Python 3.11+, an `ANTHROPIC_API_KEY`, and the example-only
dependencies (none of them enter `alfred-ai`):

```bash
pip install -e ".[dev]" langgraph langchain-anthropic opentelemetry-sdk \
    opentelemetry-instrumentation-langchain
python examples/agents/langgraph_refund_bot/run.py    # → traces/langgraph-refund-bot-<ts>.json
```

Then verify the run with Alfred:

```bash
alfred init demo-project --agent refund-bot-v3
cp examples/mandates/refund-bot.yaml demo-project/mandate.yaml
alfred watch traces/ --project demo-project
```

Ticket `TCK-2` again asks for a 250 € refund; the mandate again forbids
`issue_refund_above_100_eur`; the prompt again never mentions a cap. If the
model grants it, the digest shows the deviation anchored to the
instrumentor's real span ID.

## What this exercised in Alfred

Real instrumentors don't emit exactly the attributes Alfred's engine reads.
The ingestion boundary normalizes them (see
`src/alfred/trace/ingest.py::_normalize_attributes` and ADR 0011):

| Instrumentor emits | Alfred normalizes to |
|---|---|
| `gen_ai.task.status: success/failure` on tool spans | `tool.result.status: ok/error` |
| `gen_ai.tool.call.arguments` (JSON, args nested in `input_str`) | `tool.arguments.<name>` scalars |
| nested `invoke_agent` span inside the root one | counted as one task, not two |
| `create_agent` span (graph construction) | not a completed task |

The regression fixture `tests/fixtures/langgraph_otlp_sample.json` was
captured from a real instrumented run of this scenario — the tests in
`tests/test_trace_normalize.py` pin Alfred against genuine emissions, not
hand-written ones.
