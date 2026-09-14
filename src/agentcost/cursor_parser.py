"""Parser for Cursor AI coding agent logs."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from agentcost.cost import TokenUsage


class CursorParser:
    """Parse Cursor AI coding agent JSONL log format.
    
    Cursor stores session logs in:
    - ~/.cursor/sessions/ (global)
    - .cursor/sessions/ (project-local)
    
    Format: JSONL with entries containing message, usage, model, timestamp.
    """

    def parse(self, log_path: Path) -> List[TokenUsage]:
        """Parse a Cursor JSONL log file."""
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
