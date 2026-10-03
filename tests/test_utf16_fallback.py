"""Non-UTF-8 logs must not abort a scan (#182)."""

import json

import pytest

from agentcost.cli import _parse_all_logs, _parse_file

LINE = json.dumps({
    "model": "gpt-4o",
    "usage": {"input_tokens": 100, "output_tokens": 50},
    "timestamp": "2026-10-03T12:00:00Z",
})


def _write_utf16(path):
    path.write_bytes((LINE + "\n").encode("utf-16"))


@pytest.mark.parametrize("agent", ["claude", "codex", "opencode", "hermes"])
def test_utf16_log_does_not_raise(tmp_path, agent):
    path = tmp_path / "session.jsonl"
    _write_utf16(path)
    _parse_file(path, agent=agent)


def test_utf16_log_is_decoded_like_cursor(tmp_path):
    path = tmp_path / "codex-session.jsonl"
    _write_utf16(path)
    assert len(_parse_file(path)) == 1


def test_utf16_log_in_directory_scan_does_not_abort(tmp_path):
    (tmp_path / "codex-a.jsonl").write_text(LINE + "\n")
    _write_utf16(tmp_path / "codex-b.jsonl")
    (tmp_path / "codex-c.jsonl").write_text(LINE + "\n")
    usages = _parse_all_logs([tmp_path])
    assert len(usages) >= 2
