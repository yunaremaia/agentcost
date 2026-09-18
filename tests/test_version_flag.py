"""Tests for agentcost --version / -v."""

from click.testing import CliRunner

from agentcost import __version__
from agentcost.cli import cli


def test_version_long_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_short_v():
    runner = CliRunner()
    result = runner.invoke(cli, ["-v"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_short_V():
    runner = CliRunner()
    result = runner.invoke(cli, ["-V"])
    assert result.exit_code == 0
    assert __version__ in result.output
