"""alfred.watch — single-pass ingestion, no re-ingestion of seen files.

See PLAN.md §5 Brique 5 (`test_watch_ingests_new_files_only`) and
docs/adr/0007-brique5-delivery-cli-design.md.
"""

from __future__ import annotations

import json
import shutil
import stat
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from alfred.mandate.model import Mandate
from alfred.report.model import LineKind
from alfred.trace.ingest import ingest_otlp_file
from alfred.trace.model import EventId, TraceEvent
from alfred.trace.store import TraceStore
from alfred.watch import WatchPass, build_digests, watch_loop, watch_once


def _mandate() -> Mandate:
    return Mandate(
        agent="refund-bot-v3",
        allowed_tools=frozenset({"read_order", "issue_refund", "notify_customer"}),
        daily_budget_eur=5.0,
        forbidden_actions=(),
        escalate_when=(),
    )


@pytest.fixture
def traces_dir(tmp_path: Path, otlp_sample_path: Path) -> Path:
    directory = tmp_path / "traces"
    directory.mkdir()
    shutil.copy(otlp_sample_path, directory / "day1.json")
    return directory


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "project"
    directory.mkdir()
    return directory


def test_watch_ingests_new_files_only(project_dir: Path, traces_dir: Path) -> None:
    store = TraceStore(project_dir / "trace.db")

    digests = watch_once(project_dir, traces_dir, _mandate(), store).digests
    assert len(digests) == 1
    ingested_count = store.count()
    assert ingested_count == 3

    digests_second_pass = watch_once(project_dir, traces_dir, _mandate(), store).digests
    assert digests_second_pass == []
    assert store.count() == ingested_count
    store.close()


def test_watch_ingests_a_file_added_after_first_pass(
    project_dir: Path, traces_dir: Path, otlp_sample_path: Path
) -> None:
    store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), store)

    shutil.copy(otlp_sample_path, traces_dir / "day2.json")
    digests = watch_once(project_dir, traces_dir, _mandate(), store).digests
    assert len(digests) == 1
    store.close()


