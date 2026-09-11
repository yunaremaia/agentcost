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
        # Claude Code format: {"type":"assistant","message":{"usage":{...}}}
        message = entry.get("message", {})
        usage_data = message.get("usage", {})
        
        if not usage_data:
            return None
        
        # Extract model
        model = message.get("model", "unknown")
        if ":" in model:
            # Handle "anthropic:claude-3-5-sonnet-20241022" format
            model = model.split(":")[-1]
        
        # Normalize model name
        model = self._normalize_model(model)
        
        return TokenUsage(
            model=model,
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
            cache_write_tokens=usage_data.get("cache_creation_input_tokens", 0),
            timestamp=datetime.fromisoformat(entry.get("timestamp")) if entry.get("timestamp") else None,
            agent_id=entry.get("sessionId", None),
            session_id=entry.get("sessionId", None),
        )

    def _normalize_model(self, model: str) -> str:
        """Normalize model name to pricing key."""
        model = model.lower().replace("-", " ")
        if "sonnet" in model:
            return "claude-3-5-sonnet"
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
        
        return TokenUsage(
            model=model,
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
            cache_write_tokens=0,
            timestamp=datetime.fromisoformat(entry.get("timestamp")) if entry.get("timestamp") else None,
            session_id=entry.get("session_id"),
        )


class HermesParser:
    """Parse Hermes agent log format."""

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
        usage_data = entry.get("usage", {})
        if not usage_data:
            return None
        
        return TokenUsage(
            model=entry.get("model", "unknown"),
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
            cache_write_tokens=0,
            timestamp=datetime.fromisoformat(entry.get("timestamp")) if entry.get("timestamp") else None,
            session_id=entry.get("session_id"),
        )
