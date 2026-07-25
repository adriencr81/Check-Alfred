"""`alfred watch` — single-pass ingestion of new OTLP JSON files.

See PLAN.md §5 Brique 5 and docs/adr/0007-brique5-delivery-cli-design.md.
`watch_once` scans a directory for `*.json` files whose content is not
already recorded in `.alfred/seen.json`, ingests each into the trace store,
and returns one `Digest` per calendar day found among the newly-ingested
events — grouped by each event's own `start_time`, not "today", since an
ingested file may carry a historical trace.

A file is recognized by the SHA-256 of its bytes, not by its name: rewriting
an already-ingested file used to hide the new activity for good (ADR 0024
decision 4). A file that cannot be read is quarantined rather than fatal, and
reported on every pass until a human fixes or removes it (decisions 2 and 3).

The single pass is the default and the recommended path (re-run via cron,
see `alfred schedule`). `watch_loop` adds an opt-in continuous mode for
environments without cron (containers, CI); it wraps the same `watch_once`
primitive and reuses `.alfred/seen.json` so no digest is re-emitted between
passes. See docs/adr/0007 §1 and docs/adr/0015 for why.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from alfred._fs import write_private
from alfred.mandate.model import Mandate
from alfred.report.build import BASELINE_WINDOW_DAYS, build_digest
from alfred.report.model import Digest
from alfred.trace.ingest import ingest_otlp_file
from alfred.trace.model import TraceEvent, TraceIngestionError
from alfred.trace.redact import redactor_for
from alfred.trace.store import TraceStore

_SEEN_FILENAME = "seen.json"
_STATE_VERSION = 2
_INGESTED = "ingested"
_QUARANTINED = "quarantined"
_HASH_CHUNK_BYTES = 1 << 20


@dataclass(frozen=True, slots=True)
class QuarantinedTrace:
    """A trace file `watch_once` could not read, and why."""

    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class WatchPass:
    """The outcome of one `watch_once` pass.

    `quarantined` lists *every* file still in quarantine, not only the ones this
    pass tripped over: a hole in the audit must stay visible in the cron log
    until a human fixes or removes the file (ADR 0024 decision 3).
    """

    digests: list[Digest]
    quarantined: tuple[QuarantinedTrace, ...] = ()
    # Events refused because their `event_id` is already stored with different
    # content: an attempt to rewrite evidence a past digest may already quote
    # (ADR 0026 decisions 4 and 5). Reported like a quarantine, per pass.
    conflicts: tuple[TraceEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class _SeenFile:
    """What a past pass did with a file, and the content it did it to.

    `sha256` is None only for a v1 entry whose file is absent from the traces
    directory: an unknown digest never matches, so a file later appearing under
    that name is ingested rather than assumed handled (ADR 0024 decision 5).
    """

    sha256: str | None
    status: str
    reason: str | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _seen_path(project_dir: Path) -> Path:
    return project_dir / ".alfred" / _SEEN_FILENAME


def _load_state(project_dir: Path) -> dict[str, _SeenFile]:
    """Read `.alfred/seen.json`, accepting the v1 format (a list of names).

    A v1 entry carries no digest; `watch_once` adopts the file's current one on
    the next pass without re-ingesting it, so upgrading never replays a day's
    digests (ADR 0024 decision 5).
    """
    path = _seen_path(project_dir)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):  # v1: names only, all of them ingested
        return {str(name): _SeenFile(sha256=None, status=_INGESTED) for name in raw}
    return {
        str(name): _SeenFile(
            sha256=entry.get("sha256"),
            status=str(entry["status"]),
            reason=entry.get("reason"),
        )
        for name, entry in raw["files"].items()
    }


def _save_state(project_dir: Path, state: dict[str, _SeenFile]) -> None:
    files = {
        name: {"sha256": entry.sha256, "status": entry.status, "reason": entry.reason}
        for name, entry in sorted(state.items())
    }
    # Owner-only: quarantine reasons quote the trace, so this file can carry
    # fragments of what the agent handled (ADR 0025 decision 7).
    write_private(
        _seen_path(project_dir), json.dumps({"version": _STATE_VERSION, "files": files}, indent=2)
    )


def _quarantined(state: dict[str, _SeenFile]) -> tuple[QuarantinedTrace, ...]:
    return tuple(
        QuarantinedTrace(name=name, reason=entry.reason or "unknown")
        for name, entry in sorted(state.items())
        if entry.status == _QUARANTINED
    )


def _group_by_day(events: Iterable[TraceEvent]) -> dict[date, list[TraceEvent]]:
    by_day: dict[date, list[TraceEvent]] = defaultdict(list)
    for event in events:
        by_day[event.start_time.date()].append(event)
    return by_day


def _baseline_windows(
    store: TraceStore, days: Sequence[date]
) -> dict[date, list[list[TraceEvent]]]:
    """The rolling baseline window (F3) for each day in `days`, in one query.

    A day's window is its active prior days in `[day-7, day-1]`, grouped by
    `start_time.date()` — exactly what the per-day query returned before, but
    the union of every window is `[min-7, max-1]`, so one `find_by_date_range`
    over that span feeds them all instead of one query per day (whose windows
    largely overlap). Each day then slices the shared grouping to its own
    window; only active days appear, so an empty list means no baseline
    (docs/adr/0019).
    """
    if not days:
        return {}
    prior = store.find_by_date_range(
        min(days) - timedelta(days=BASELINE_WINDOW_DAYS), max(days) - timedelta(days=1)
    )
    by_day = _group_by_day(prior)
    active_days = sorted(by_day)
    return {
        day: [
            by_day[prior_day]
            for prior_day in active_days
            if day - timedelta(days=BASELINE_WINDOW_DAYS) <= prior_day <= day - timedelta(days=1)
        ]
        for day in days
    }


def build_digests(
    mandate: Mandate, events: Iterable[TraceEvent], store: TraceStore
) -> list[Digest]:
    """Build one `Digest` per calendar day present in `events`, ordered by date.

    `events` must already be in `store` (the caller ingests them first) so each
    day's rolling baseline (F3) can read the prior days. This is the shared core
    of the digest pipeline — day-grouping plus baseline — reused by `watch_once`
    and by `alfred report`, without the seen-file bookkeeping that is specific to
    `watch`.
    """
    by_day = _group_by_day(events)
    days = sorted(by_day)
    windows = _baseline_windows(store, days)
    return [build_digest(mandate, by_day[day], day, history=windows[day]) for day in days]


def watch_once(
    project_dir: Path, traces_dir: Path, mandate: Mandate, store: TraceStore
) -> WatchPass:
    """Ingest OTLP JSON files in `traces_dir` not yet recorded as seen.

    Returns one `Digest` per calendar day among the newly-ingested events,
    ordered by date, plus every file still in quarantine. The digests are empty
    if every file was already seen (or `traces_dir` has no `*.json` files) —
    this is what makes a second call over the same directory a no-op.

    A file that cannot be read is quarantined, not fatal: the pass carries on
    with the other files and records the failure, so one malformed span can
    neither hide the rest of the day nor stop `alfred watch` for good (ADR
    0024 decisions 2 and 3). The state is written after each file — and only
    once its events are in the store — so an interrupted pass never replays
    work it already did (decision 6).

    Each digest carries a rolling baseline computed from the prior days already
    in the store (F3), so a number reads against its own recent history.
    """
    state = _load_state(project_dir)
    redactor = redactor_for(project_dir, mandate.redact)
    new_events: list[TraceEvent] = []
    conflicts: list[TraceEvent] = []
    for file_path in sorted(Path(traces_dir).glob("*.json")):
        try:
            content = _sha256(file_path)
        except OSError as exc:
            state[file_path.name] = _SeenFile(sha256=None, status=_QUARANTINED, reason=str(exc))
            _save_state(project_dir, state)
            continue
        known = state.get(file_path.name)
        if known is not None and known.sha256 == content:
            continue  # same file, same bytes — already handled
        if known is not None and known.sha256 is None and known.status == _INGESTED:
            # v1 state: adopt the current content rather than re-emit its digest.
            state[file_path.name] = _SeenFile(sha256=content, status=_INGESTED)
            _save_state(project_dir, state)
            continue
        try:
            events = ingest_otlp_file(file_path, redactor)
        except (TraceIngestionError, OSError) as exc:
            state[file_path.name] = _SeenFile(
                sha256=content, status=_QUARANTINED, reason=str(exc)
            )
            _save_state(project_dir, state)
            continue
        conflicts.extend(store.put_many(events))
        new_events.extend(events)
        state[file_path.name] = _SeenFile(sha256=content, status=_INGESTED)
        _save_state(project_dir, state)

    return WatchPass(
        digests=build_digests(mandate, new_events, store),
        quarantined=_quarantined(state),
        conflicts=tuple(conflicts),
    )


def watch_loop(
    project_dir: Path,
    traces_dir: Path,
    mandate: Mandate,
    store: TraceStore,
    on_pass: Callable[[WatchPass], None],
    *,
    interval_s: float,
    sleep: Callable[[float], None] | None = None,
    max_passes: int | None = None,
) -> None:
    """Run `watch_once` repeatedly, handing each pass's outcome to `on_pass`.

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
        on_pass(watch_once(project_dir, traces_dir, mandate, store))
        passes += 1
        if max_passes is not None and passes >= max_passes:
            return
        do_sleep(interval_s)
