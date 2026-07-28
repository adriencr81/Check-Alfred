"""Owner-only writes for the files an Alfred project keeps on disk.

Four of them carry something their owner would not hand to every local account:
`.alfred/config.toml` (the Slack webhook URL — its path *is* the credential),
`.alfred/redaction-key` (the secret behind every mask), `.alfred/trace.db` and
`.alfred/seen.json` (tool arguments, i.e. whatever the agent handled). They were
created with the process umask, so typically world-readable — the gap ADR 0025
decision 7 closes.

`chmod` is not the same guarantee everywhere: on Windows the mode bits are
approximate and real protection comes from NTFS ACLs. This is a floor, not a
substitute for the platform's own access control.
"""

from __future__ import annotations

from pathlib import Path

_OWNER_ONLY = 0o600


def restrict(path: Path) -> None:
    """Narrow an existing file to owner read/write. Missing file: no-op."""
    if path.exists():
        path.chmod(_OWNER_ONLY)


def write_private(path: Path, text: str) -> None:
    """Write `text` to `path` with owner-only permissions.

    The file is created first and narrowed immediately: on POSIX the window is
    the same one `os.open(..., 0o600)` would leave for an already-existing file,
    and the parent directory is created if needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=_OWNER_ONLY, exist_ok=True)
    restrict(path)
    path.write_text(text, encoding="utf-8")
