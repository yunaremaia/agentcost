"""Tests for init command and project-local config."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentcost.budget import load_budget_config, save_budget_config, PROJECT_CONFIG_NAME
from agentcost.cli import cli


class TestProjectLocalConfig:
    """Test project-local config loading and saving."""

    def test_save_project_config(self, tmp_path: Path) -> None:
        """Test saving project-local config."""
        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            target = save_budget_config(daily=5.0, weekly=25.0, monthly=100.0, project=True)
            assert target == tmp_path / PROJECT_CONFIG_NAME
            assert target.exists()
            content = target.read_text()
            assert "daily = 5.0" in content
            assert "weekly = 25.0" in content
            assert "monthly = 100.0" in content
        finally:
            os.chdir(old_cwd)

    def test_load_project_config(self, tmp_path: Path) -> None:
        """Test loading project-local config."""
        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            save_budget_config(daily=5.0, weekly=25.0, monthly=100.0, project=True)
            config = load_budget_config(tmp_path)
            assert config["daily"] == 5.0
            assert config["weekly"] == 25.0
            assert config["monthly"] == 100.0
        finally:
            os.chdir(old_cwd)

    def test_project_overrides_global(self, tmp_path: Path) -> None:
        """Test that project-local config overrides global config."""
        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            # Create a global config file manually
            global_config = tmp_path / ".agentcost"
            global_config.mkdir(exist_ok=True)
            global_file = global_config / "config.toml"
            global_file.write_text("[budget]\ndaily = 10.0\nweekly = 50.0\nmonthly = 200.0\n")
            
            # Patch the global config location
            with patch("agentcost.budget.CONFIG_FILE", global_file):
                with patch("agentcost.budget.CONFIG_DIR", global_config):
                    # Save project-local config (only daily differs)
                    save_budget_config(daily=7.0, project=True)
                    
                    config = load_budget_config(tmp_path)
                    assert config["daily"] == 7.0  # Project overrides
                    assert config["weekly"] == 50.0  # Global preserved
                    assert config["monthly"] == 200.0  # Global preserved
        finally:
            os.chdir(old_cwd)

    def test_no_project_config(self, tmp_path: Path) -> None:
        """Test loading when no project-local config exists."""
        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            save_budget_config(daily=10.0, project=False)  # Only global
            config = load_budget_config(tmp_path)
            assert config["daily"] == 10.0
        finally:
            os.chdir(old_cwd)

    def test_load_budget_config_default_cwd(self, tmp_path: Path) -> None:
        """Test load_budget_config with default CWD."""
        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            save_budget_config(daily=15.0, project=True)
            config = load_budget_config()  # No arg = use CWD
            assert config["daily"] == 15.0
        finally:
            os.chdir(old_cwd)


class TestInitCommand:
    """Test the init command."""

    def test_init_project(self, tmp_path: Path) -> None:
        """Test init command for project config."""
        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(cli, ["init", "--project"], input="5.0\n25.0\n100.0\n")
            assert result.exit_code == 0
            assert "Config saved" in result.output
            assert PROJECT_CONFIG_NAME in result.output
            assert (tmp_path / PROJECT_CONFIG_NAME).exists()
        finally:
            os.chdir(old_cwd)

    def test_init_invalid_input(self, tmp_path: Path) -> None:
        """Test init command with invalid input."""
        old_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(cli, ["init", "--project"], input="invalid\n25.0\n100.0\n")
            assert result.exit_code != 0
            assert "Invalid number" in result.output
        finally:
            os.chdir(old_cwd)
