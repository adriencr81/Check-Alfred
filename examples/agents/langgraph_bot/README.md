# `langgraph_bot` — a LangGraph agent Alfred supervises, no manual instrumentation

This example shows the **native LangGraph connector**: you attach one callback
handler to a graph invocation and Alfred records what the graph actually did —
no `AgentTracer.session()/llm_call()/tool_call()` calls in your code.

```python
from alfred.instrument import AgentTracer
from alfred.integrations.langgraph import AlfredCallbackHandler

tracer = AgentTracer(agent="expense-bot", traces_dir="traces")
graph.invoke(inputs, config={"callbacks": [AlfredCallbackHandler(tracer)]})
tracer.flush()
```

`agent.py` is a two-node graph — `think` (one model call) then `act` (one tool
call) — driven by a **deterministic fake chat model**, so it runs with no API
key and no network. Swap in `ChatAnthropic`/`ChatOpenAI` unchanged for a real
agent.

The `act` node approves a 250 € expense, over the mandate's 100 € cap.

## Run it

```bash
pip install alfred-ai[langgraph]
python examples/agents/langgraph_bot/agent.py     # → traces/expense-bot-<ts>.json
alfred init demo --agent expense-bot
cp examples/agents/langgraph_bot/mandate.yaml demo/mandate.yaml
alfred watch traces/ --project demo
```

Alfred catches the over-cap approval as a `forbidden_action` deviation, anchored
to the tool call's event ID — computed from the trace, never self-reported.

The falsifiable contract (real graph, fake model, zero network) lives in
`tests/test_integration_langgraph.py`. Design rationale:
`docs/adr/0014-langgraph-native-connector.md`.
