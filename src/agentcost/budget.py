"""Budget management for agentcost."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".agentcost"
CONFIG_FILE = CONFIG_DIR / "config.toml"
PROJECT_CONFIG_NAME = ".agentcost.toml"


def _ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_toml_file(path: Path) -> dict:
    """Load a TOML file and return its 'budget' section, or {} on error."""
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
            return data.get("budget", {})
    except Exception:
        return {}


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
    
    if project:
        target = Path.cwd() / PROJECT_CONFIG_NAME
    else:
        _ensure_config_dir()
        target = CONFIG_FILE
    
    # Merge with existing config
    existing = _load_toml_file(target)
    existing.update(config)
    
    # Write TOML
    lines = ["[budget]"]
    if "daily" in existing:
        lines.append(f'daily = {existing["daily"]}')
    if "weekly" in existing:
        lines.append(f'weekly = {existing["weekly"]}')
    if "monthly" in existing:
        lines.append(f'monthly = {existing["monthly"]}')
    
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
