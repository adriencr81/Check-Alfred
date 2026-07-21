"""Falsifiable specification for the minimal BYOA example (Brique 11).

The example lives in examples/agents/minimal/ — a ~30-line toy agent with no
LLM and no API key, instrumented with `alfred.instrument`. It is the "test 5
minutes BYOA" reference: a stranger clones, runs it, and sees an anchored
digest with a caught deviation, without any network or credentials.

This test runs the example exactly as shipped (into an in-memory tracer, so
zero disk and zero network) and proves the Brique 11 contract: the run's
trace is ingestible, every digest line is anchored to real trace event IDs,
and the over-cap approval surfaces as a single `forbidden_action` deviation
under the example's own mandate.

See PLAN.md §12 Brique 11.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "examples" / "agents"))

from minimal.agent import AGENT_NAME, approve_expenses  # noqa: E402

from alfred.instrument import AgentTracer  # noqa: E402
from alfred.mandate.model import DeviationType  # noqa: E402
from alfred.mandate.yaml_io import load_mandate  # noqa: E402
from alfred.report.build import build_digest  # noqa: E402
from alfred.trace.ingest import ingest_otlp_json  # noqa: E402
from alfred.trace.model import SpanKind, TraceEvent  # noqa: E402

MANDATE_PATH = REPO_ROOT / "examples" / "agents" / "minimal" / "mandate.yaml"


def _run() -> list[TraceEvent]:
    tracer = AgentTracer(agent=AGENT_NAME)
    approve_expenses(tracer)
    return ingest_otlp_json(tracer.payload())


def test_run_emits_ingestible_otlp() -> None:
    events = _run()
    kinds = [event.kind for event in events]
    assert kinds.count(SpanKind.AGENT_TASK) == 3
    assert kinds.count(SpanKind.TOOL_CALL) == 3
    assert kinds.count(SpanKind.LLM_CALL) == 0  # no LLM: no API key required
    assert len({event.event_id for event in events}) == len(events)


def test_digest_lines_are_all_anchored() -> None:
    events = _run()
    mandate = load_mandate(MANDATE_PATH)
    digest = build_digest(mandate, events, date.today())
    assert digest.lines  # a digest with no computed line would be vacuous
    known_ids = {event.event_id for event in events}
    for line in digest.lines:
        assert line.sources
        assert set(line.sources) <= known_ids


def test_over_cap_approval_yields_forbidden_action() -> None:
    events = _run()
    mandate = load_mandate(MANDATE_PATH)
    digest = build_digest(mandate, events, date.today())
    assert len(digest.deviations) == 1
    deviation = digest.deviations[0]
    assert deviation.type is DeviationType.FORBIDDEN_ACTION
    over_cap = next(
        event
        for event in events
        if event.attributes.get("tool.arguments.amount_eur") == 250.0
    )
    assert deviation.event_ids == (over_cap.event_id,)
