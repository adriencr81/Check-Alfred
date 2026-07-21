"""The smallest possible agent Alfred can supervise — no LLM, no API key.

`expense-bot` "handles" three expense requests by approving each one, and
records every step with the public `alfred.instrument` SDK. There is no model
call and no network: the policy is hard-coded (approve everything), which is
exactly the naive behaviour Alfred exists to catch — the third request is over
the mandate's 100 € cap.

Run it, then let Alfred verify what the agent actually did:

    python examples/agents/minimal/agent.py     # → traces/expense-bot-<ts>.json
    alfred init demo --agent expense-bot
    cp examples/agents/minimal/mandate.yaml demo/mandate.yaml
    alfred watch traces/ --project demo

Falsifiable contract in tests/test_example_minimal.py (PLAN.md §12 Brique 11).
"""

from __future__ import annotations

from pathlib import Path

from alfred.instrument import AgentTracer

AGENT_NAME = "expense-bot"

# (request id, amount in €) — the last one is over the mandate's 100 € cap.
REQUESTS = [("REQ-1", 42.0), ("REQ-2", 80.0), ("REQ-3", 250.0)]


def approve_expenses(tracer: AgentTracer) -> None:
    """Approve every request, recording each task and tool call. No LLM."""
    for request_id, amount_eur in REQUESTS:
        with (
            tracer.session(task_name=f"handle.{request_id}", task_id=request_id),
            tracer.tool_call(
                "approve_expense", {"request_id": request_id, "amount_eur": amount_eur}
            ) as tool,
        ):
            tool.record_result(status="ok")


def main(traces_dir: str = "traces") -> None:
    tracer = AgentTracer(agent=AGENT_NAME, traces_dir=traces_dir)
    approve_expenses(tracer)
    trace_path = tracer.flush()
    print(f"Trace written to {trace_path}")
    print("Now let Alfred verify what the agent actually did:")
    print(f"  alfred init demo --agent {AGENT_NAME}")
    print(f"  cp {Path(__file__).parent / 'mandate.yaml'} demo/mandate.yaml")
    print(f"  alfred watch {traces_dir}/ --project demo")


if __name__ == "__main__":
    main()
