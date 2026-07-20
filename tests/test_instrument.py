"""Falsifiable specification for the public instrumentation SDK (Brique 8).

`alfred.instrument.AgentTracer` promotes the proven emission shape of the
refund-bot example tracer into a public API: any agent loop instruments
itself in ~10 lines and produces an OTLP JSON trace that
`alfred.trace.ingest` reads, with exactly the attribute keys the mandate
engine and report builder consume. See PLAN.md §12 Brique 8 and
docs/adr/0013-byoa-bring-your-own-agent-plan.md.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from alfred.instrument import AgentTracer
from alfred.mandate.model import Mandate
from alfred.report.build import build_digest
from alfred.trace.ingest import ingest_otlp_file, ingest_otlp_json
from alfred.trace.model import SpanKind, TraceEvent

AGENT = "support-bot"
MODEL = "claude-opus-4-8"


def _toy_run(tracer: AgentTracer) -> None:
    """The ~10-line integration promised by the quickstart."""
    with tracer.session(task_name="triage", task_id="T-1"):
        with tracer.llm_call(model=MODEL) as llm:
            llm.record_usage(input_tokens=900, output_tokens=120, cost_eur=0.012)
        with tracer.tool_call("send_email", arguments={"to": "a@example.com"}) as tool:
            tool.record_result(status="ok")


def _events(tracer: AgentTracer) -> list[TraceEvent]:
    return ingest_otlp_json(tracer.payload())


def test_instrumented_loop_trace_ingests(tmp_path: Path) -> None:
    tracer = AgentTracer(agent=AGENT, traces_dir=tmp_path)
    _toy_run(tracer)
    trace_path = tracer.flush()
    assert trace_path.parent == tmp_path

    events = ingest_otlp_file(trace_path)
    kinds = [event.kind for event in events]
    assert kinds.count(SpanKind.AGENT_TASK) == 1
    assert kinds.count(SpanKind.LLM_CALL) == 1
    assert kinds.count(SpanKind.TOOL_CALL) == 1
    assert len({event.event_id for event in events}) == len(events)
    assert len({event.trace_id for event in events}) == 1

    task = next(event for event in events if event.kind is SpanKind.AGENT_TASK)
    assert task.attributes["gen_ai.agent.name"] == AGENT
    for event in events:
        assert event.start_time <= event.end_time
        assert task.start_time <= event.start_time
        assert event.end_time <= task.end_time
        if event is not task:
            assert event.parent_span_id == task.event_id


def test_tool_arguments_flattened() -> None:
    tracer = AgentTracer(agent=AGENT)
    with tracer.session(), tracer.tool_call(
        "issue_refund", arguments={"order_id": "ORD-1", "amount_eur": 250.0}
    ):
        pass  # no record_result: a clean exit defaults to status "ok"

    tool = next(event for event in _events(tracer) if event.kind is SpanKind.TOOL_CALL)
    assert tool.attributes["gen_ai.tool.name"] == "issue_refund"
    assert tool.attributes["tool.arguments.amount_eur"] == 250.0
    assert tool.attributes["tool.arguments.order_id"] == "ORD-1"
    assert tool.attributes["tool.result.status"] == "ok"


def test_tool_error_recorded() -> None:
    tracer = AgentTracer(agent=AGENT)
    with (
        pytest.raises(ValueError, match="smtp down"),
        tracer.session(),
        tracer.tool_call("send_email"),
    ):
        raise ValueError("smtp down")

    tool = next(event for event in _events(tracer) if event.kind is SpanKind.TOOL_CALL)
    assert tool.attributes["tool.result.status"] != "ok"


def test_usage_propagated() -> None:
    tracer = AgentTracer(agent=AGENT)
    with tracer.session(), tracer.llm_call(model=MODEL) as llm:
        llm.record_usage(input_tokens=900, output_tokens=120)

    llm_event = next(event for event in _events(tracer) if event.kind is SpanKind.LLM_CALL)
    assert llm_event.attributes["gen_ai.usage.input_tokens"] == 900
    assert llm_event.attributes["gen_ai.usage.output_tokens"] == 120
    assert llm_event.attributes["gen_ai.request.model"] == MODEL
    assert llm_event.attributes["gen_ai.response.model"] == MODEL


def test_call_outside_session_raises() -> None:
    tracer = AgentTracer(agent=AGENT)
    with pytest.raises(RuntimeError), tracer.llm_call(model=MODEL):
        pass
    with pytest.raises(RuntimeError), tracer.tool_call("send_email"):
        pass


def test_digest_from_instrumented_trace_anchored() -> None:
    tracer = AgentTracer(agent=AGENT)
    _toy_run(tracer)
    events = _events(tracer)
    mandate = Mandate(
        agent=AGENT,
        allowed_tools=frozenset({"send_email"}),
        daily_budget_eur=5.0,
        forbidden_actions=(),
        escalate_when=(),
    )
    digest = build_digest(mandate, events, date(2026, 7, 20))
    assert digest.lines
    event_ids = {event.event_id for event in events}
    for line in digest.lines:
        assert line.sources
        assert set(line.sources) <= event_ids
