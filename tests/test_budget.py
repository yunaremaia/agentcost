"""Tests for budget management and compare command."""
from __future__ import annotations
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agentcost.budget import load_budget_config, save_budget_config, CONFIG_FILE
from agentcost.cli import cli


class TestBudgetConfig:
    def test_load_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        assert load_budget_config() == {}

    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        save_budget_config(daily=5.0, weekly=25.0, monthly=100.0)
        config = load_budget_config()
        assert config["daily"] == 5.0
        assert config["weekly"] == 25.0
        assert config["monthly"] == 100.0

    def test_save_partial(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        save_budget_config(daily=10.0)
        config = load_budget_config()
        assert config == {"daily": 10.0}

    def test_load_corrupt_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        (tmp_path / "config.toml").write_text("not valid toml {{{")
        assert load_budget_config() == {}


class TestBudgetCommand:
    def test_budget_set(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, ["budget", "set", "--daily", "5.0", "--weekly", "25.0"])
        assert result.exit_code == 0
        assert "saved" in result.output

    def test_budget_show_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, ["budget", "show"])
        assert result.exit_code == 0
        assert "No budget" in result.output

    def test_budget_show_configured(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        save_budget_config(daily=5.0)
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, ["budget", "show"])
        assert result.exit_code == 0
        assert "5.0" in result.output

    def test_budget_check_no_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, ["budget", "check"])
        assert result.exit_code == 1
