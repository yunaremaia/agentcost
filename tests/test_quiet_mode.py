"""Tests for --quiet / -q flag across all commands."""

import json
from datetime import datetime
from pathlib import Path
from click.testing import CliRunner
import pytest

from agentcost.cli import cli


@pytest.fixture
def sample_claude_log(tmp_path: Path) -> Path:
    """Create a sample claude jsonl log with current timestamp."""
    log_dir = tmp_path / "claude_logs"
    log_dir.mkdir()
    log_file = log_dir / "claude_session.jsonl"
    entry = {
        "type": "assistant",
        "timestamp": datetime.now().isoformat(),
        "message": {
            "model": "claude-3-5-sonnet",
            "usage": {"input_tokens": 1000, "output_tokens": 500},
        },
    }
    log_file.write_text(json.dumps(entry) + "\n")
    return log_file


def test_discover_quiet(sample_claude_log: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["discover", "-p", str(sample_claude_log.parent), "--quiet"])
    assert result.exit_code == 0
    # Should only contain paths, no rich headers
    lines = [line.strip() for line in result.output.splitlines() if line.strip()]
    assert "Hermes SQLite database" not in result.output
    assert "Found log files" not in result.output
    assert str(sample_claude_log) in lines


def test_today_quiet(sample_claude_log: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["today", "-p", str(sample_claude_log), "--quiet"])
    assert result.exit_code == 0
    # Output should be valid JSON and have no rich borders/panels
    assert "agentcost — Today" not in result.output
    data = json.loads(result.output)
    assert "calls" in data
    assert "total_tokens" in data
    assert "total_cost_usd" in data


def test_today_quiet_and_json_output(sample_claude_log: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["today", "-p", str(sample_claude_log), "--json-output", "-q"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["calls"] == 1
    assert data["total_tokens"] == 1500


def test_week_quiet(sample_claude_log: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["week", "-p", str(sample_claude_log), "--days", "7", "-q"])
    assert result.exit_code == 0
    assert "agentcost — 7 Days" not in result.output
    data = json.loads(result.output)
    assert len(data) > 0


def test_alert_quiet_under_threshold(sample_claude_log: Path):
    runner = CliRunner()
    # High threshold => exit 0, no output in quiet mode
    result = runner.invoke(cli, ["alert", "-p", str(sample_claude_log), "--threshold", "100.0", "-q"])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_alert_quiet_over_threshold(sample_claude_log: Path):
    runner = CliRunner()
    # Threshold 0 => exit 1, no alert banner in quiet mode
    result = runner.invoke(cli, ["alert", "-p", str(sample_claude_log), "--threshold", "0.0", "-q"])
    assert result.exit_code == 1
    assert "ALERT: Today's spending" not in result.output


def test_cron_quiet():
    runner = CliRunner()
    result = runner.invoke(cli, ["cron", "-q"])
    assert result.exit_code == 0
    assert "No cron outputs found" not in result.output


def test_analyze_quiet(sample_claude_log: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(sample_claude_log), "--agent", "claude", "-q"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "total_cost" in data or "calls" in data or "by_model" in data


def test_compare_quiet(sample_claude_log: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["compare", "-p", str(sample_claude_log), "-q"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0
