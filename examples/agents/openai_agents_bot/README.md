# `openai_agents_bot` — an OpenAI Agents SDK agent Alfred supervises, no manual instrumentation

This example shows the **native OpenAI Agents SDK connector**: you register one
tracing processor and Alfred records what the agent actually did — no
`AgentTracer.session()/llm_call()/tool_call()` calls in your code.

```python
from agents import Agent, Runner, set_trace_processors
from alfred.instrument import AgentTracer
from alfred.integrations.openai_agents import AlfredTracingProcessor

tracer = AgentTracer(agent="expense-bot", traces_dir="traces")
set_trace_processors([AlfredTracingProcessor(tracer)])
Runner.run_sync(agent, "Please approve REQ-3.")
tracer.flush()
```

`agent.py` runs one agent that makes a model call, approves an expense (one tool
call), then answers. It uses a real `OpenAIChatCompletionsModel` wired to a
**fake `AsyncOpenAI` client** (a mock HTTP transport returning canned
responses), so it runs with no API key and no network. Drop the fake client and
set `OPENAI_API_KEY` for a real agent — the connector is unchanged.

The agent approves a 250 € expense, over the mandate's 100 € cap.

## Run it

```bash
pip install alfred-ai[openai-agents]
python examples/agents/openai_agents_bot/agent.py   # → traces/expense-bot-<ts>.json
alfred init demo --agent expense-bot
cp examples/agents/openai_agents_bot/mandate.yaml demo/mandate.yaml
alfred watch traces/ --project demo
```

Alfred catches the over-cap approval as a `forbidden_action` deviation, anchored
to the tool call's event ID — computed from the trace, never self-reported.

`set_trace_processors([...])` registers Alfred as the only processor (fully
offline); use `add_trace_processor(...)` instead to keep the SDK's own OpenAI
trace export alongside Alfred's.

The falsifiable contract (real run, fake client, zero network) lives in
`tests/test_integration_openai_agents.py`. Design rationale:
`docs/adr/0021-openai-agents-native-connector.md`.
