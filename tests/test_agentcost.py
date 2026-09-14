"""Tests for agentcost."""

import pytest
from datetime import datetime
from pathlib import Path
import json
import tempfile

from agentcost.cost import TokenUsage, CostBreakdown, calculate_cost, summarize_usage, MODEL_PRICING
from agentcost.parsers import ClaudeCodeParser, CodexParser, HermesParser
from agentcost.discovery import LogDiscovery
from agentcost.report import ReportGenerator


class TestCostCalculation:
    """Calculate cost from token usage."""

    def test_calculate_cost_sonnet(self):
        usage = TokenUsage(
            model="claude-3-5-sonnet",
            input_tokens=10000,
            output_tokens=5000,
        )
        cost = calculate_cost(usage)
        expected = (10000/1e6 * 3.0) + (5000/1e6 * 15.0)
        assert abs(cost - expected) < 0.001

    def test_calculate_cost_with_cache(self):
        usage = TokenUsage(
            model="claude-3-5-sonnet",
            input_tokens=10000,
            output_tokens=5000,
            cache_read_tokens=8000,
            cache_write_tokens=2000,
        )
        cost = calculate_cost(usage)
        expected = (10000/1e6 * 3.0) + (5000/1e6 * 15.0) + (8000/1e6 * 0.3) + (2000/1e6 * 3.75)
        assert abs(cost - expected) < 0.001

    def test_calculate_cost_unknown_model(self):
        usage = TokenUsage(
            model="unknown-model-xyz",
            input_tokens=10000,
            output_tokens=5000,
        )
        cost = calculate_cost(usage)
        # Should use default pricing
        assert cost > 0

    def test_calculate_cost_grok2(self):
        usage = TokenUsage(model="grok-2", input_tokens=10000, output_tokens=5000)
        cost = calculate_cost(usage)
        expected = (10000 / 1e6 * 2.0) + (5000 / 1e6 * 10.0)
        assert abs(cost - expected) < 0.001

    def test_calculate_cost_qwen_max(self):
        usage = TokenUsage(model="qwen-max", input_tokens=10000, output_tokens=5000)
        cost = calculate_cost(usage)
        expected = (10000 / 1e6 * 2.0) + (5000 / 1e6 * 6.0)
        assert abs(cost - expected) < 0.001

    def test_calculate_cost_kimi_latest(self):
        usage = TokenUsage(model="kimi-latest", input_tokens=10000, output_tokens=5000)
        cost = calculate_cost(usage)
        expected = (10000 / 1e6 * 0.21) + (5000 / 1e6 * 2.52)
        assert abs(cost - expected) < 0.001

    def test_calculate_cost_llama_31_405b(self):
        usage = TokenUsage(model="llama-3.1-405b", input_tokens=10000, output_tokens=5000)
        cost = calculate_cost(usage)
        expected = (10000 / 1e6 * 3.0) + (5000 / 1e6 * 15.0)
        assert abs(cost - expected) < 0.001

    def test_calculate_cost_claude_3_7_sonnet(self):
        usage = TokenUsage(model="claude-3-7-sonnet", input_tokens=10000, output_tokens=5000)
        cost = calculate_cost(usage)
        expected = (10000 / 1e6 * 3.0) + (5000 / 1e6 * 15.0)
        assert abs(cost - expected) < 0.001

    def test_calculate_cost_deepseek_r1(self):
        usage = TokenUsage(model="deepseek-r1", input_tokens=10000, output_tokens=5000)
        cost = calculate_cost(usage)
        expected = (10000 / 1e6 * 0.55) + (5000 / 1e6 * 2.19)
        assert abs(cost - expected) < 0.001

    def test_summarize_usage(self):
        usages = [
            TokenUsage("claude-3-5-sonnet", 1000, 500),
            TokenUsage("claude-3-5-sonnet", 2000, 1000),
            TokenUsage("gpt-4o", 500, 250),
        ]
        summary = summarize_usage(usages)
        assert summary.calls == 3
        assert summary.total_input == 3500
        assert summary.total_output == 1750
        assert summary.total_tokens == 5250
        assert summary.total_cost_usd > 0