def test_watch_returns_empty_when_no_json_files(project_dir: Path, tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    store = TraceStore(project_dir / "trace.db")
    assert watch_once(project_dir, empty_dir, _mandate(), store).digests == []
    store.close()


def test_watch_loop_runs_max_passes_and_sleeps_between_them(
    project_dir: Path, traces_dir: Path
) -> None:
    store = TraceStore(project_dir / "trace.db")
    collected: list[WatchPass] = []
    sleeps: list[float] = []

    watch_loop(
        project_dir,
        traces_dir,
        _mandate(),
        store,
        collected.append,
        interval_s=42.0,
        sleep=sleeps.append,
        max_passes=3,
    )
    store.close()

    # Three passes: first delivers the one day's digest, the rest are empty
    # (seen.json dedups), so no digest is re-emitted.
    assert len(collected) == 3
    assert len(collected[0].digests) == 1
    assert collected[1].digests == [] and collected[2].digests == []
    # Sleeps happen between passes only — not after the last.
    assert sleeps == [42.0, 42.0]


def test_watch_loop_delivers_a_file_that_arrives_between_passes(
    project_dir: Path, traces_dir: Path, otlp_sample_path: Path
) -> None:
    store = TraceStore(project_dir / "trace.db")
    collected: list[WatchPass] = []

    def on_pass(result: WatchPass) -> None:
        collected.append(result)
        if len(collected) == 1:  # drop a new file in after the first pass
            shutil.copy(otlp_sample_path, traces_dir / "day2.json")

    watch_loop(
        project_dir,
        traces_dir,
        _mandate(),
        store,
        on_pass,
        interval_s=0.0,
        sleep=lambda _s: None,
        max_passes=2,
    )
    store.close()

    assert len(collected[0].digests) == 1  # day1
    assert len(collected[1].digests) == 1  # day2, picked up on the second pass


def _write_cost_trace(directory: Path, day: date, span_id: str, cost_eur: float) -> None:
    """Write a one-span OTLP file: an `chat` LLM call with a known cost on `day`."""
    nanos = str(int(datetime(day.year, day.month, day.day, 12, tzinfo=UTC).timestamp()) * 10**9)
    payload = {
        "resourceSpans": [{"scopeSpans": [{"spans": [{
            "spanId": span_id,
            "traceId": f"trace-{span_id}",
            "name": "chat",
            "startTimeUnixNano": nanos,
            "endTimeUnixNano": nanos,
            "attributes": [
                {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                {"key": "gen_ai.usage.cost_eur", "value": {"doubleValue": cost_eur}},
            ],
        }]}]}]
    }
    (directory / f"{day.isoformat()}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_watch_attaches_rolling_baseline_from_store_history(
    project_dir: Path, tmp_path: Path
) -> None:
    """E2E: four consecutive days ingested → the last digest's cost line reads
    against a baseline anchored to the three prior days' events (F3)."""
    directory = tmp_path / "traces"
    directory.mkdir()
    _write_cost_trace(directory, date(2026, 8, 26), "d26", 1.0)
    _write_cost_trace(directory, date(2026, 8, 27), "d27", 2.0)
    _write_cost_trace(directory, date(2026, 8, 28), "d28", 3.0)
    _write_cost_trace(directory, date(2026, 8, 29), "d29", 8.0)

    store = TraceStore(project_dir / "trace.db")
    digests = watch_once(project_dir, directory, _mandate(), store).digests
    store.close()

    assert [d.date for d in digests] == [
        date(2026, 8, 26),
        date(2026, 8, 27),
        date(2026, 8, 28),
        date(2026, 8, 29),
    ]
    first_cost = next(line for line in digests[0].lines if line.kind is LineKind.COST_EUR)
    assert first_cost.baseline is None  # no prior history for the first day

    last_cost = next(line for line in digests[-1].lines if line.kind is LineKind.COST_EUR)
    assert last_cost.baseline is not None
    assert last_cost.baseline.mean == pytest.approx(2.0)  # (1+2+3)/3
    assert last_cost.baseline.sample_days == 3
    assert set(last_cost.baseline.sources) == {"d26", "d27", "d28"}


def test_build_digests_reads_baseline_window_in_a_single_query(
    project_dir: Path, tmp_path: Path
) -> None:
    """Every digest day's baseline comes from one store query, not one per day."""
    directory = tmp_path / "traces"
    directory.mkdir()
    _write_cost_trace(directory, date(2026, 8, 26), "d26", 1.0)
    _write_cost_trace(directory, date(2026, 8, 27), "d27", 2.0)
    _write_cost_trace(directory, date(2026, 8, 28), "d28", 3.0)
    _write_cost_trace(directory, date(2026, 8, 29), "d29", 8.0)

    store = TraceStore(project_dir / "trace.db")
    events = [
        event for path in sorted(directory.glob("*.json")) for event in ingest_otlp_file(path)
    ]
    store.put_many(events)

    calls = 0
    real_find = store.find_by_date_range

    def counting_find(start: date, end: date) -> list[TraceEvent]:
        nonlocal calls
        calls += 1
        return real_find(start, end)

    store.find_by_date_range = counting_find  # type: ignore[method-assign]
    digests = build_digests(_mandate(), events, store)
    store.close()

    assert calls == 1  # four digest days, one baseline-window query
    last_cost = next(line for line in digests[-1].lines if line.kind is LineKind.COST_EUR)
    assert last_cost.baseline is not None
    assert last_cost.baseline.mean == pytest.approx(2.0)  # (1+2+3)/3, unchanged
    assert set(last_cost.baseline.sources) == {"d26", "d27", "d28"}


def test_watch_persists_seen_state_across_processes(project_dir: Path, traces_dir: Path) -> None:
    """A fresh `TraceStore`/call (simulating a new CLI invocation) still
    skips files ingested by a prior call, since seen-state lives on disk."""
    first_store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), first_store)
    first_store.close()

    second_store = TraceStore(project_dir / "trace.db")
    assert watch_once(project_dir, traces_dir, _mandate(), second_store).digests == []
    second_store.close()


