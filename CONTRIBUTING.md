# Contributing to Alfred

Alfred's workflow rules live in [`CLAUDE.md`](CLAUDE.md) — they apply to
every contributor, human or agent. The short version:

- **Tests first, and falsifiable.** New behavior lands with a test that
  fails without it. `pytest -q` must be green before you open a PR.
- **The event-id anchoring rule is non-negotiable.** Every line of a
  report must trace back to a specific trace event. If a change can't
  satisfy this, stop and discuss before writing code — see
  [`docs/verified_nlg.md`](docs/verified_nlg.md) for what this guarantees
  and how it's tested.
- **Surgical changes.** One coherent unit of work per PR/commit. No
  drive-by refactors or renames bundled with a feature or fix.
- **No silent assumptions.** If a requirement is ambiguous (mandate
  semantics, deviation thresholds, digest format), open an issue or ask
  in the PR rather than guessing.

## Local setup

```bash
pip install -e ".[dev]"
pre-commit install
```

## Before opening a PR

```bash
pytest -q
ruff check . && mypy --strict src/
```

CI (`.github/workflows/ci.yml`) runs the same three commands on Python
3.11 and 3.12; `.github/workflows/codeql.yml` runs a static security scan.
Both must pass.

## Design decisions

Non-obvious decisions (deviations from `PLAN.md`, choices the plan left
open) are recorded as dated ADRs under `docs/adr/`. If your change makes
one of these calls, add an ADR alongside it — see the existing ones for
the expected format.
