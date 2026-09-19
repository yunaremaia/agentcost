"""Parsers for various AI agent log formats."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from agentcost.cost import TokenUsage


class ClaudeCodeParser:
    """Parse Claude Code JSONL log format."""

    def parse(self, log_path: Path) -> List[TokenUsage]:
        """Parse a Claude Code JSONL file."""
        usages = []
        try:
            with open(log_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        usage = self._parse_entry(entry)
                        if usage:
                            usages.append(usage)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return usages

    def _parse_entry(self, entry: Dict[str, Any]) -> Optional[TokenUsage]:
        """Parse a single log entry."""
        message = entry.get("message", {})
        usage_data = message.get("usage", {})
        
        if not usage_data:
            return None
        
        # Extract model
        model = message.get("model", "unknown")
        if ":" in model:
            model = model.split(":")[-1]
        
        model = self._normalize_model(model)
        
        ts_str = entry.get("timestamp", "")
        timestamp = None
        if ts_str:
            try:
                timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        session_id = entry.get("sessionId", None) or entry.get("session_id")
        
        return TokenUsage(
            model=model,
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
            cache_write_tokens=usage_data.get("cache_creation_input_tokens", 0) or usage_data.get("cache_write_tokens", 0),
            timestamp=timestamp,
            agent_id="claude-code",
            session_id=session_id,
        )

    def _normalize_model(self, model: str) -> str:
        """Normalize model name to pricing key."""
        model = model.lower().replace("-", " ").replace(".", " ")
        if "sonnet" in model and ("3 5" in model or "3.5" in model):
            return "claude-3-5-sonnet"
        elif "opus" in model and "4" in model:
            return "claude-opus-4"
        elif "sonnet" in model and "4" in model:
            return "claude-sonnet-4"
        elif "opus" in model:
            return "claude-3-opus"
        elif "haiku" in model:
            return "claude-3-haiku"
        elif "claude 2" in model or "claude2" in model:
            return "claude-2.1"
        return model


class CodexParser:
    """Parse OpenAI Codex CLI log format."""

    def parse(self, log_path: Path) -> List[TokenUsage]:
        """Parse a Codex log file."""
        usages = []
        try:
            with open(log_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        usage = self._parse_entry(entry)
                        if usage:
                            usages.append(usage)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return usages

    def _parse_entry(self, entry: Dict[str, Any]) -> Optional[TokenUsage]:
        """Parse a single Codex log entry."""
        usage_data = entry.get("usage", {})
        if not usage_data:
            return None
        
        model = entry.get("model", "gpt-4o")
        if "gpt-4o-mini" in model:
            model = "gpt-4o-mini"
        elif "gpt-4" in model:
            model = "gpt-4o"
        
        ts_str = entry.get("timestamp", "")
        timestamp = None
        if ts_str:
            try:
                timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        return TokenUsage(
            model=model,
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
            cache_write_tokens=usage_data.get("cache_creation_input_tokens", 0) or usage_data.get("cache_write_tokens", 0),
            timestamp=timestamp,
            agent_id="codex-cli",
            session_id=entry.get("session_id"),
        )


class HermesParser:
    """Parse Hermes agent log format (JSONL from cron output)."""

    def parse(self, log_path: Path) -> List[TokenUsage]:
        """Parse a Hermes log file."""
        usages = []
        try:
            with open(log_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        usage = self._parse_entry(entry)
                        if usage:
                            usages.append(usage)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return usages

    def _parse_entry(self, entry: Dict[str, Any]) -> Optional[TokenUsage]:
        """Parse a single Hermes log entry."""
        # Hermes format: {"type":"message","role":"assistant","content":"...","timestamp":"...","model":"...","tokens":{...}}
        usage_data = entry.get("usage", entry.get("tokens", {}))
        if not usage_data:
            return None
        
        model = entry.get("model", "unknown")
        ts_str = entry.get("timestamp", "")
        timestamp = None
        if ts_str:
            try:
                timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        return TokenUsage(
            model=model,
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
            cache_write_tokens=usage_data.get("cache_creation_input_tokens", 0) or usage_data.get("cache_write_tokens", 0),
            timestamp=timestamp,
            agent_id="hermes-agent",
            session_id=entry.get("session_id"),
        )


class OpenCodeParser:
    """Parse OpenCode CLI log format."""

    def parse(self, log_path: Path) -> List[TokenUsage]:
        """Parse an OpenCode log file."""
        usages = []
        try:
            with open(log_path) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        usage = self._parse_entry(entry)
                        if usage:
                            usages.append(usage)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return usages

    def _parse_entry(self, entry: Dict[str, Any]) -> Optional[TokenUsage]:
        """Parse a single OpenCode log entry."""
        usage_data = entry.get("usage", {})
        if not usage_data:
            return None
        
        model = entry.get("model", "unknown")
        ts_str = entry.get("timestamp", "")
        timestamp = None
        if ts_str:
            try:
                timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        return TokenUsage(
            model=model,
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
            cache_write_tokens=usage_data.get("cache_creation_input_tokens", 0) or usage_data.get("cache_write_tokens", 0),
            timestamp=timestamp,
            agent_id="opencode-cli",
            session_id=entry.get("session_id"),
        )
