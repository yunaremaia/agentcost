"""Parsers must report a log they could not read faithfully (#185).

A log that cannot be decoded cleanly must still contribute whatever usages can
be recovered, but it must say so. Silently returning zero usages is the defect
these tests pin down.
"""

import json
import logging
import struct

import pytest

from agentcost.cli import _parse_file
from agentcost.cursor_parser import CursorParser
from agentcost.parsers import (
    ClaudeCodeParser,
    CodexParser,
    HermesParser,
    OpenCodeParser,
)

CODEX_LINE = json.dumps({
    "model": "gpt-4o",
    "usage": {"input_tokens": 100, "output_tokens": 50},
    "timestamp": "2026-10-03T12:00:00Z",
})

CLAUDE_LINE = json.dumps({
    "message": {
        "model": "claude-sonnet-4",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    "sessionId": "s1",
    "timestamp": "2026-10-03T12:00:00Z",
})

CURSOR_LINE = json.dumps({
    "message": {
        "model": "claude-sonnet-4",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    "timestamp": "2026-10-03T12:00:00Z",
})

ALL_PARSERS = [
    pytest.param(ClaudeCodeParser(), CLAUDE_LINE, id="claude"),
    pytest.param(CodexParser(), CODEX_LINE, id="codex"),
    pytest.param(HermesParser(), CODEX_LINE, id="hermes"),
    pytest.param(OpenCodeParser(), CODEX_LINE, id="opencode"),
    pytest.param(CursorParser(), CURSOR_LINE, id="cursor"),
]


def _binary_payload():
    """256 distinct byte values, repeated: decodable by latin-1, not JSON."""
    return bytes(range(256)) * 4


def _binary_utf16_payload():
    """Binary bytes that decode without error as utf-16-be.

    A two-byte sniff used to call anything starting ``\\x00`` UTF-16, so this
    file "decoded" successfully and was reported as a faithful read while
    contributing zero usages. Nothing warned.
    """
    return struct.pack(">4H", 0x0041, 0x0042, 0x0000, 0x0043) * 8


@pytest.mark.parametrize("parser,line", ALL_PARSERS)
def test_latin1_log_warns_but_still_counts_usages(tmp_path, parser, line, caplog, capsys):
    """A non-UTF-8 log keeps its usages and gains a warning, not a silent drop."""
    # "café" makes the payload genuinely undecodable as UTF-8, in a field no
    # parser reads, so the usage itself must survive the fallback.
    payload = json.loads(line)
    payload["note"] = "café"
    path = tmp_path / "session.jsonl"
    # ensure_ascii=False, or json escapes "é" to ASCII and UTF-8 succeeds.
    path.write_bytes(
        (json.dumps(payload, ensure_ascii=False) + "\n").encode("latin-1")
    )

    with caplog.at_level(logging.WARNING):
        usages = parser.parse(path)

    assert len(usages) == 1, "latin-1 log lost its usages"
    diagnostics = [r.getMessage() for r in caplog.records] + [capsys.readouterr().err]
    assert any("not valid UTF-8" in d for d in diagnostics), (
        "latin-1 fallback was not reported"
    )


@pytest.mark.parametrize("parser,line", ALL_PARSERS)
def test_binary_log_warns_instead_of_failing_silently(tmp_path, parser, line, caplog, capsys):
    """latin-1 decodes every byte, so binary logs must be reported (#185)."""
    path = tmp_path / "session.jsonl"
    path.write_bytes(_binary_payload())

    with caplog.at_level(logging.WARNING):
        usages = parser.parse(path)

    assert usages == []
    diagnostics = [r.getMessage() for r in caplog.records] + [capsys.readouterr().err]
    assert any("not text" in d for d in diagnostics), (
        "binary log produced no diagnostic; it vanished silently"
    )


@pytest.mark.parametrize("parser,line", ALL_PARSERS)
def test_utf8_log_is_not_warned_about(tmp_path, parser, line, caplog, capsys):
    """The faithful path stays quiet -- no warning noise for normal logs."""
    path = tmp_path / "session.jsonl"
    path.write_text(line + "\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        assert len(parser.parse(path)) == 1

    assert caplog.records == [] and "not text" not in capsys.readouterr().err


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
def test_bomless_utf16_log_is_counted(tmp_path, encoding):
    """utf-16 without a BOM must not fall through to a successful utf-8 read."""
    path = tmp_path / "codex-session.jsonl"
    path.write_bytes((CODEX_LINE + "\n").encode(encoding))

    assert len(_parse_file(path)) == 1, f"{encoding} without BOM decoded to mojibake"


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be"])
def test_every_utf16_variant_is_counted(tmp_path, encoding):
    path = tmp_path / "codex-session.jsonl"
    path.write_bytes((CODEX_LINE + "\n").encode(encoding))

    assert len(_parse_file(path)) == 1


def test_strict_cursor_parser_raises_on_binary_log(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_bytes(_binary_payload())

    with pytest.raises(ValueError):
        CursorParser().parse(path, strict=True)


@pytest.mark.parametrize("parser,line", ALL_PARSERS)
def test_binary_that_decodes_as_utf16_is_not_called_faithful(
    tmp_path, parser, line, caplog, capsys
):
    """Bytes that decode as UTF-16 but are not text must still be reported.

    A two-byte sniff accepts any file starting ``\\x00``, so this payload used
    to decode without error, be marked faithful, and yield zero usages in
    complete silence.
    """
    path = tmp_path / "session.jsonl"
    path.write_bytes(_binary_utf16_payload())

    with caplog.at_level(logging.WARNING):
        usages = parser.parse(path)

    assert usages == []
    diagnostics = [r.getMessage() for r in caplog.records] + [capsys.readouterr().err]
    assert any("not text" in d for d in diagnostics), (
        "binary log decoded as UTF-16 was reported as a faithful read"
    )


def test_strict_cursor_parser_raises_on_binary_decoding_as_utf16(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_bytes(_binary_utf16_payload())

    with pytest.raises(ValueError):
        CursorParser().parse(path, strict=True)
