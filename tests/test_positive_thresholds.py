"""Budget thresholds must be positive before any side effects occur."""

from unittest.mock import patch

import pytest
import click
from click.testing import CliRunner

from agentcost.budget import load_budget_config, save_budget_config
from agentcost.cli import cli


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly"])
@pytest.mark.parametrize("value", ["0", "-5", "nan", "inf"])
def test_budget_set_rejects_invalid_threshold(tmp_path, monkeypatch, period, value):
    target = tmp_path / "config.toml"
    target.write_text("[budget]\ndaily = 10.0\n", encoding="utf-8")
    monkeypatch.setattr("agentcost.budget.CONFIG_FILE", target)
    result = CliRunner().invoke(cli, ["budget", "set", f"--{period}", value])
    assert result.exit_code == 2
    assert "positive" in result.output
    assert period in result.output
    assert target.read_text(encoding="utf-8") == "[budget]\ndaily = 10.0\n"


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly"])
@pytest.mark.parametrize("value", ["0", "-5", "nan", "inf"])
def test_budget_check_rejects_invalid_config(tmp_path, monkeypatch, period, value):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "config.toml"
    target.write_text(f"[budget]\n{period} = {value}\n", encoding="utf-8")
    monkeypatch.setattr("agentcost.budget.CONFIG_FILE", target)
    with patch("agentcost.cli._parse_all_logs") as parse:
        result = CliRunner().invoke(cli, ["budget", "check"])
    assert result.exit_code == 2
    assert "positive" in result.output
    assert period in result.output
    parse.assert_not_called()


@pytest.mark.parametrize("value", ["0", "-5", "nan", "inf"])
def test_alert_rejects_invalid_threshold(value):
    with patch("agentcost.cli._parse_all_logs") as parse:
        result = CliRunner().invoke(cli, ["alert", "--threshold", value])
    assert result.exit_code == 2
    assert "positive" in result.output
    parse.assert_not_called()


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly"])
def test_small_positive_thresholds(tmp_path, monkeypatch, period):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "config.toml"
    monkeypatch.setattr("agentcost.budget.CONFIG_FILE", target)
    monkeypatch.setattr("agentcost.budget.CONFIG_DIR", tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["budget", "set", f"--{period}", "1e-100"])
    assert result.exit_code == 0
    assert load_budget_config() == {period: 1e-100}
    with patch("agentcost.cli._parse_all_logs", return_value=[]):
        assert runner.invoke(cli, ["budget", "check"]).exit_code == 0
        assert runner.invoke(cli, ["alert", "--threshold", "1e-100"]).exit_code == 0


@pytest.mark.parametrize("project", [False, True])
def test_invalid_save_does_not_create_config(tmp_path, monkeypatch, project):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("agentcost.budget.CONFIG_DIR", tmp_path / "global")
    monkeypatch.setattr("agentcost.budget.CONFIG_FILE", tmp_path / "global/config.toml")
    with pytest.raises(click.BadParameter, match="weekly.*positive"):
        save_budget_config(daily=10, weekly=-1, project=project)
    assert list(tmp_path.iterdir()) == []


def test_check_validates_project_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "config.toml"
    target.write_text("[budget]\ndaily = 10.0\n", encoding="utf-8")
    (tmp_path / ".agentcost.toml").write_text("[budget]\ndaily = 0\n", encoding="utf-8")
    monkeypatch.setattr("agentcost.budget.CONFIG_FILE", target)
    with patch("agentcost.cli._parse_all_logs") as parse:
        result = CliRunner().invoke(cli, ["budget", "check", "--quiet"])
    assert result.exit_code == 2
    assert "daily budget" in result.output
    parse.assert_not_called()
