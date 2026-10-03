"""Alert and budget checks agree at the spending threshold."""

import datetime
import json

import pytest
from click.testing import CliRunner

from agentcost.cli import cli
from agentcost.parsers import CodexParser


@pytest.fixture
def exact_cost_log(tmp_path, monkeypatch):
    class FixedDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 3, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(datetime, "datetime", FixedDatetime)
    log = tmp_path / "usage.jsonl"
    log.write_text(json.dumps({
        "timestamp": "2026-10-03T10:00:00",
        "model": "gpt-4o",
        "usage": {"input_tokens": 1_000_000, "output_tokens": 0},
    }) + "\n", encoding="utf-8")
    return log


@pytest.mark.parametrize("command", ["alert", "budget"])
@pytest.mark.parametrize("threshold, expected_exit", [
    (2.49, 1),
    (2.50, 0),
    (2.51, 0),
])
@pytest.mark.parametrize("flags", [[], ["--quiet"], ["--sarif"], ["--sarif", "--quiet"]])
def test_threshold_boundaries(exact_cost_log, monkeypatch, command, threshold,
                              expected_exit, flags):
    """Exactly $2.50 of usage exceeds only the $2.49 threshold."""
    if command == "alert":
        args = ["alert", "-p", str(exact_cost_log), "--agent", "codex",
                "--threshold", str(threshold)]
    else:
        usages = CodexParser().parse(exact_cost_log)
        monkeypatch.setattr("agentcost.cli._parse_all_logs", lambda: usages)
        monkeypatch.setattr("agentcost.cli.load_budget_config", lambda: {"daily": threshold})
        args = ["budget", "check"]

    result = CliRunner().invoke(cli, args + flags)
    assert result.exit_code == expected_exit, result.output

    if "--sarif" in flags:
        findings = json.loads(result.output)["runs"][0]["results"]
        assert len(findings) == expected_exit
        if findings:
            assert findings[0]["ruleId"] == "agentcost/budget-daily"
    elif "--quiet" in flags:
        assert result.output == ""
    elif command == "alert":
        if expected_exit:
            assert "exceeds threshold" in result.output
        else:
            assert "Within budget: $2.50" in result.output
            assert "exceeds" not in result.output
            if threshold == 2.50:
                assert "Remaining: $0.000000" in result.output
    else:
        if expected_exit:
            assert "DAILY BUDGET EXCEEDED" in result.output
        else:
            assert "Daily: $2.5000" in result.output
            assert "EXCEEDED" not in result.output
