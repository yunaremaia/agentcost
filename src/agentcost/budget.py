"""Budget management for agentcost."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".agentcost"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def _ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_budget_config() -> dict:
    """Load budget configuration from ~/.agentcost/config.toml."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
            return data.get("budget", {})
    except Exception:
        return {}


def save_budget_config(daily: Optional[float] = None, weekly: Optional[float] = None, monthly: Optional[float] = None):
    """Save budget thresholds to config file."""
    _ensure_config_dir()
    config = {}
    if daily is not None:
        config["daily"] = daily
    if weekly is not None:
        config["weekly"] = weekly
    if monthly is not None:
        config["monthly"] = monthly
    
    # Write TOML manually to avoid dependency
    lines = ["[budget]"]
    if "daily" in config:
        lines.append(f'daily = {config["daily"]}')
    if "weekly" in config:
        lines.append(f'weekly = {config["weekly"]}')
    if "monthly" in config:
        lines.append(f'monthly = {config["monthly"]}')
    
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
