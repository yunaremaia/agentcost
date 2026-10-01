"""Guard the published distribution name against the README and the packaging.

`agentcost` on PyPI belongs to an unrelated project (author Kushagra Agrawal,
github.com/agentcost-ai/agentcost-sdk), so `pip install agentcost` installs
someone else's package. This distribution ships as `agentcost-py`.

The guard reads `[project] name` from pyproject instead of hardcoding it, so the
next rename fails here rather than in a user's terminal.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
ACTION_YML = REPO_ROOT / "action.yml"
PRE_COMMIT_HOOKS = REPO_ROOT / ".pre-commit-hooks.yaml"

# The short name is owned by a third party on PyPI. Any install of the bare
# short name is wrong. The negative lookahead is essential: without it
# "pip install agentcost" is a substring of the correct "pip install agentcost-py"
# and this guard would reject the line it exists to protect. All whitespace is
# [ \t] rather than \s so the pattern cannot cross a line boundary and match a
# different line's `agentcost` (e.g. a step named "Run agentcost").
SHORT_NAME_INSTALL = re.compile(
    r"pip(?:3)?[ \t]+install[ \t]+(?:[^\s=!<>]+[ \t]+)*agentcost(?![\w-])"
)

# A from-source install is legitimate and must not be flagged.
SOURCE_INSTALL = re.compile(r"install\s+[^\s]*git\+https?://", re.IGNORECASE)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def project_name() -> str:
    """Extract `[project] name` without tomllib (CI runs Python 3.10)."""
    text = read(PYPROJECT)
    match = re.search(r'^\[project\]\s*$(.*?)(?=^\[|\Z)', text, re.MULTILINE | re.DOTALL)
    assert match, "no [project] table in pyproject.toml"
    name = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', match.group(1), re.MULTILINE)
    assert name, "no [project] name in pyproject.toml"
    return name.group(1)


def install_name(readme: str) -> str:
    """The distribution name the README tells people to install."""
    match = re.search(r"pip(?:3)?\s+install\s+([A-Za-z0-9._-]+)", readme)
    assert match, "README has no `pip install <name>` line"
    return match.group(1)


@pytest.fixture(scope="module")
def readme() -> str:
    return read(README)


def test_readme_install_name_matches_pyproject(readme: str) -> None:
    """(d) The install line and [project] name must be the same distribution."""
    assert install_name(readme) == project_name()


def test_readme_does_not_advertise_the_conflicting_short_name(readme: str) -> None:
    """(b) `pip install agentcost` installs a different author's package."""
    offenders = [
        line
        for line in readme.splitlines()
        if SHORT_NAME_INSTALL.search(line) and not SOURCE_INSTALL.search(line)
    ]
    assert not offenders, (
        "README still tells users to install the short name `agentcost`, which "
        f"belongs to an unrelated project on PyPI: {offenders}"
    )


def test_readme_documents_the_name_conflict(readme: str) -> None:
    """(c) Say plainly which name belongs to whom, so nobody falls in again."""
    paragraphs = [p.strip() for p in readme.split("\n\n") if p.strip()]
    notes = [
        p
        for p in paragraphs
        if re.search(r"`agentcost`", p)
        and re.search(r"another|different|unrelated|not this", p, re.IGNORECASE)
    ]
    assert notes, (
        "README must explain that the short PyPI name `agentcost` belongs to "
        "another project and that this tool is installed as "
        f"`{project_name()}`"
    )


def test_composite_action_installs_the_distribution(readme: str) -> None:
    """action.yml runs at install time for anyone using the repo as an Action."""
    action = read(ACTION_YML)
    installed = re.findall(r"pip(?:3)?\s+install\s+([A-Za-z0-9._-]+)", action)
    assert installed, "action.yml no longer installs agentcost from PyPI"
    assert all(name == project_name() for name in installed), (
        f"action.yml must install {project_name()!r}, found {installed}"
    )
    assert not SHORT_NAME_INSTALL.search(action)


def test_pre_commit_hook_installs_the_distribution() -> None:
    """`additional_dependencies` is handed straight to pip by pre-commit."""
    hooks = read(PRE_COMMIT_HOOKS)
    block = re.search(
        r"^\s*additional_dependencies:\s*$(.*?)(?=^\S|\Z)",
        hooks,
        re.MULTILINE | re.DOTALL,
    )
    assert block, "no additional_dependencies in .pre-commit-hooks.yaml"
    # Only the requirements under additional_dependencies; `- id:` is a hook id.
    deps = re.findall(r"^\s*-\s*[\"']?([A-Za-z0-9._-]+)", block.group(1), re.MULTILINE)
    assert deps, "additional_dependencies block is empty"
    assert all(
        re.split(r"[<>=!\[ ]", dep)[0] == project_name() for dep in deps
    ), f"pre-commit hook must depend on {project_name()!r}, found {deps}"


def test_only_the_distribution_name_changed() -> None:
    """The importable package, the CLI entry point and the repo name are unchanged."""
    pyproject = read(PYPROJECT)
    assert '[project.scripts]\nagentcost = "agentcost.cli:cli"' in pyproject
    assert 'include = ["agentcost*"]' in pyproject
    assert project_name() != "agentcost", (
        "the distribution must not be published under the conflicting short name"
    )


def test_no_pypi_badge_while_unpublished(readme: str) -> None:
    """A badge for a package that is not on PyPI renders 'not found'."""
    assert "img.shields.io/pypi" not in readme, (
        "no PyPI badge until the package is actually published"
    )
