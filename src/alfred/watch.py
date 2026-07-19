"""`alfred watch` — single-pass ingestion of new OTLP JSON files.

See PLAN.md §5 Brique 5 and docs/adr/0007-brique5-delivery-cli-design.md.
`watch_once` scans a directory for `*.json` files not already recorded in
`.alfred/seen.json`, ingests each into the trace store, and returns one
`Digest` per calendar day found among the newly-ingested events — grouped
by each event's own `start_time`, not "today", since an ingested file may
carry a historical trace.

A file that cannot be ingested (invalid JSON, malformed OTLP, unreadable)
is quarantined: reported in the result's `failures`, marked seen so it is
not retried on every run, and the rest of the batch still goes through —
one bad file must never block the pipeline (see ADR 0011, arbitrage S3).

No daemon, no polling loop: each invocation does one pass and exits. See
the ADR for why (zero-infra philosophy, simpler to test, cron-friendly).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from alfred.mandate.model import Mandate
from alfred.report.build import build_digest
from alfred.report.model import Digest
from alfred.trace.ingest import ingest_otlp_file
from alfred.trace.model import TraceEvent, TraceIngestionError
from alfred.trace.store import TraceStore

_SEEN_FILENAME = "seen.json"


@dataclass(frozen=True, slots=True)
class FileFailure:
    """A trace file that could not be ingested, and why."""

    file_name: str
    error: str


@dataclass(frozen=True, slots=True)
class WatchResult:
    digests: tuple[Digest, ...]
    failures: tuple[FileFailure, ...]


def _seen_path(project_dir: Path) -> Path:
    return project_dir / ".alfred" / _SEEN_FILENAME


def _load_seen(project_dir: Path) -> set[str]:
    path = _seen_path(project_dir)
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")))


def _save_seen(project_dir: Path, seen: set[str]) -> None:
    path = _seen_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(seen)), encoding="utf-8")


def watch_once(
    project_dir: Path, traces_dir: Path, mandate: Mandate, store: TraceStore
) -> WatchResult:
    """Ingest OTLP JSON files in `traces_dir` not yet recorded as seen.

    Returns one `Digest` per calendar day among the newly-ingested events,
    ordered by date, plus one `FileFailure` per file that could not be
    ingested. Every scanned file — ingested or failed — is marked seen, so
    a second call over the same directory is a no-op.
    """
    seen = _load_seen(project_dir)
    new_files = sorted(p for p in Path(traces_dir).glob("*.json") if p.name not in seen)
    if not new_files:
        return WatchResult(digests=(), failures=())

    by_day: dict[date, list[TraceEvent]] = defaultdict(list)
    failures: list[FileFailure] = []
    for file_path in new_files:
        try:
            events = ingest_otlp_file(file_path)
        except (TraceIngestionError, ValueError, OSError) as exc:
            failures.append(FileFailure(file_name=file_path.name, error=str(exc)))
            seen.add(file_path.name)
            continue
        store.put_many(events)
        for event in events:
            by_day[event.start_time.date()].append(event)
        seen.add(file_path.name)

    _save_seen(project_dir, seen)
    return WatchResult(
        digests=tuple(build_digest(mandate, by_day[day], day) for day in sorted(by_day)),
        failures=tuple(failures),
    )
