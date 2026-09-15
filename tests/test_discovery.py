from pathlib import Path

from click.testing import CliRunner

from agentcost.cli import cli
from agentcost.discovery import LogDiscovery


def test_cursor_discovery_from_explicit_path(tmp_path: Path) -> None:
    cursor_dir = tmp_path / ".cursor" / "sessions"
    cursor_dir.mkdir(parents=True)
    session = cursor_dir / "session.jsonl"
    session.write_text("{}\n")

    logs = LogDiscovery([str(cursor_dir)]).discover()

    assert logs["cursor"] == [session]


def test_discover_accepts_cursor_filter(tmp_path: Path) -> None:
    cursor_dir = tmp_path / "cursor"
    cursor_dir.mkdir()
    session = cursor_dir / "session.jsonl"
    session.write_text("{}\n")

    result = CliRunner().invoke(cli, ["discover", "--path", str(cursor_dir), "--agent", "cursor", "--quiet"])

    assert result.exit_code == 0
    assert result.output.strip() == str(session)
