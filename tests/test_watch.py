"""alfred.watch — single-pass ingestion, no re-ingestion of seen files.

See PLAN.md §5 Brique 5 (`test_watch_ingests_new_files_only`),
docs/adr/0007-brique5-delivery-cli-design.md, and ADR 0011 (quarantine of
files that cannot be ingested).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from alfred.mandate.model import Mandate
from alfred.trace.store import TraceStore
from alfred.watch import watch_once


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

    result = watch_once(project_dir, traces_dir, _mandate(), store)
    assert len(result.digests) == 1
    assert result.failures == ()
    ingested_count = store.count()
    assert ingested_count == 3

    second_pass = watch_once(project_dir, traces_dir, _mandate(), store)
    assert second_pass.digests == ()
    assert store.count() == ingested_count
    store.close()


def test_watch_ingests_a_file_added_after_first_pass(
    project_dir: Path, traces_dir: Path, otlp_sample_path: Path
) -> None:
    store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), store)

    shutil.copy(otlp_sample_path, traces_dir / "day2.json")
    result = watch_once(project_dir, traces_dir, _mandate(), store)
    assert len(result.digests) == 1
    store.close()


def test_watch_returns_empty_when_no_json_files(project_dir: Path, tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    store = TraceStore(project_dir / "trace.db")
    result = watch_once(project_dir, empty_dir, _mandate(), store)
    assert result.digests == ()
    assert result.failures == ()
    store.close()


def test_watch_persists_seen_state_across_processes(project_dir: Path, traces_dir: Path) -> None:
    """A fresh `TraceStore`/call (simulating a new CLI invocation) still
    skips files ingested by a prior call, since seen-state lives on disk."""
    first_store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), first_store)
    first_store.close()

    second_store = TraceStore(project_dir / "trace.db")
    assert watch_once(project_dir, traces_dir, _mandate(), second_store).digests == ()
    second_store.close()


def test_watch_reingests_a_rewritten_file(project_dir: Path, traces_dir: Path) -> None:
    """B6 regression: seen-identity is name+size+mtime, not the bare name —
    a file rewritten with new content must be scanned again."""
    store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), store)

    trace_file = traces_dir / "day1.json"
    trace_file.write_text(trace_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = watch_once(project_dir, traces_dir, _mandate(), store)
    assert len(result.digests) == 1
    store.close()


def test_watch_quarantines_corrupt_file_and_ingests_the_rest(
    project_dir: Path, traces_dir: Path
) -> None:
    """B3 regression: one bad file must never block the pipeline.

    The corrupt file is reported by name, the valid file still produces a
    digest, and the second pass is a full no-op (the corrupt file is
    quarantined, not retried forever)."""
    (traces_dir / "corrupt.json").write_text("{not json", encoding="utf-8")
    store = TraceStore(project_dir / "trace.db")

    result = watch_once(project_dir, traces_dir, _mandate(), store)
    assert len(result.digests) == 1
    assert len(result.failures) == 1
    assert result.failures[0].file_name == "corrupt.json"
    assert result.failures[0].error

    second_pass = watch_once(project_dir, traces_dir, _mandate(), store)
    assert second_pass.digests == ()
    assert second_pass.failures == ()
    store.close()


def test_watch_quarantines_malformed_otlp_file(project_dir: Path, tmp_path: Path) -> None:
    """Valid JSON that is not OTLP fails loudly once, then stays quarantined."""
    traces = tmp_path / "traces"
    traces.mkdir()
    (traces / "not-otlp.json").write_text('{"garbage": true}', encoding="utf-8")
    store = TraceStore(project_dir / "trace.db")

    result = watch_once(project_dir, traces, _mandate(), store)
    assert result.digests == ()
    assert len(result.failures) == 1
    assert result.failures[0].file_name == "not-otlp.json"
    assert store.count() == 0

    assert watch_once(project_dir, traces, _mandate(), store).failures == ()
    store.close()
