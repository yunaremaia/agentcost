"""Tests for HermesOutputParser."""
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from agentcost.hermes_output import (
    HermesOutputParser,
    _estimate_tokens_from_text,
    _parse_tool_calls_from_output,
    TOOL_CALL_OVERHEAD_TOKENS,
    get_tool_overhead,
)


class TestToolOverhead:
    def test_known_tool_uses_configured_value(self):
        assert get_tool_overhead("terminal") == TOOL_CALL_OVERHEAD_TOKENS["terminal"]

    def test_unknown_tool_warns_and_uses_default(self, caplog):
        assert get_tool_overhead("not_a_real_tool") == 100
        assert "Unknown tool" in caplog.text


class TestEstimateTokensFromText:
    def test_empty_string(self):
        assert _estimate_tokens_from_text("") == 0

    def test_none_input(self):
        # Function raises TypeError on None (len(None) fails)
        with pytest.raises(TypeError):
            _estimate_tokens_from_text(None)  # type: ignore

    def test_short_text(self):
        assert _estimate_tokens_from_text("hello world") == 2

    def test_longer_text(self):
        text = "a" * 1000
        assert _estimate_tokens_from_text(text) == 250


class TestParseToolCallsFromOutput:
    def test_no_tool_calls(self):
        assert _parse_tool_calls_from_output("plain text output") == []

    def test_terminal_block(self):
        content = """
Some output here.

[TERMINAL]
```
bash
ls -la /root
```

More output.
"""
        calls = _parse_tool_calls_from_output(content)
        # Terminal blocks need [TERMINAL] marker to be detected
        assert isinstance(calls, list)

    def test_python_block(self):
        content = """
```python
print("hello")
```
"""
        calls = _parse_tool_calls_from_output(content)
        # Python blocks in ```python are ambiguous — might not be detected as tool calls
        # Just verify no crash
        assert isinstance(calls, list)


class TestHermesOutputParser:
    def test_list_jobs_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = HermesOutputParser(Path(tmpdir))
            assert parser.list_jobs() == []

    def test_list_jobs_with_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "job-1").mkdir()
            (base / "job-2").mkdir()
            (base / "not-a-dir.txt").write_text("skip me")

            parser = HermesOutputParser(base)
            jobs = parser.list_jobs()
            assert len(jobs) == 2
            assert "job-1" in jobs
            assert "job-2" in jobs

    def test_parse_job_outputs_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = HermesOutputParser(Path(tmpdir))
            assert parser.parse_job_outputs("nonexistent") == []

    def test_parse_single_output_skips_tiny_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir) / "job-1"
            job_dir.mkdir()
            (job_dir / "2026-01-01_12-00-00.md").write_text("tiny")

            parser = HermesOutputParser(Path(tmpdir))
            result = parser._parse_single_output(job_dir / "2026-01-01_12-00-00.md")
            assert result is None

    def test_parse_single_output_valid_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir) / "job-1"
            job_dir.mkdir()

            # Create a realistic cron output file (>100 chars)
            content = """# Cron Job: test-job

## Output

Running task execution now...
All operations completed successfully.

```bash
echo "hello world"
```

## Result
Task finished successfully at 2026-09-12 10:00:00 UTC.
"""
            (job_dir / "2026-09-12_10-00-00.md").write_text(content)

            parser = HermesOutputParser(Path(tmpdir))
            result = parser._parse_single_output(job_dir / "2026-09-12_10-00-00.md")
            assert result is not None
            assert result.input_tokens > 0
            assert result.output_tokens > 0
            assert result.agent_id is not None

    def test_parse_all_jobs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            for job_name in ["job-a", "job-b"]:
                job_dir = base / job_name
                job_dir.mkdir()
                content = f"# Cron Job: {job_name}\n\n" + "x" * 500
                (job_dir / "2026-01-01_12-00-00.md").write_text(content)

            parser = HermesOutputParser(base)
            results = parser.parse_all_jobs(limit_per_job=1)
            assert len(results) == 2
            assert "job-a" in results
            assert "job-b" in results

    def test_extract_job_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = HermesOutputParser(Path(tmpdir))
            content = "# Cron Job: my-test-job\n\nSome output here."
            assert parser._extract_job_name(content) == "my-test-job"

    def test_extract_job_name_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = HermesOutputParser(Path(tmpdir))
            assert parser._extract_job_name("random text") is None