def _write_broken(directory: Path, name: str = "broken.json") -> Path:
    """A file whose JSON parses but whose span cannot be normalized."""
    payload = {
        "resourceSpans": [{"scopeSpans": [{"spans": [{
            "spanId": "badspan",
            "traceId": "trace-bad",
            "name": "chat",
            "startTimeUnixNano": "boom",
            "endTimeUnixNano": "boom",
            "attributes": [],
        }]}]}]
    }
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_watch_quarantines_an_unparsable_file_and_still_delivers_the_rest(
    project_dir: Path, traces_dir: Path
) -> None:
    """ADR 0024 decision 2: one bad span used to abort the whole pass — and
    since seen-state was written only at the end, every re-run aborted again."""
    _write_broken(traces_dir, "00-broken.json")  # sorts before the good file
    store = TraceStore(project_dir / "trace.db")

    result = watch_once(project_dir, traces_dir, _mandate(), store)

    assert len(result.digests) == 1  # the healthy file was still ingested
    assert [q.name for q in result.quarantined] == ["00-broken.json"]
    assert "badspan" in result.quarantined[0].reason
    store.close()


def test_watch_keeps_reporting_a_quarantined_file_on_later_passes(
    project_dir: Path, traces_dir: Path
) -> None:
    """Decision 3: a hole in the audit stays visible until a human fixes it."""
    _write_broken(traces_dir)
    store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), store)

    second = watch_once(project_dir, traces_dir, _mandate(), store)
    assert [q.name for q in second.quarantined] == ["broken.json"]
    assert second.digests == []  # but it is not re-ingested
    store.close()


def test_watch_state_survives_a_failure_on_a_later_file(
    project_dir: Path, traces_dir: Path
) -> None:
    """Decision 6: state is written per file, so a pass interrupted after the
    first file does not replay it."""
    _write_broken(traces_dir, "zz-broken.json")  # sorts after day1.json
    store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), store)
    store.close()

    second_store = TraceStore(project_dir / "trace.db")
    assert watch_once(project_dir, traces_dir, _mandate(), second_store).digests == []
    second_store.close()


def test_watch_reingests_a_file_whose_content_changed(
    project_dir: Path, traces_dir: Path, otlp_sample_path: Path
) -> None:
    """ADR 0024 decision 4: seen-state keyed on filenames let an agent rewrite
    an already-ingested file and never be audited again."""
    store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), store)

    payload = json.loads((traces_dir / "day1.json").read_text(encoding="utf-8"))
    span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    span["spanId"] = "rewritten"
    span["attributes"] = [
        {"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}},
        {"key": "gen_ai.tool.name", "value": {"stringValue": "exfiltrate_database"}},
    ]
    (traces_dir / "day1.json").write_text(json.dumps(payload), encoding="utf-8")

    result = watch_once(project_dir, traces_dir, _mandate(), store)
    assert len(result.digests) == 1
    assert any(
        d.details.get("tool") == "exfiltrate_database"
        for digest in result.digests
        for d in digest.deviations
    )
    store.close()


def test_watch_adopts_a_v1_seen_file_without_reingesting(
    project_dir: Path, traces_dir: Path
) -> None:
    """Decision 5: upgrading must not replay a day's digests."""
    seen = project_dir / ".alfred" / "seen.json"
    seen.parent.mkdir(parents=True, exist_ok=True)
    seen.write_text(json.dumps(["day1.json"]), encoding="utf-8")

    store = TraceStore(project_dir / "trace.db")
    assert watch_once(project_dir, traces_dir, _mandate(), store).digests == []
    assert store.count() == 0
    # ...and the adopted digest is recorded, so a later rewrite is still caught.
    state = json.loads(seen.read_text(encoding="utf-8"))
    assert state["files"]["day1.json"]["sha256"]
    store.close()


def test_watch_ingests_a_quarantined_file_once_it_is_fixed(
    project_dir: Path, traces_dir: Path, otlp_sample_path: Path
) -> None:
    """Fixing the file is how a human clears the quarantine."""
    broken = _write_broken(traces_dir)
    store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), store)

    shutil.copy(otlp_sample_path, broken)  # same name, valid content now
    result = watch_once(project_dir, traces_dir, _mandate(), store)
    assert result.quarantined == ()
    assert len(result.digests) == 1
    store.close()


