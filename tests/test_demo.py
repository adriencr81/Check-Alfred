"""alfred.demo — fake agent trace + mandate (Brique 6).

See PLAN.md §5 Brique 6 and
docs/adr/0008-brique6-demo-launch-polish-design.md.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from alfred.demo.fake_agent import build_demo_payload, demo_mandate
from alfred.mandate.engine import evaluate
from alfred.mandate.model import DeviationType
from alfred.report.build import build_digest
from alfred.report.model import LineKind
from alfred.trace.ingest import ingest_otlp_json
from alfred.trace.model import SpanKind, TraceEvent


def test_build_demo_payload_ingests_to_real_events() -> None:
    events = ingest_otlp_json(build_demo_payload("demo-bot"))
    assert len(events) == 9  # 3 tasks x (agent_task + chat + tool_call)
    assert all(event.kind is not SpanKind.UNKNOWN for event in events)
    kinds = {event.kind for event in events}
    assert kinds == {SpanKind.AGENT_TASK, SpanKind.LLM_CALL, SpanKind.TOOL_CALL}


def test_build_demo_payload_events_land_on_the_same_day() -> None:
    events = ingest_otlp_json(build_demo_payload("demo-bot"))
    assert len({event.start_time.date() for event in events}) == 1


def test_demo_digest_is_credible() -> None:
    events = ingest_otlp_json(build_demo_payload("demo-bot"))
    mandate = demo_mandate("demo-bot")
    digest = build_digest(mandate, events, events[0].start_time.date())

    assert digest.agent == "demo-bot"
    tasks_line = next(line for line in digest.lines if line.kind is LineKind.TASKS_COMPLETED)
    assert tasks_line.value == 3
    escalations_line = next(line for line in digest.lines if line.kind is LineKind.ESCALATIONS)
    assert escalations_line.value == 1

    assert len(digest.deviations) == 1
    deviation = digest.deviations[0]
    assert deviation.type is DeviationType.TOOL_NOT_ALLOWED
    assert deviation.details["tool"] == "read_pii"


def test_demo_trace_deviation_matches_direct_mandate_evaluation() -> None:
    events = ingest_otlp_json(build_demo_payload("demo-bot"))
    mandate = demo_mandate("demo-bot")
    by_trace: dict[str, list[TraceEvent]] = defaultdict(list)
    for event in events:
        by_trace[event.trace_id].append(event)
    deviations = [d for trace_events in by_trace.values() for d in evaluate(mandate, trace_events)]
    assert len(deviations) == 1


def test_build_demo_payload_is_deterministic_given_same_anchor() -> None:
    anchor = datetime(2026, 7, 18, 9, 0, 0)
    first = build_demo_payload("demo-bot", now=anchor)
    second = build_demo_payload("demo-bot", now=anchor)
    assert first == second
