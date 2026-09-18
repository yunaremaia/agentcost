"""Parser for Cursor AI coding agent logs."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from agentcost.cost import TokenUsage

# Files above this size are skipped with a warning instead of being read (#83).
_MAX_LOG_BYTES = 100 * 1024 * 1024
# Cursor writes UTF-8 logs; UTF-16 and latin-1 are fallbacks for odd exports.
_ENCODINGS = ("utf-8", "utf-16", "latin-1")


class CursorParser:
    """Parse Cursor AI coding agent JSONL log format.
    
    Cursor stores session logs in:
    - ~/.cursor/sessions/ (global)
    - .cursor/sessions/ (project-local)
    
    Format: JSONL with entries containing message, usage, model, timestamp.
    """

    def parse(self, log_path: Path, *, strict: bool = False) -> List[TokenUsage]:
        """Parse a Cursor JSONL log file.

        Failures never abort a scan by default: each failed file prints a
        warning to stderr and contributes no usages, so one unreadable log
        cannot mask the rest (#83). With ``strict=True`` the same failures
        raise instead, letting callers exit non-zero.
        """
        try:
            if log_path.stat().st_size > _MAX_LOG_BYTES:
                print(f"Warning: {log_path} exceeds 100MB, skipping", file=sys.stderr)
                return []

            lines: List[str] = []
            for encoding in _ENCODINGS:
                try:
                    with open(log_path, encoding=encoding) as f:
                        lines = f.readlines()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                print(f"Warning: Could not decode {log_path}", file=sys.stderr)
                if strict:
                    raise ValueError(f"Could not decode {log_path}")
                return []

            usages = []
            for line in lines:
                try:
                    entry = json.loads(line.strip())
                    usage = self._parse_entry(entry)
                    if usage:
                        usages.append(usage)
                except json.JSONDecodeError:
                    continue
            return usages
        except FileNotFoundError:
            print(f"Warning: {log_path} not found", file=sys.stderr)
            if strict:
                raise
            return []
        except ValueError as e:
            print(f"Warning: Failed to parse {log_path}: {e}", file=sys.stderr)
            if strict:
                raise
            return []

    def _parse_entry(self, entry: Dict[str, Any]) -> Optional[TokenUsage]:
        """Parse a single Cursor log entry."""
        # Cursor wraps the message in a "message" key
        message = entry.get("message", entry)
        usage_data = message.get("usage", {})
        
        if not usage_data:
            return None
        
        # Extract model name
        model = message.get("model", entry.get("model", "unknown"))
        if ":" in model:
            model = model.split(":")[-1].strip()
        model = self._normalize_model(model)
        
        # Parse timestamp
        ts_str = entry.get("timestamp", "")
        timestamp = None
        if ts_str:
            try:
                timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        session_id = entry.get("sessionId") or entry.get("session_id")
        
        return TokenUsage(
            model=model,
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
            cache_write_tokens=usage_data.get("cache_creation_input_tokens", 0),
            timestamp=timestamp,
            agent_id="cursor-agent",
            session_id=session_id,
        )

    def _normalize_model(self, model: str) -> str:
        """Normalize model name to pricing key."""
        model = model.lower().replace("-", " ").replace(".", " ")
        if "sonnet" in model:
            if "3 5" in model or "3.5" in model:
                return "claude-3-5-sonnet"
            elif "4" in model:
                return "claude-sonnet-4"
            return "claude-3-5-sonnet"
        elif "opus" in model:
            if "4" in model:
                return "claude-opus-4"
            return "claude-3-opus"
        elif "haiku" in model:
            return "claude-3-haiku"
        elif "gpt 4o mini" in model or "gpt-4o-mini" in model:
            return "gpt-4o-mini"
        elif "gpt 4o" in model or "gpt-4o" in model:
            return "gpt-4o"
        elif "gpt 4" in model:
            return "gpt-4"
        elif "gemini" in model:
            if "2.5" in model or "2 5" in model:
                return "gemini-2.5-pro"
            return "gemini-2.0-flash"
        elif "deepseek" in model:
            return "deepseek-v3"
        return model
