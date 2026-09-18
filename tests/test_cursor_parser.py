"""Tests for Cursor AI agent parser."""

import json
import pytest
from pathlib import Path
import tempfile
from types import SimpleNamespace

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

    def test_missing_file_warns_and_returns_empty(self, capsys, tmp_path):
        """A missing log file warns on stderr and yields no usages (#83)."""
        parser = CursorParser()
        result = parser.parse(tmp_path / "definitely-missing-cursor.jsonl")
        assert result == []
        assert "not found" in capsys.readouterr().err

    def test_missing_file_strict_raises(self, tmp_path):
        """With strict=True a missing log file raises instead of warning (#83)."""
        parser = CursorParser()
        with pytest.raises(FileNotFoundError):
            parser.parse(tmp_path / "definitely-missing-cursor.jsonl", strict=True)

    def test_oversized_file_skipped_with_warning(self, tmp_path, monkeypatch, capsys):
        """Files above 100MB are skipped with a warning (#83)."""
        parser = CursorParser()
        log = tmp_path / "huge.jsonl"
        log.write_text("{}", encoding="utf-8")

        real_stat = Path.stat

        def fake_stat(self):
            if self == log:
                return SimpleNamespace(st_size=150 * 1024 * 1024)
            return real_stat(self)

        monkeypatch.setattr(Path, "stat", fake_stat)
        result = parser.parse(log)
        assert result == []
        assert "exceeds 100MB" in capsys.readouterr().err

    def test_utf16_log_parsed(self, tmp_path):
        """UTF-16 encoded logs are read via the encoding fallback (#83)."""
        parser = CursorParser()
        entry = {"message": {"usage": {"input_tokens": 1000, "output_tokens": 500}}}
        log = tmp_path / "cursor_utf16.jsonl"
        log.write_text(json.dumps(entry) + "\n", encoding="utf-16")
        result = parser.parse(log)
        assert len(result) == 1
        assert result[0].input_tokens == 1000

    def test_binary_garbage_returns_empty_without_crash(self, tmp_path):
        """Undecodable binary garbage yields no usages and does not crash (#83)."""
        parser = CursorParser()
        log = tmp_path / "cursor_binary.jsonl"
        log.write_bytes(b"\xd8\x41\x00\xdc\x80\xff\x81\x82\x83")
        result = parser.parse(log)
        assert result == []
