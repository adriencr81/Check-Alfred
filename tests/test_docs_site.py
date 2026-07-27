"""The landing page is cited in every launch post, so it must build and it must
not quietly disagree with the README.

Two failure modes are worth a test. A `mkdocs.yml` that names a page which does
not exist fails the build — but only once someone runs it, which on a launch
morning is too late. And the landing restates the README's headline claims (the
install commands, the neighbours it compares itself to); when the README moves
and the landing does not, the page a newcomer reads first is the stale one.

What is deliberately *not* asserted: prose equality. The landing is allowed to
be shorter and phrased differently — it is a landing, not a mirror.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
MKDOCS = ROOT / "mkdocs.yml"
README = ROOT / "README.md"
DOCS_WORKFLOW = ROOT / ".github/workflows/docs.yml"


def _config() -> dict[str, Any]:
    config = yaml.safe_load(MKDOCS.read_text(encoding="utf-8"))
    assert isinstance(config, dict)
    return config


def _landing() -> str:
    config = _config()
    docs_dir = ROOT / str(config["docs_dir"])
    return (docs_dir / "index.md").read_text(encoding="utf-8")


def test_every_nav_page_exists() -> None:
    config = _config()
    docs_dir = ROOT / str(config["docs_dir"])
    assert docs_dir.is_dir(), f"docs_dir does not exist: {docs_dir}"
    for entry in config["nav"]:
        assert isinstance(entry, dict)
        for path in entry.values():
            assert (docs_dir / str(path)).is_file(), f"nav names a missing page: {path}"


def test_site_does_not_publish_the_strategy_documents() -> None:
    """`docs_dir` must stay a dedicated folder, never the whole `docs/` tree.

    `docs/` holds the growth plan (YC targets, revenue thresholds, the
    founder's own decision criteria) and the ADRs. Pointing mkdocs at it would
    publish all of that as official documentation on an indexed site.
    """
    docs_dir = (ROOT / str(_config()["docs_dir"])).resolve()
    assert docs_dir != (ROOT / "docs").resolve()
    published = {p.name for p in docs_dir.rglob("*.md")}
    assert "GROWTH_PLAN_3M.md" not in published
    assert not (docs_dir / "adr").exists()


def test_landing_install_commands_match_the_readme() -> None:
    """The zero-install command is the one a launch post sends people to."""
    landing = _landing()
    readme = README.read_text(encoding="utf-8")
    for command in ("uvx alfred-ai demo", "pip install alfred-ai"):
        assert command in landing, f"landing lost the documented command: {command}"
        assert command in readme, f"README and landing disagree on: {command}"


def test_readme_states_no_test_count() -> None:
    """A hardcoded suite size on the front page is stale the next commit.

    It went 398 → 400 → 401 in a single day, each time contradicting a page
    whose whole argument is that no number should be self-declared. The CI
    badge is the living version of the claim; this is a guarded regression, so
    it fails the day someone writes the number back in.
    """
    readme = README.read_text(encoding="utf-8")
    stale = re.findall(r"\d+\s+tests\b", readme)
    assert not stale, f"README states a test count that will drift: {stale}"


def test_deploy_queues_instead_of_racing_itself() -> None:
    """Two pushes to main close together must not fail the second deployment.

    GitHub Pages accepts one deployment at a time; without a concurrency group
    the second gets a 400 and main shows a red run for something that is not a
    defect. `cancel-in-progress` must stay false so a deployment already under
    way is allowed to finish.
    """
    workflow = yaml.safe_load(DOCS_WORKFLOW.read_text(encoding="utf-8"))
    concurrency = workflow["jobs"]["deploy"]["concurrency"]
    assert concurrency["group"], "deploy job lost its concurrency group"
    assert concurrency["cancel-in-progress"] is False

    # On the job, not the workflow: pull request builds never deploy, so
    # serialising them behind the same group would queue them for nothing.
    assert "concurrency" not in workflow


def test_landing_compares_the_same_neighbours_as_the_readme() -> None:
    landing = _landing()
    readme = README.read_text(encoding="utf-8")
    for neighbour in ("Langfuse", "AgentOps", "LangSmith", "Guardrails", "Grafana"):
        assert neighbour in landing, f"landing dropped a neighbour: {neighbour}"
        assert neighbour in readme, f"README dropped a neighbour: {neighbour}"
