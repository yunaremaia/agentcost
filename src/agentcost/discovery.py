"""Log discovery for AI agent sessions."""

from pathlib import Path
from typing import List, Dict


# Default paths where agent logs are stored
DEFAULT_PATHS = [
    "~/.claude/projects",
    "~/.codex/sessions",
    "~/.opencode/sessions",
    "~/.hermes/logs",
    "~/.hermes/cron/output",
]


class LogDiscovery:
    """Discover AI agent log files."""

    def __init__(self, additional_paths: List[str] = None):
        """Initialize with optional additional paths."""
        self.paths = [Path(p).expanduser() for p in DEFAULT_PATHS]
        if additional_paths:
            self.paths.extend([Path(p).expanduser() for p in additional_paths])

    def discover(self) -> Dict[str, List[Path]]:
        """Discover all log files by agent type."""
        logs: Dict[str, List[Path]] = {
            "claude": [],
            "codex": [],
            "opencode": [],
            "hermes": [],
        }
        
        for base_path in self.paths:
            if not base_path.exists():
                continue
            base_name = base_path.name.lower()
            
            if "claude" in base_name:
                logs["claude"].extend(self._find_jsonl(base_path))
            elif "codex" in base_name:
                logs["codex"].extend(self._find_jsonl(base_path))
            elif "opencode" in base_name:
                logs["opencode"].extend(self._find_jsonl(base_path))
            elif "hermes" in base_name:
                logs["hermes"].extend(self._find_logs(base_path))
        
        return logs

    def _find_jsonl(self, base_path: Path) -> List[Path]:
        """Find all JSONL files in a directory recursively."""
        jsonl_files = []
        for path in base_path.rglob("*.jsonl"):
            jsonl_files.append(path)
        for path in base_path.rglob("*.json"):
            jsonl_files.append(path)
        return jsonl_files

    def _find_logs(self, base_path: Path) -> List[Path]:
        """Find all log files in a directory recursively."""
        log_files = []
        for ext in ["*.jsonl", "*.json", "*.log"]:
            for path in base_path.rglob(ext):
                log_files.append(path)
        return log_files
