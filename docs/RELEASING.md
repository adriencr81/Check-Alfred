# Releasing Alfred to PyPI

Alfred publishes via **PyPI Trusted Publishing** (OIDC): GitHub Actions proves
the repo's identity to PyPI, so there is **no token or password to store**. The
pipeline (`.github/workflows/release.yml`) currently targets **TestPyPI** — a
throwaway index to rehearse the release without burning the real `alfred-ai`
name. Switching to real PyPI for the v0.1 launch is a one-line change.

## One-time setup on TestPyPI (you, ~2 minutes)

The workflow can't publish until TestPyPI knows to trust it. Configure a
**pending publisher** (no account-side project needs to exist yet):

1. Sign in at <https://test.pypi.org> (create an account if needed).
2. Go to **Account settings → Publishing → Add a pending publisher**.
3. Fill in exactly:
   - **PyPI Project Name**: `alfred-ai`
   - **Owner**: `adriencr81`
   - **Repository name**: `Check-Alfred`
   - **Workflow name**: `release.yml`
   - **Environment name**: `testpypi`
4. Save.

## Rehearse the publish

- **Manual run (recommended for the dry run):** GitHub → **Actions → Release →
  Run workflow** on your branch. The `build` job builds + `twine check`s, then
  `publish-testpypi` uploads to TestPyPI.
- **Or push a tag:** `git tag v0.1.0.dev0 && git push origin v0.1.0.dev0`.

Verify the result at <https://test.pypi.org/project/alfred-ai/> and install it
in a clean venv:

```bash
pip install -i https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ alfred-ai
alfred demo
```

(The extra index lets the real `pyyaml` dependency resolve from PyPI while
`alfred-ai` comes from TestPyPI.)

> TestPyPI rejects re-uploading a version that already exists. To rehearse
> again, bump the version (`0.1.0.dev1`, …) in `pyproject.toml`.

## Going live on real PyPI (August, when you're ready)

1. Add a pending publisher on <https://pypi.org> with the **same** five values
   as above, but environment name `pypi`.
2. In `.github/workflows/release.yml`, point the publish job at real PyPI:
   rename `publish-testpypi` → `publish-pypi`, set `environment: pypi`, and
   **remove** the `repository-url:` line (it defaults to real PyPI).
3. Set the release version in `pyproject.toml` to `0.1.0` (drop the `.dev`).
4. Tag it: `git tag v0.1.0 && git push origin v0.1.0`. CI publishes.
5. `pip install alfred-ai` now works for everyone. **This is irreversible** —
   the name and version are permanent.

## Why this shape

- **Trusted Publishing over API tokens** — nothing secret lives in the repo or
  in GitHub secrets; the OIDC exchange is short-lived and scoped.
- **TestPyPI first** — the real name is claimed exactly once and a version can
  never be re-uploaded, so we rehearse on a disposable index. See
  [ADR 0016](adr/0016-pypi-trusted-publishing.md).
