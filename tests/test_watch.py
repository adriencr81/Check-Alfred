"""alfred.watch — single-pass ingestion, no re-ingestion of seen files.

See PLAN.md §5 Brique 5 (`test_watch_ingests_new_files_only`) and
docs/adr/0007-brique5-delivery-cli-design.md.
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


def test_watch_persists_seen_state_across_processes(project_dir: Path, traces_dir: Path) -> None:
    """A fresh `TraceStore`/call (simulating a new CLI invocation) still
    skips files ingested by a prior call, since seen-state lives on disk."""
    first_store = TraceStore(project_dir / "trace.db")
    watch_once(project_dir, traces_dir, _mandate(), first_store)
    first_store.close()

    second_store = TraceStore(project_dir / "trace.db")
    assert watch_once(project_dir, traces_dir, _mandate(), second_store) == []
    second_store.close()
