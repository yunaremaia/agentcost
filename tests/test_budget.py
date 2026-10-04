"""Tests for budget management and compare command."""
from __future__ import annotations
import click
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agentcost.budget import (
    load_budget_config,
    save_budget_config,
    CONFIG_FILE,
    PROJECT_CONFIG_NAME,
)
from agentcost.cli import cli


class TestBudgetConfig:
    def test_load_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)
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

    def test_load_corrupt_file_raises(self, tmp_path, monkeypatch):
        """A corrupt config is an error, not an empty config: 'budget set' would
        otherwise overwrite the very file the user needs to repair."""
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        (tmp_path / "config.toml").write_text("not valid toml {{{")
        with pytest.raises(click.ClickException) as excinfo:
            load_budget_config()
        assert str(tmp_path / "config.toml") in str(excinfo.value)

    def test_load_corrupt_project_file_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        (tmp_path / PROJECT_CONFIG_NAME).write_text("[budget\ndaily =")
        with pytest.raises(click.ClickException) as excinfo:
            load_budget_config(tmp_path)
        assert str(tmp_path / PROJECT_CONFIG_NAME) in str(excinfo.value)

    def test_load_missing_file_stays_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)
        assert not (tmp_path / "config.toml").exists()
        assert not (tmp_path / PROJECT_CONFIG_NAME).exists()
        assert load_budget_config(tmp_path) == {}


class TestConfigFilePreservation:
    """save_budget_config must only touch the [budget] table."""

    def test_save_preserves_other_sections(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "config.toml"
        config.write_text('[budget]\ndaily = 10.0\nweekly = 20.0\n\n[alerts]\nemail = "y@x.io"\n')
        save_budget_config(daily=15.0)
        after = config.read_text()
        assert "[alerts]" in after
        assert 'email = "y@x.io"' in after
        assert "daily = 15.0" in after
        assert "weekly = 20.0" in after

    def test_save_preserves_comments(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "config.toml"
        config.write_text(
            "# team config, edit freely\n"
            "[budget]\n"
            "# hard cap, do not remove\n"
            "daily = 10.0\n"
            "\n"
            "[alerts]\n"
            "# keep me\n"
            'email = "y@x.io"\n'
        )
        save_budget_config(daily=15.0)
        after = config.read_text()
        assert "# team config, edit freely" in after
        assert "# hard cap, do not remove" in after
        assert "# keep me" in after

    def test_save_creates_budget_section_in_other_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "config.toml"
        config.write_text('[alerts]\nemail = "y@x.io"\n')
        save_budget_config(daily=5.0)
        after = config.read_text()
        assert "[alerts]" in after
        assert load_budget_config() == {"daily": 5.0}


class TestCorruptConfigInCLI:
    def test_budget_show_reports_corrupt_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.toml").write_text("not valid toml {{{")
        from click.testing import CliRunner

        result = CliRunner().invoke(cli, ["budget", "show"])
        assert result.exit_code != 0
        assert "config.toml" in result.output

    def test_budget_check_does_not_ask_for_a_set_that_overwrites(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.toml").write_text("not valid toml {{{")
        from click.testing import CliRunner

        result = CliRunner().invoke(cli, ["budget", "check"])
        assert result.exit_code != 0
        assert "No budget thresholds set" not in result.output

    def test_budget_set_refuses_to_overwrite_corrupt_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "config.toml"
        config.write_text("not valid toml {{{")
        from click.testing import CliRunner

        result = CliRunner().invoke(cli, ["budget", "set", "--daily", "5.0"])
        assert result.exit_code != 0
        assert config.read_text() == "not valid toml {{{"

    def test_empty_budget_exit_codes_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "config.toml")
        monkeypatch.chdir(tmp_path)
        from click.testing import CliRunner

        assert CliRunner().invoke(cli, ["budget", "show"]).exit_code == 0
        assert CliRunner().invoke(cli, ["budget", "check"]).exit_code == 1


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
