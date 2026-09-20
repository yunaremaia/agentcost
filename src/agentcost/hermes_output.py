"""Parser for Hermes cron output files (markdown files with prompt + tool calls).

Reads cron outputs from ~/.hermes/cron/output/<job_id>/ to estimate token usage
per cron task based on model pricing.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Iterator

from agentcost.cost import TokenUsage


# Approximate token counts for tool call overhead (prompt side)
# These are rough estimates based on observed patterns
TOOL_CALL_OVERHEAD_TOKENS = {
    "terminal": 150,
    "execute_code": 200,
    "delegate_task": 300,
    "browser_exec": 250,
    "patch": 100,
    "read_file": 80,
    "search_files": 100,
    "write_file": 120,
    "web_search": 50,
    "web_extract": 50,
    "tool_search": 50,
    "tool_call": 200,
    "memory": 60,
    "todo_list": 40,
    "cronjob_manage": 80,
    "vision_analyze": 400,
    "text_to_speech": 30,
    "clarify": 100,
    "browser_vault": 50,
}

DEFAULT_TOOL_OVERHEAD_TOKENS = 100
logger = logging.getLogger(__name__)


def get_tool_overhead(tool_name: str) -> int:
    """Return the estimated token overhead for a tool call."""
    if tool_name in TOOL_CALL_OVERHEAD_TOKENS:
        return TOOL_CALL_OVERHEAD_TOKENS[tool_name]

    logger.warning(
        "Unknown tool %r; using default overhead of %d tokens",
        tool_name,
        DEFAULT_TOOL_OVERHEAD_TOKENS,
    )
    return DEFAULT_TOOL_OVERHEAD_TOKENS


def _estimate_tokens_from_text(text: str) -> int:
    """Rough token estimation: ~4 chars per token for English/mixed text."""
    if text is None:
        raise TypeError("text must be a string, not None")
    if not text:
        return 0
    return len(text) // 4


def _parse_tool_calls_from_output(content: str) -> list[dict]:
    """Extract tool calls from Hermes output markdown.
    
    Looks for patterns like:
    ```json
    {"tool": "terminal", "arguments": {...}}
    ```
    or inline tool call markers.
    """
    calls = []
    
    # Pattern 1: JSON tool call blocks
    json_pattern = r'```json\s*\n(\{[^}]*"tool"[^}]*\})\s*\n```'
    for match in re.finditer(json_pattern, content, re.DOTALL):
        try:
            call = json.loads(match.group(1))
            calls.append(call)
        except json.JSONDecodeError:
            pass
    
    # Pattern 2: Tool call headers (terminal, execute_code, etc.)
    tool_header_pattern = r'\[?TERMINAL\]?\s*```(?:bash|sh)\s*(.+?)\s*```'
    for match in re.finditer(tool_header_pattern, content, re.DOTALL):
        calls.append({
            "tool": "terminal",
            "arguments": {"command": match.group(1)[:500]}  # truncate
        })
    
    # Pattern 2b: Bare ```bash blocks (without [TERMINAL] header)
    bare_bash_pattern = r'```\s*(?:bash|sh)\s*\n(.+?)\s*\n```'
    for match in re.finditer(bare_bash_pattern, content, re.DOTALL):
        calls.append({
            "tool": "terminal",
            "arguments": {"command": match.group(1)[:500]}
        })
    
    # Pattern 3: execute_code blocks
    exec_pattern = r'\[?EXEC\]?\s*\n```python\s*\n(.+?)\s*\n```'
    for match in re.finditer(exec_pattern, content, re.DOTALL):
        calls.append({
            "tool": "execute_code",
            "arguments": {"code": match.group(1)[:1000]}
        })
    
    return calls


class HermesOutputParser:
    """Parse Hermes cron output files to extract token usage estimates."""
    
    def __init__(self, cron_output_dir: Path = Path.home() / ".hermes" / "cron" / "output"):
        self.cron_output_dir = cron_output_dir
    
    def list_jobs(self) -> list[str]:
        """List all job IDs that have output files."""
        if not self.cron_output_dir.exists():
            return []
        try:
            return [d.name for d in self.cron_output_dir.iterdir() if d.is_dir()]
        except PermissionError:
            return []
    
    def parse_job_outputs(self, job_id: str, limit: int = 10) -> list[TokenUsage]:
        """Parse output files for a specific job, return TokenUsage estimates."""
        job_dir = self.cron_output_dir / job_id
        if not job_dir.exists():
            return []
        
        try:
            files = sorted(job_dir.glob("*.md"), reverse=True)[:limit]
        except PermissionError:
            return []
        results = []
        
        for f in files:
            usage = self._parse_single_output(f)
            if usage:
                results.append(usage)
        
        return results
    
    def _parse_single_output(self, filepath: Path) -> TokenUsage | None:
        """Parse a single cron output markdown file."""
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        
        if len(content) < 100:  # skip tiny/empty files
            return None
        
        # Extract timestamp from filename (format: YYYY-MM-DD_HH-MM-SS.md)
        filename = filepath.stem
        try:
            # Try to parse timestamp
            dt = datetime.strptime(filename, "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            dt = datetime.fromtimestamp(filepath.stat().st_mtime)
        
        # Estimate total content tokens
        total_content_tokens = _estimate_tokens_from_text(content)
        
        # Count tool calls
        tool_calls = _parse_tool_calls_from_output(content)
        tool_call_count = len(tool_calls)
        
        # Estimate tool call prompt overhead
        tool_prompt_tokens = 0
        tool_response_tokens = 0
        for call in tool_calls:
            tool_name = call.get("tool", "unknown")
            overhead = get_tool_overhead(tool_name)
            tool_prompt_tokens += overhead
            
            # Estimate response tokens from content
            args = call.get("arguments", {})
            if isinstance(args, dict):
                for v in args.values():
                    if isinstance(v, str):
                        tool_prompt_tokens += _estimate_tokens_from_text(v)
            
            # Tool responses are typically short (success/error/result)
            tool_response_tokens += 50
        
        # Estimate user prompt tokens (first ~20% of file is usually the prompt)
        prompt_tokens = _estimate_tokens_from_text(content[:len(content)//5])
        
        # Estimate assistant response tokens (remaining ~80%)
        completion_tokens = total_content_tokens - prompt_tokens + tool_response_tokens
        
        # Add tool call overhead to prompt
        prompt_tokens += tool_prompt_tokens
        
        # Rough ratios for cache hit (assume 40% for repetitive cron prompts)
        cache_read_tokens = int(prompt_tokens * 0.4)
        cache_write_tokens = int(prompt_tokens * 0.1)
        input_tokens = prompt_tokens - cache_read_tokens - cache_write_tokens
        
        # Extract job name from content (if present in header)
        job_name = self._extract_job_name(content) or filepath.parent.name
        
        return TokenUsage(
            model="meituan/longcat-2.0:free",
            input_tokens=input_tokens,
            output_tokens=completion_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            timestamp=dt,
            agent_id=job_name,
        )
    
    def _extract_job_name(self, content: str) -> str | None:
        """Extract job name from output content header."""
        # Pattern: "# Cron Job: job-name" or "Name: job-name"
        patterns = [
            r'# Cron Job:\s+(.+)',
            r'Name:\s+(.+)',
            r'Job Name:\s+(.+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content[:500])
            if match:
                return match.group(1).strip()
        return None
    
    def parse_all_jobs(self, limit_per_job: int = 5) -> dict[str, list[TokenUsage]]:
        """Parse outputs for all known jobs."""
        results = {}
        for job_id in self.list_jobs():
            usages = self.parse_job_outputs(job_id, limit=limit_per_job)
            if usages:
                results[job_id] = usages
        return results


def scan_cron_outputs(
    cron_output_dir: Path = Path.home() / ".hermes" / "cron" / "output",
    job_id: str | None = None,
    limit: int = 10,
) -> list[TokenUsage]:
    """Scan Hermes cron outputs and return token usage estimates.
    
    Args:
        cron_output_dir: Directory containing cron outputs
        job_id: Specific job to scan, or None for all
        limit: Max output files per job
    
    Returns:
        List of TokenUsage estimates
    """
    parser = HermesOutputParser(cron_output_dir)
    
    if job_id:
        return parser.parse_job_outputs(job_id, limit=limit)
    else:
        all_usages = []
        for jid in parser.list_jobs():
            all_usages.extend(parser.parse_job_outputs(jid, limit=limit))
        return all_usages
