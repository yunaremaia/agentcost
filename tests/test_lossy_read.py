"""Files that are not UTF-8 or UTF-16 must not crash a scan (#185)."""

import json
import logging

from agentcost.cli import _parse_all_logs, _parse_file
from agentcost.cursor_parser import CursorParser


def _line(tokens, note=None):
    entry = {
        "model": "gpt-4o",
        "usage": {"input_tokens": tokens, "output_tokens": 50},
        "timestamp": "2026-10-03T12:00:00Z",
    }
    if note:
        entry["note"] = note
    return json.dumps(entry, ensure_ascii=False)


def _write_latin1(path):
    path.write_bytes((_line(101, "café") + "\n").encode("latin-1"))


def test_latin1_log_does_not_crash(tmp_path):
    path = tmp_path / "codex-session.jsonl"
    _write_latin1(path)
    assert len(_parse_file(path, agent="codex")) == 1


def test_latin1_log_in_directory_scan_does_not_abort(tmp_path):
    (tmp_path / "codex-a.jsonl").write_text(_line(100) + "\n")
    _write_latin1(tmp_path / "codex-b.jsonl")
    (tmp_path / "codex-c.jsonl").write_text(_line(102) + "\n")
    assert len(_parse_all_logs([tmp_path])) == 3


def test_latin1_log_warns_that_it_was_not_read_faithfully(tmp_path, caplog):
    path = tmp_path / "codex-session.jsonl"
    _write_latin1(path)
    with caplog.at_level(logging.WARNING):
        _parse_file(path, agent="codex")
    assert str(path) in caplog.text


def test_binary_log_does_not_crash_and_warns(tmp_path, caplog):
    path = tmp_path / "codex-session.jsonl"
    path.write_bytes(b"\x80\x81\x82\x83" * 50)
    with caplog.at_level(logging.WARNING):
        usages = _parse_file(path, agent="codex")
    assert usages == []
    assert str(path) in caplog.text


def test_binary_cursor_log_warns_that_it_was_not_read_faithfully(tmp_path, capsys):
    path = tmp_path / "cursor-session.jsonl"
    path.write_bytes(b"\x80\x81\x82\x83" * 50)
    assert CursorParser().parse(path) == []
    assert "not read faithfully" in capsys.readouterr().err.lower()