def _write_agent_trace(
    directory: Path,
    *,
    agent: str | None,
    tool: str,
    day: date,
    trace_id: str,
    cost_eur: float = 0.0,
) -> None:
    """One trace: an `invoke_agent` span — naming its agent unless `agent` is
    None — plus the tool call it made, and an LLM call when a cost is wanted."""
    nanos = str(int(datetime(day.year, day.month, day.day, 12, tzinfo=UTC).timestamp()) * 10**9)
    task_attributes: list[dict[str, object]] = [
        {"key": "gen_ai.operation.name", "value": {"stringValue": "invoke_agent"}}
    ]
    if agent is not None:
        task_attributes.append({"key": "gen_ai.agent.name", "value": {"stringValue": agent}})

    def _span(suffix: str, name: str, attributes: list[dict[str, object]]) -> dict[str, object]:
        return {
            "spanId": f"{trace_id}-{suffix}",
            "traceId": trace_id,
            "name": name,
            "startTimeUnixNano": nanos,
            "endTimeUnixNano": nanos,
            "attributes": attributes,
        }

    spans: list[dict[str, object]] = [
        _span("task", "invoke_agent", task_attributes),
        _span(
            "tool",
            tool,
            [
                {"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}},
                {"key": "gen_ai.tool.name", "value": {"stringValue": tool}},
            ],
        ),
    ]
    if cost_eur:
        spans.append(
            _span(
                "llm",
                "chat",
                [
                    {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                    {"key": "gen_ai.usage.cost_eur", "value": {"doubleValue": cost_eur}},
                ],
            )
        )
    payload = {"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}
    (directory / f"{day.isoformat()}-{trace_id}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


@pytest.fixture
def shared_traces_dir(tmp_path: Path) -> Path:
    """A traces directory two agents write into — the case of issue #60."""
    directory = tmp_path / "shared"
    directory.mkdir()
    return directory


def test_digest_ignores_another_agents_events(project_dir: Path, shared_traces_dir: Path) -> None:
    """Issue #60: two agents sharing a traces directory. `charge_card` is not in
    the refund-bot's mandate, but the refund-bot never called it — the expense-bot
    did, and its events must not be evaluated against someone else's mandate."""
    day = date(2026, 8, 26)
    _write_agent_trace(
        shared_traces_dir, agent="refund-bot-v3", tool="issue_refund", day=day, trace_id="mine"
    )
    _write_agent_trace(
        shared_traces_dir, agent="expense-bot", tool="charge_card", day=day, trace_id="theirs"
    )
    store = TraceStore(project_dir / "trace.db")

    result = watch_once(project_dir, shared_traces_dir, _mandate(), store)
    store.close()

    assert len(result.digests) == 1
    assert result.digests[0].deviations == ()
    tasks = next(
        line for line in result.digests[0].lines if line.kind is LineKind.TASKS_COMPLETED
    )
    assert tasks.value == 1  # the refund-bot's one task, not both agents'
    cited = {source for line in result.digests[0].lines for source in line.sources}
    assert not any(source.startswith("theirs") for source in cited)
    assert result.unattributed == ()  # both traces name their agent


def test_digest_still_reports_the_mandate_agents_own_deviation(
    project_dir: Path, shared_traces_dir: Path
) -> None:
    """Mirror of the test above: the filter must not swallow real deviations.
    The same forbidden tool, called by the agent the mandate governs, is caught."""
    day = date(2026, 8, 26)
    _write_agent_trace(
        shared_traces_dir, agent="refund-bot-v3", tool="charge_card", day=day, trace_id="mine"
    )
    store = TraceStore(project_dir / "trace.db")

    result = watch_once(project_dir, shared_traces_dir, _mandate(), store)
    store.close()

    deviations = result.digests[0].deviations
    assert len(deviations) == 1
    assert deviations[0].details.get("tool") == "charge_card"


def test_baseline_ignores_another_agents_history(
    project_dir: Path, shared_traces_dir: Path
) -> None:
    """The rolling baseline (F3) reads prior days straight from the store, so it
    mixed agents too — a second, unfiltered site of the same bug.

    Same three prior days and same expected mean as
    `test_watch_attaches_rolling_baseline_from_store_history`; the only
    difference is the expense-bot spending 90 € in the middle of the window.
    """
    for day, cost in ((26, 1.0), (27, 2.0), (28, 3.0), (29, 8.0)):
        _write_agent_trace(
            shared_traces_dir,
            agent="refund-bot-v3",
            tool="issue_refund",
            day=date(2026, 8, day),
            trace_id=f"mine-{day}",
            cost_eur=cost,
        )
    _write_agent_trace(
        shared_traces_dir,
        agent="expense-bot",
        tool="charge_card",
        day=date(2026, 8, 27),
        trace_id="theirs-27",
        cost_eur=90.0,
    )
    store = TraceStore(project_dir / "trace.db")

    digests = watch_once(project_dir, shared_traces_dir, _mandate(), store).digests
    store.close()

    last_cost = next(line for line in digests[-1].lines if line.kind is LineKind.COST_EUR)
    assert last_cost.baseline is not None
    assert last_cost.baseline.mean == pytest.approx(2.0)  # (1+2+3)/3, not (1+92+3)/3
    assert set(last_cost.baseline.sources) == {"mine-26-llm", "mine-27-llm", "mine-28-llm"}


def test_unattributed_trace_is_evaluated_and_reported(
    project_dir: Path, shared_traces_dir: Path
) -> None:
    """A trace with no `gen_ai.agent.name` — the shape an OTel Collector bridge
    produces — is still evaluated, since excluding it would silently empty the
    digest of everyone who does not emit the attribute. But it cannot be proven
    to belong to this mandate, and that gap is reported (ADR 0024)."""
    day = date(2026, 8, 26)
    _write_agent_trace(
        shared_traces_dir, agent=None, tool="issue_refund", day=day, trace_id="nameless"
    )
    store = TraceStore(project_dir / "trace.db")

    result = watch_once(project_dir, shared_traces_dir, _mandate(), store)
    store.close()

    assert len(result.digests) == 1  # evaluated, not dropped
    assert {event.event_id for event in result.unattributed} == {
        "nameless-task",
        "nameless-tool",
    }


def test_another_agents_events_are_not_reported_as_unattributed(
    project_dir: Path, shared_traces_dir: Path
) -> None:
    """An excluded trace is not a gap: it belongs to a mandate of its own."""
    _write_agent_trace(
        shared_traces_dir,
        agent="expense-bot",
        tool="charge_card",
        day=date(2026, 8, 26),
        trace_id="theirs",
    )
    store = TraceStore(project_dir / "trace.db")

    result = watch_once(project_dir, shared_traces_dir, _mandate(), store)
    store.close()

    assert result.unattributed == ()
    assert result.digests == []  # nothing of this agent's happened that day


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes don't exist on Windows")
def test_seen_state_and_store_are_owner_only(project_dir: Path, traces_dir: Path) -> None:
    """ADR 0025 decision 7: both files carry what the agent handled."""
    db_path = project_dir / "trace.db"
    store = TraceStore(db_path)
    watch_once(project_dir, traces_dir, _mandate(), store)
    store.close()

    assert stat.S_IMODE(db_path.stat().st_mode) == 0o600
    seen = project_dir / ".alfred" / "seen.json"
    assert stat.S_IMODE(seen.stat().st_mode) == 0o600


def test_watch_reports_an_event_that_tries_to_overwrite_stored_evidence(
    project_dir: Path, traces_dir: Path
) -> None:
    """ADR 0026 decisions 4 and 5: re-emitting a spanId with different content
    used to rewrite the stored anchor. The first version wins, and the attempt
    is reported like a quarantine — every pass, exit non-zero."""
    store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), store)

    payload = json.loads((traces_dir / "day1.json").read_text(encoding="utf-8"))
    span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][2]
    span["attributes"] = []  # same spanId, evidence removed
    (traces_dir / "day2.json").write_text(json.dumps(payload), encoding="utf-8")

    result = watch_once(project_dir, traces_dir, _mandate(), store)
    assert [event.event_id for event in result.conflicts] == ["b2c3d4e5f6071829"]
    stored = store.get(EventId("b2c3d4e5f6071829"))
    assert stored is not None
    assert stored.attributes  # the original evidence is intact
    store.close()
