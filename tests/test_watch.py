"""alfred.watch — single-pass ingestion, no re-ingestion of seen files.

See PLAN.md §5 Brique 5 (`test_watch_ingests_new_files_only`) and
docs/adr/0007-brique5-delivery-cli-design.md.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from alfred.mandate.model import Mandate
from alfred.report.model import Digest, LineKind
from alfred.trace.ingest import ingest_otlp_file
from alfred.trace.model import TraceEvent
from alfred.trace.store import TraceStore
from alfred.watch import build_digests, watch_loop, watch_once


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

    digests = watch_once(project_dir, traces_dir, _mandate(), store)
    assert len(digests) == 1
    ingested_count = store.count()
    assert ingested_count == 3

    digests_second_pass = watch_once(project_dir, traces_dir, _mandate(), store)
    assert digests_second_pass == []
    assert store.count() == ingested_count
    store.close()


def test_watch_ingests_a_file_added_after_first_pass(
    project_dir: Path, traces_dir: Path, otlp_sample_path: Path
) -> None:
    store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), store)

    shutil.copy(otlp_sample_path, traces_dir / "day2.json")
    digests = watch_once(project_dir, traces_dir, _mandate(), store)
    assert len(digests) == 1
    store.close()


def test_watch_returns_empty_when_no_json_files(project_dir: Path, tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    store = TraceStore(project_dir / "trace.db")
    assert watch_once(project_dir, empty_dir, _mandate(), store) == []
    store.close()


def test_watch_loop_runs_max_passes_and_sleeps_between_them(
    project_dir: Path, traces_dir: Path
) -> None:
    store = TraceStore(project_dir / "trace.db")
    collected: list[list[Digest]] = []
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
    assert len(collected[0]) == 1
    assert collected[1] == [] and collected[2] == []
    # Sleeps happen between passes only — not after the last.
    assert sleeps == [42.0, 42.0]


def test_watch_loop_delivers_a_file_that_arrives_between_passes(
    project_dir: Path, traces_dir: Path, otlp_sample_path: Path
) -> None:
    store = TraceStore(project_dir / "trace.db")
    collected: list[list[Digest]] = []

    def on_digests(digests: list[Digest]) -> None:
        collected.append(digests)
        if len(collected) == 1:  # drop a new file in after the first pass
            shutil.copy(otlp_sample_path, traces_dir / "day2.json")

    watch_loop(
        project_dir,
        traces_dir,
        _mandate(),
        store,
        on_digests,
        interval_s=0.0,
        sleep=lambda _s: None,
        max_passes=2,
    )
    store.close()

    assert len(collected[0]) == 1  # day1
    assert len(collected[1]) == 1  # day2, picked up on the second pass


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
    digests = watch_once(project_dir, directory, _mandate(), store)
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
    assert watch_once(project_dir, traces_dir, _mandate(), second_store) == []
    second_store.close()
