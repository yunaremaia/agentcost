"""Tests for Cursor AI agent parser."""

import json
import pytest
from pathlib import Path
import tempfile

from agentcost.cursor_parser import CursorParser
from agentcost.cost import TokenUsage


class TestCursorParser:
    """Test Cursor JSONL log parsing."""

    def test_empty_log(self):
        """Parse empty file returns empty list."""
        parser = CursorParser()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('')
            f.flush()
            result = parser.parse(Path(f.name))
        assert result == []

    def test_valid_log_with_usage(self):
        """Parse valid Cursor JSONL with usage data."""
        parser = CursorParser()
        entries = [
            json.dumps({
                "timestamp": "2026-09-14T10:30:00Z",
                "model": "claude-3-5-sonnet",
                "message": {
                    "role": "assistant",
                    "content": "Refactored the code",
                    "usage": {
                        "input_tokens": 5000,
                        "output_tokens": 2000,
                        "cache_read_input_tokens": 1000,
                        "cache_creation_input_tokens": 500,
                    }
                },
                "sessionId": "sess-123",
            }),
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('\n'.join(entries))
            f.flush()
            result = parser.parse(Path(f.name))
        assert len(result) == 1
        assert result[0].model == "claude-3-5-sonnet"
        assert result[0].input_tokens == 5000
        assert result[0].output_tokens == 2000
        assert result[0].cache_read_tokens == 1000
        assert result[0].cache_write_tokens == 500
        assert result[0].agent_id == "cursor-agent"

    def test_malformed_jsonl_lines(self):
        """Malformed JSONL lines are skipped."""
        parser = CursorParser()
        lines = [
            '{"timestamp": "2026-09-14T10:30:00Z", "model": "claude-3-5-sonnet", "message": {"role": "assistant", "usage": {"input_tokens": 1000, "output_tokens": 500}}}',
            'not json at all',
            '',
            '{"timestamp": "2026-09-14T10:31:00Z", "model": "gpt-4o", "message": {"role": "assistant", "usage": {"input_tokens": 2000, "output_tokens": 800}}}',
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('\n'.join(lines))
            f.flush()
            result = parser.parse(Path(f.name))
        assert len(result) == 2

    def test_model_with_provider_prefix(self):
        """Model name with provider prefix is normalized."""
        parser = CursorParser()
        entry = json.dumps({
            "model": "anthropic/claude-3-5-sonnet",
            "message": {"usage": {"input_tokens": 1000, "output_tokens": 500}}
        })
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(entry)
            f.flush()
            result = parser.parse(Path(f.name))
        assert result[0].model == "claude-3-5-sonnet"

    def test_top_level_message(self):
        """Cursor can have message as top-level or wrapped."""
        parser = CursorParser()
        entry = json.dumps({
            "timestamp": "2026-09-14T10:30:00Z",
            "message": {
                "model": "claude-sonnet-4",
                "usage": {"input_tokens": 3000, "output_tokens": 1500}
            }
        })
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(entry)
            f.flush()
            result = parser.parse(Path(f.name))
        assert len(result) == 1
        assert result[0].model == "claude-sonnet-4"

    def test_entry_without_usage(self):
        """Entries without usage are skipped."""
        parser = CursorParser()
        entry = json.dumps({
            "timestamp": "2026-09-14T10:30:00Z",
            "message": {"role": "user", "content": "Hello"}
        })
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(entry)
            f.flush()
            result = parser.parse(Path(f.name))
        assert result == []
