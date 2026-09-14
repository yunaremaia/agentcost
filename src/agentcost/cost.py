"""Token cost tracker for AI agent sessions."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import json


@dataclass
class TokenUsage:
    """Token usage for a single model call."""
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    timestamp: Optional[datetime] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens


@dataclass
class CostBreakdown:
    """Cost breakdown for a session or period."""
    total_input: int = 0
    total_output: int = 0
    total_cache_read: int = 0
    total_cache_write: int = 0
    total_cost_usd: float = 0.0
    calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.total_input + self.total_output + self.total_cache_read + self.total_cache_write


# Model pricing per 1M tokens (USD)
MODEL_PRICING = {
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
    "claude-3-opus": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75},
    "claude-3-haiku": {"input": 0.25, "output": 1.25, "cache_read": 0.03, "cache_write": 0.3},
    "claude-2.1": {"input": 8.0, "output": 24.0, "cache_read": 0.8, "cache_write": 10.0},
    "gpt-4o": {"input": 2.5, "output": 10.0, "cache_read": 1.25, "cache_write": 5.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6, "cache_read": 0.075, "cache_write": 0.3},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5, "cache_read": 0.25, "cache_write": 0.75},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0, "cache_read": 0.31, "cache_write": 1.25},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.3, "cache_read": 0.019, "cache_write": 0.075},
    "claude-opus-4": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.0, "cache_read": 0.31, "cache_write": 1.25},
    "gemini-2.0-flash": {"input": 0.075, "output": 0.3, "cache_read": 0.019, "cache_write": 0.075},
    "deepseek-v3": {"input": 0.27, "output": 1.1, "cache_read": 0.07, "cache_write": 0.27},
    "deepseek-r1": {"input": 0.55, "output": 2.19, "cache_read": 0.14, "cache_write": 0.55},
    "grok-2": {"input": 2.0, "output": 10.0, "cache_read": 0.5, "cache_write": 2.5},
    "grok-2-vision": {"input": 2.0, "output": 10.0, "cache_read": 0.5, "cache_write": 2.5},
    "qwen-max": {"input": 2.0, "output": 6.0, "cache_read": 0.5, "cache_write": 1.5},
    "qwen-plus": {"input": 0.8, "output": 2.0, "cache_read": 0.2, "cache_write": 0.5},
    "kimi-latest": {"input": 0.21, "output": 2.52, "cache_read": 0.05, "cache_write": 0.21},
    "llama-3.1-405b": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.0},
    "llama-3.1-70b": {"input": 0.9, "output": 0.9, "cache_read": 0.09, "cache_write": 0.09},
    "llama-3.1-8b": {"input": 0.18, "output": 0.18, "cache_read": 0.02, "cache_write": 0.02},
    "claude-3-7-sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
}


def calculate_cost(usage: TokenUsage) -> float:
    """Calculate cost in USD for a token usage entry."""
    pricing = MODEL_PRICING.get(usage.model)
    if not pricing:
        # Default pricing for unknown models
        pricing = {"input": 1.0, "output": 3.0, "cache_read": 0.1, "cache_write": 1.25}
    
    cost = (
        (usage.input_tokens / 1_000_000) * pricing["input"] +
        (usage.output_tokens / 1_000_000) * pricing["output"] +
        (usage.cache_read_tokens / 1_000_000) * pricing["cache_read"] +
        (usage.cache_write_tokens / 1_000_000) * pricing["cache_write"]
    )
    return cost


def summarize_usage(usages: List[TokenUsage]) -> CostBreakdown:
    """Summarize a list of token usages."""
    breakdown = CostBreakdown()
    for u in usages:
        breakdown.total_input += u.input_tokens
        breakdown.total_output += u.output_tokens
        breakdown.total_cache_read += u.cache_read_tokens
        breakdown.total_cache_write += u.cache_write_tokens
        breakdown.total_cost_usd += calculate_cost(u)
        breakdown.calls += 1
    return breakdown
