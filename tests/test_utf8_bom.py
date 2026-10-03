"""A UTF-8 BOM must not silently cost the first entry of a log.

Python's ``utf-8`` codec keeps a leading byte-order mark as the character
U+FEFF, while ``utf-16``/``utf-8-sig`` strip it. The reader opened every log
with plain ``utf-8``, so for a BOM-prefixed file the first line reached
``json.loads`` as ``'\\ufeff{"message": ...'`` and raised ``JSONDecodeError`` --
an exception every parser swallows with ``continue``. The first entry of the
session therefore vanished with no warning and no diagnostic at all, and a
log holding a single entry reported zero usages while claiming to be read
faithfully.

That is the #185 failure mode reached through a third door: the file *is*
valid UTF-8, so the lossy-read fallback never fires, and nothing in the
read path tells the caller that an entry was dropped. The BOM is how tools
on Windows (PowerShell ``Out-File``, many editors, some exporters) emit
UTF-8, so this is ordinary input, not a corrupt file.
"""

import json
import logging

import pytest

from agentcost.cli import _parse_all_logs, _parse_file
from agentcost.cursor_parser import CursorParser
from agentcost.parsers import (
    ClaudeCodeParser,
    CodexParser,
    HermesParser,
    OpenCodeParser,
)

CLAUDE_LINE = json.dumps({
    "message": {
        "model": "claude-sonnet-4",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    },
    "sessionId": "s1",
    "timestamp": "2026-10-03T12:00:00Z",
})

CODEX_LINE = json.dumps({
    "model": "gpt-4o",
    "usage": {"input_tokens": 100, "output_tokens": 50},
    "timestamp": "2026-10-03T12:00:00Z",
})

ALL_PARSERS = [
    pytest.param(ClaudeCodeParser(), CLAUDE_LINE, id="claude"),
    pytest.param(CodexParser(), CODEX_LINE, id="codex"),
    pytest.param(HermesParser(), CODEX_LINE, id="hermes"),
    pytest.param(OpenCodeParser(), CODEX_LINE, id="opencode"),
    pytest.param(CursorParser(), CLAUDE_LINE, id="cursor"),
]


def _with_utf8_bom(text):
    """The exact bytes ``PowerShell Out-File``/most Windows editors write."""
    return "\ufeff" + text


@pytest.mark.parametrize("parser,line", ALL_PARSERS)
def test_utf8_bom_log_keeps_its_first_entry(tmp_path, parser, line):
    """Every entry survives a leading BOM, not just all but the first."""
    path = tmp_path / "session.jsonl"
    path.write_bytes(_with_utf8_bom((line + "\n") * 3).encode("utf-8"))

    usages = parser.parse(path)

    assert len(usages) == 3, "the BOM-prefixed first entry was dropped"


@pytest.mark.parametrize("parser,line", ALL_PARSERS)
def test_utf8_bom_single_entry_log_is_not_silently_empty(tmp_path, parser, line):
    """A one-entry BOM log reported zero usages -- and claimed to be faithful.

    This is the discriminating case: it is indistinguishable from "no
    activity today" in every command output, so the cost simply vanishes.
    """
    path = tmp_path / "session.jsonl"
    path.write_bytes(_with_utf8_bom(line + "\n").encode("utf-8"))

    usages = parser.parse(path)

    assert len(usages) == 1, "a one-entry UTF-8 BOM log reported zero usages"


@pytest.mark.parametrize("parser,line", ALL_PARSERS)
def test_utf8_bom_log_is_read_faithfully_without_warning(
    tmp_path, parser, line, caplog, capsys
):
    """The BOM is not damage, so stripping it must stay quiet.

    A fix that merely warned about the BOM would pass the two tests above
    while still charging the user a spurious "not read faithfully" on every
    Windows-written log.
    """
    path = tmp_path / "session.jsonl"
    path.write_bytes(_with_utf8_bom((line + "\n") * 2).encode("utf-8"))

    with caplog.at_level(logging.WARNING):
        usages = parser.parse(path)

    assert len(usages) == 2
    assert caplog.records == [], f"unexpected warning: {caplog.records}"
    assert capsys.readouterr().err == ""


def test_bomless_utf8_log_is_unchanged(tmp_path):
    """Control: utf-8-sig must not disturb a file that has no BOM."""
    path = tmp_path / "codex-session.jsonl"
    path.write_bytes(((CODEX_LINE + "\n") * 2).encode("utf-8"))

    assert len(_parse_file(path)) == 2


def test_utf8_bom_log_is_counted_through_the_discovery_path(tmp_path):
    """A BOM must not lose an entry when logs are found by scanning."""
    path = tmp_path / "codex-session.jsonl"
    path.write_bytes(_with_utf8_bom((CODEX_LINE + "\n") * 4).encode("utf-8"))

    assert len(_parse_file(path)) == 4


def test_utf8_bom_log_does_not_hide_other_logs_in_a_directory_scan(tmp_path):
    """One BOM-prefixed log must not zero out its neighbours."""
    (tmp_path / "codex-a.jsonl").write_text(CODEX_LINE + "\n", encoding="utf-8")
    (tmp_path / "codex-b.jsonl").write_bytes(
        _with_utf8_bom((CODEX_LINE + "\n") * 3).encode("utf-8")
    )
    (tmp_path / "codex-c.jsonl").write_text(CODEX_LINE + "\n", encoding="utf-8")

    assert len(_parse_all_logs([tmp_path])) == 5


def test_utf8_bom_log_does_not_abort_a_directory_scan(tmp_path):
    """Regression guard for the crash the lossy fallback was added to prevent."""
    (tmp_path / "codex-a.jsonl").write_bytes(
        _with_utf8_bom(CODEX_LINE + "\n").encode("utf-8")
    )
    (tmp_path / "codex-b.jsonl").write_bytes(b"\x80\x81\x82\x83" * 50)

    assert len(_parse_all_logs([tmp_path])) == 1


def test_cursor_parser_strict_does_not_raise_on_a_utf8_bom_log(tmp_path):
    """A BOM is valid UTF-8, so ``strict=True`` must treat it as faithful."""
    path = tmp_path / "cursor-session.jsonl"
    path.write_bytes(_with_utf8_bom((CLAUDE_LINE + "\n") * 2).encode("utf-8"))

    assert len(CursorParser().parse(path, strict=True)) == 2