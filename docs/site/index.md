# Alfred

**Accountability layer for AI employees.** A Python package that turns raw agent
traces into a daily stand-up your team can actually trust — every line anchored
to a trace event ID.

*Status: v0.1 is feature-complete and targeted for public release in early
August 2026. Until it ships, the install commands below name a package that is
not on PyPI yet — build from the [repository](https://github.com/adriencr81/Check-Alfred)
in the meantime.*

---

## See it work

No virtualenv, no clone, no API key, no Slack webhook, no network call — an
instrumented fake agent produces a real trace and a real digest:

```bash
uvx alfred-ai demo          # or: pipx run alfred-ai demo
```

```
Alfred · demo-bot · 2026-07-26

Tasks completed:               3   [evt:demo-1-task, demo-2-task, demo-3-task]
Cost (tokens → €):        1.18 €   [evt:demo-1-llm, demo-2-llm, demo-3-llm]
Escalations:                   1   [evt:demo-3-tool]
Deviations (mandate):          1   [evt:demo-2-tool] — tool_not_allowed: tool 'read_pii' is not in allowed_tools
```

Then install it and point it at your own agent:

```bash
pip install alfred-ai
alfred init --slack-webhook https://hooks.slack.com/…
alfred watch traces/
```

## Why

You wouldn't hire a human employee without a mandate and a daily stand-up.
Alfred is that layer for your AI employees — a declarative mandate in YAML, an
evidence-anchored digest in Slack, deviations flagged the moment they happen.

**The rule that makes it different: every line of an Alfred report is anchored
to one or more trace event IDs.** The LLM only rephrases what was already
computed from the traces. No self-declared summaries, no hallucinated numbers.
A report line without a source event is a bug, not a feature — and there is a
test that says so.

That rule has teeth in both directions. It means a deviation always names the
events that prove it. It also means Alfred does not claim what the trace cannot
support: an agent that escapes its instrumentation, or a tool that returns
garbage with a success status, leaves no signal, and Alfred says nothing rather
than guessing.

## Why not X

| Neighbor | What it does | What Alfred does differently |
|---|---|---|
| Langfuse · AgentOps · LangSmith | Developer observability: traces, prompts, tokens, replay. | Manager reporting: mandate vs reality, typed deviations, daily digest legible without a dashboard. |
| Guardrails · NeMo Guardrails | Inline filters on LLM inputs / outputs. | Post-hoc control across the whole agent session, including tool calls and cost. |
| A homegrown Grafana / Datadog dashboard | Aggregated metrics, alerting. | Narrative, anchored, opinionated report — no dashboard design required. |

Alfred is **complementary, not a replacement**. It reads the same OpenTelemetry
GenAI traces your observability stack already emits, so pointing it at those
traces needs no reinstrumentation. The split is the question and the reader:
observability asks *is my agent working?* for the developer debugging it; Alfred
asks *did my agent stay within its mandate?* for the person accountable for it.

## Plug in your own agent

| Path | For agents that… |
|---|---|
| **`alfred.instrument` SDK** | you can add ~10 lines to (wrap the loop, model call, tool call) |
| **LangGraph connector** | run on LangGraph — attach one callback handler |
| **OpenAI Agents SDK connector** | run on the OpenAI Agents SDK — register one tracing processor |
| **OTel Collector bridge** | already emit OpenTelemetry GenAI spans |

The floor is five minutes and no credentials. Full walkthrough:
[**docs/integrate.md**](https://github.com/adriencr81/Check-Alfred/blob/main/docs/integrate.md).

## Stay in the loop

One email per release, plus the monthly finding — a real case where Alfred
caught a deviation an agent's own summary had smoothed over. No drip sequence,
no product announcements between releases, unsubscribe in one click.

<form action="https://buttondown.com/api/emails/embed-subscribe/alfred-ai"
      method="post" target="_blank" class="buttondown-subscribe">
  <input type="email" name="email" placeholder="you@example.com" required
         style="padding: 0.45em 0.6em; min-width: 16em; max-width: 100%;">
  <button type="submit" style="padding: 0.45em 1.1em;">Subscribe</button>
</form>

<p><small>Prefer a page? <a href="https://buttondown.com/alfred-ai">Subscribe on
Buttondown</a> directly.</small></p>

Nothing here is collected by Alfred itself: the package emits no telemetry, and
subscribing is a deliberate act on this page, outside the product. Your traces
stay on your machine either way.

## More

- [Repository, README and full deviation reference](https://github.com/adriencr81/Check-Alfred)
- [Integrate your own agent](https://github.com/adriencr81/Check-Alfred/blob/main/docs/integrate.md)
- [How the verified narration works](https://github.com/adriencr81/Check-Alfred/blob/main/docs/verified_nlg.md)
- [Security policy and threat model](https://github.com/adriencr81/Check-Alfred/blob/main/SECURITY.md)

**Apache-2.0.** The advanced mandate engine (formal verdict semantics,
verifiable policies, multi-agent, retention, compliance) is planned as
closed-source — open-core, announced up front. If that is the half your team
needs, [tell us what you're accountable for](teams.md).
