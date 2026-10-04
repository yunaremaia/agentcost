"""Budget management for agentcost."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import click

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef,no-unresolved-imports]

CONFIG_DIR = Path.home() / ".agentcost"
CONFIG_FILE = CONFIG_DIR / "config.toml"
PROJECT_CONFIG_NAME = ".agentcost.toml"


def validate_threshold(value: float, name: str):
    """Reject invalid spending thresholds before saving or checking usage."""
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise click.BadParameter(f"{name} must be a finite positive number, got {value}")


def _ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_toml_file(path: Path) -> dict:
    """Load a TOML file and return its 'budget' section.

    A missing file is an empty config. A file that exists but does not parse is
    an error: reporting it as {} makes the CLI say "no budget configured" and
    point at `budget set`, which would overwrite the very file the user has to
    repair by hand.
    """
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise click.ClickException(
            f"{path} is not valid TOML: {e}\n"
            "Fix the file by hand, or delete it to start from scratch. "
            "agentcost will not overwrite it."
        ) from e
    budget = data.get("budget", {})
    if not isinstance(budget, dict):
        raise click.ClickException(f"{path}: [budget] must be a table.")
    return budget


def _toml_value(value) -> str:
    """Render a Python value as a TOML scalar."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    return repr(value)


def _merge_budget_section(text: str, updates: dict) -> str:
    """Return `text` with only the given keys changed inside its [budget] table.

    Every other line -- other tables, comments, blank lines, the user's own
    formatting -- is copied through verbatim, so setting a threshold cannot
    destroy the rest of the config.
    """
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == "[budget]"), None)
    if start is None:
        head = lines + [""] if lines else []
        tail = ["[budget]"] + [f"{k} = {_toml_value(v)}" for k, v in updates.items()]
        return "\n".join(head + tail) + "\n"

    # The table ends at the next table header.
    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = i
            break

    section = lines[start + 1 : end]
    for key, value in updates.items():
        rendered = f"{key} = {_toml_value(value)}"
        for j, line in enumerate(section):
            name, sep, _ = line.partition("=")
            if sep and name.strip() == key:
                section[j] = rendered
                break
        else:
            section.append(rendered)

    return "\n".join(lines[: start + 1] + section + lines[end:]) + "\n"


def load_budget_config(cwd: Optional[Path] = None) -> dict:
    """Load budget configuration with project-local override.
    
    Priority: project-local (.agentcost.toml in CWD) > global (~/.agentcost/config.toml).
    Project-local values override global values for matching keys.
    """
    global_config = _load_toml_file(CONFIG_FILE)
    
    project_config = {}
    if cwd is not None:
        project_config = _load_toml_file(cwd / PROJECT_CONFIG_NAME)
    else:
        # Try CWD
        project_config = _load_toml_file(Path.cwd() / PROJECT_CONFIG_NAME)
    
    # Merge: project-local overrides global
    merged = {**global_config, **project_config}
    return merged


def save_budget_config(daily: Optional[float] = None, weekly: Optional[float] = None, monthly: Optional[float] = None, project: bool = False):
    """Save budget thresholds to config file.
    
    Args:
        daily: Daily budget in USD
        weekly: Weekly budget in USD
        monthly: Monthly budget in USD
        project: If True, save to .agentcost.toml in CWD instead of global
    """
    config = {}
    if daily is not None:
        config["daily"] = daily
    if weekly is not None:
        config["weekly"] = weekly
    if monthly is not None:
        config["monthly"] = monthly

    for name, value in config.items():
        validate_threshold(value, f"{name} budget")
    
    if project:
        target = Path.cwd() / PROJECT_CONFIG_NAME
    else:
        _ensure_config_dir()
        target = CONFIG_FILE

    # Read the file as text and edit only the [budget] table, so other tables
    # and comments survive. A file that does not parse raises from the load
    # below instead of being overwritten.
    _load_toml_file(target)
    text = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(_merge_budget_section(text, config), encoding="utf-8")
    return target
