# minimal — the 5-minute "bring your own agent" test

The shortest path from *your* agent to an Alfred digest. `expense-bot` is a
~30-line toy agent with **no LLM and no API key**: it approves three expense
requests and records each step with the public `alfred.instrument` SDK. One
request is over the mandate's cap — so Alfred catches a real deviation, from a
real trace, with zero setup.

This is the honest floor of the product: no network, no credentials, no
framework. If you can run this, you can instrument your own loop the same way
(see [`docs/integrate.md`](../../../docs/integrate.md)).

## Run it

Requires only Python 3.11+ and this repo installed (`pip install -e ".[dev]"`):

```bash
python examples/agents/minimal/agent.py        # → traces/expense-bot-<ts>.json
alfred init demo --agent expense-bot
cp examples/agents/minimal/mandate.yaml demo/mandate.yaml
alfred watch traces/ --project demo
```

Expected digest (event IDs will be your run's real span IDs):

```
Alfred · expense-bot · <today>

Tasks completed:           3   [evt:…]
Deviations (mandate):      1   [evt:…] — forbidden_action: approve_expense called with amount_eur=250.0 > 100.0
```

## What's real, what's fake

| Real | Fake |
|---|---|
| The trace: span IDs, timestamps, task and tool spans | The expense requests (hard-coded in `agent.py`) |
| Every digest line, computed from those events | The "decision" (approve everything — deliberately naive) |
| The caught deviation, anchored to REQ-3's tool call | — |

There is no model call here, so no cost line and no self-reported anything —
the digest is nothing but what the trace proves. Swap the hard-coded loop for
your real agent, keep the `alfred.instrument` calls, and the guarantee holds.
For a version with a real LLM in the loop, see
[`../refund_bot/`](../refund_bot/).