class TestClaudeCodeParser:
    """Parse Claude Code JSONL logs."""

    def test_parse_basic_jsonl(self, tmp_path):
        """Parse a basic Claude Code JSONL file."""
        log_file = tmp_path / "session.jsonl"
        log_file.write_text(
            '{"type":"assistant","message":{"model":"claude-3-5-sonnet-20241022","usage":{"input_tokens":1000,"output_tokens":500}},"timestamp":"2026-09-11T10:00:00"}\n'
        )
        parser = ClaudeCodeParser()
        usages = parser.parse(log_file)
        assert len(usages) == 1
        assert usages[0].input_tokens == 1000
        assert usages[0].output_tokens == 500
        assert "sonnet" in usages[0].model

    def test_parse_multiple_entries(self, tmp_path):
        """Parse multiple JSONL entries."""
        log_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({"type":"assistant","message":{"model":"claude-3-5-sonnet","usage":{"input_tokens":100,"output_tokens":50}}}),
            json.dumps({"type":"assistant","message":{"model":"claude-3-opus","usage":{"input_tokens":200,"output_tokens":100}}}),
        ]
        log_file.write_text("\n".join(lines))
        parser = ClaudeCodeParser()
        usages = parser.parse(log_file)
        assert len(usages) == 2

    def test_parse_skips_invalid_lines(self, tmp_path):
        """Skip invalid JSON lines gracefully."""
        log_file = tmp_path / "session.jsonl"
        log_file.write_text(
            '{"type":"assistant","message":{"model":"claude-3-5-sonnet","usage":{"input_tokens":100,"output_tokens":50}}}\n'
            'this is not json\n'
            '{"type":"assistant","message":{"model":"claude-3-5-sonnet","usage":{"input_tokens":200,"output_tokens":100}}}\n'
        )
        parser = ClaudeCodeParser()
        usages = parser.parse(log_file)
        assert len(usages) == 2

    def test_parse_empty_file(self, tmp_path):
        """Handle empty log file."""
        log_file = tmp_path / "empty.jsonl"
        log_file.write_text("")
        parser = ClaudeCodeParser()
        usages = parser.parse(log_file)
        assert len(usages) == 0


class TestCodexParser:
    """Parse Codex CLI logs."""

    def test_parse_codex_jsonl(self, tmp_path):
        log_file = tmp_path / "codex.jsonl"
        log_file.write_text(
            json.dumps({"model":"gpt-4o","usage":{"input_tokens":500,"output_tokens":200},"timestamp":"2026-09-11T10:00:00"}) + "\n"
        )
        parser = CodexParser()
        usages = parser.parse(log_file)
        assert len(usages) == 1
        assert usages[0].input_tokens == 500


class TestLogDiscovery:
    """Discover agent log files."""

    def test_discover_finds_paths(self):
        discovery = LogDiscovery()
        assert len(discovery.paths) > 0

    def test_discover_nonexistent_path(self):
        discovery = LogDiscovery(additional_paths=["/nonexistent/path/xyz"])
        # Should not raise
        logs = discovery.discover()
        assert isinstance(logs, dict)


class TestReportGenerator:
    """Generate cost reports."""

    def test_daily_summary(self):
        now = datetime.now()
        usages = [
            TokenUsage("claude-3-5-sonnet", 1000, 500, timestamp=now),
            TokenUsage("claude-3-5-sonnet", 2000, 1000, timestamp=now),
        ]
        gen = ReportGenerator()
        report = gen.daily_summary(usages, now)
        assert report["total_calls"] == 2
        assert report["total_tokens"] == 4500

    def test_monthly_summary(self):
        now = datetime.now()
        usages = [
            TokenUsage("claude-3-5-sonnet", 5000, 2000, timestamp=now),
        ]
        gen = ReportGenerator()
        report = gen.monthly_summary(usages, now)
        assert report["total_calls"] == 1
        assert report["total_tokens"] == 7000

    def test_projection(self):
        now = datetime.now()
        usages = [
            TokenUsage("claude-3-5-sonnet", 10000, 5000, timestamp=now),
        ]
        gen = ReportGenerator()
        projection = gen.projection(usages)
        assert projection["projected_monthly_usd"] > 0
        assert "daily_average_usd" in projection

    def test_empty_usages(self):
        gen = ReportGenerator()
        report = gen.daily_summary([])
        assert report["total_calls"] == 0
        assert report["total_tokens"] == 0


class TestTokenUsage:
    """TokenUsage dataclass."""

    def test_total_tokens(self):
        usage = TokenUsage(
            model="claude-3-5-sonnet",
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=200,
            cache_write_tokens=100,
        )
        assert usage.total_tokens == 1800
