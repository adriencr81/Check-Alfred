"""`alfred watch` — single-pass ingestion of new OTLP JSON files.

See PLAN.md §5 Brique 5 and docs/adr/0007-brique5-delivery-cli-design.md.
`watch_once` scans a directory for `*.json` files not already recorded in
`.alfred/seen.json`, ingests each into the trace store, and returns one
`Digest` per calendar day found among the newly-ingested events — grouped
by each event's own `start_time`, not "today", since an ingested file may
carry a historical trace.

The single pass is the default and the recommended path (re-run via cron,
see `alfred schedule`). `watch_loop` adds an opt-in continuous mode for
environments without cron (containers, CI); it wraps the same `watch_once`
primitive and reuses `.alfred/seen.json` so no digest is re-emitted between
passes. See docs/adr/0007 §1 and docs/adr/0015 for why.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from pathlib import Path

from alfred.mandate.model import Mandate
from alfred.report.build import BASELINE_WINDOW_DAYS, build_digest
from alfred.report.model import Digest
from alfred.trace.ingest import ingest_otlp_file
from alfred.trace.model import TraceEvent
from alfred.trace.store import TraceStore

_SEEN_FILENAME = "seen.json"


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


def _group_by_day(events: Iterable[TraceEvent]) -> dict[date, list[TraceEvent]]:
    by_day: dict[date, list[TraceEvent]] = defaultdict(list)
    for event in events:
        by_day[event.start_time.date()].append(event)
    return by_day


def _baseline_history(store: TraceStore, day: date) -> list[list[TraceEvent]]:
    """The rolling baseline window for `day`: the active days in `[day-7, day-1]`.

    Reads from the store (which already holds the just-ingested events),
    grouped by `start_time.date()` and excluding `day` itself. Only active days
    appear — an empty list means no baseline will be attached (F3, docs/adr/0019).
    """
    window = store.find_by_date_range(
        day - timedelta(days=BASELINE_WINDOW_DAYS), day - timedelta(days=1)
    )
    by_day = _group_by_day(window)
    return [by_day[prior] for prior in sorted(by_day)]


def watch_once(
    project_dir: Path, traces_dir: Path, mandate: Mandate, store: TraceStore
) -> list[Digest]:
    """Ingest OTLP JSON files in `traces_dir` not yet recorded as seen.

    Returns one `Digest` per calendar day among the newly-ingested events,
    ordered by date. Returns an empty list if every file was already seen
    (or `traces_dir` has no `*.json` files) — this is what makes a second
    call over the same directory a no-op.

    Each digest carries a rolling baseline computed from the prior days already
    in the store (F3), so a number reads against its own recent history.
    """
    seen = _load_seen(project_dir)
    new_files = sorted(p for p in Path(traces_dir).glob("*.json") if p.name not in seen)
    if not new_files:
        return []

    new_events: list[TraceEvent] = []
    for file_path in new_files:
        events = ingest_otlp_file(file_path)
        store.put_many(events)
        new_events.extend(events)
        seen.add(file_path.name)

    _save_seen(project_dir, seen)
    by_day = _group_by_day(new_events)
    return [
        build_digest(mandate, by_day[day], day, history=_baseline_history(store, day))
        for day in sorted(by_day)
    ]


def watch_loop(
    project_dir: Path,
    traces_dir: Path,
    mandate: Mandate,
    store: TraceStore,
    on_digests: Callable[[list[Digest]], None],
    *,
    interval_s: float,
    sleep: Callable[[float], None] | None = None,
    max_passes: int | None = None,
) -> None:
    """Run `watch_once` repeatedly, delivering each pass's digests.

    Opt-in continuous mode (ADR 0015). Each pass reuses `.alfred/seen.json`,
    so only newly-arrived trace files produce digests — no re-delivery. After
    a pass, sleeps `interval_s` before the next, unless `max_passes` is
    reached. `sleep` and `max_passes` are injected to keep the loop testable
    without real time; production passes `max_passes=None` (loop forever) and
    relies on `KeyboardInterrupt` to stop. `sleep` defaults to `time.sleep`,
    resolved at call time so it stays monkeypatchable.
    """
    do_sleep = time.sleep if sleep is None else sleep
    passes = 0
    while True:
        on_digests(watch_once(project_dir, traces_dir, mandate, store))
        passes += 1
        if max_passes is not None and passes >= max_passes:
            return
        do_sleep(interval_s)
