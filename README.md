# agentcost

**Token usage tracker for multi-agent AI sessions.**

`agentcost` analyzes logs from AI coding agents (Claude Code, Codex CLI, OpenCode, Hermes) and calculates the real cost in tokens and USD. See how much each agent, session, and project costs — with monthly projections.

## Install

```bash
pip install agentcost
```

## Usage

### Discover logs automatically

```bash
agentcost discover
```

### Analyze a log file

```bash
agentcost analyze ~/.claude/projects/my-session.jsonl --agent claude --period daily
```

### Output formats

```bash
agentcost analyze session.jsonl --format json
agentcost analyze session.jsonl --format markdown
```

### Example output

```
╭──────────────────────────────────────────────────────────────╮
│ agentcost v0.1.0 — 42 calls                                  │
│ Total tokens: 156,230                                        │
│ Input: 98,400 | Output: 57,830                              │
│ Cache Read: 12,000 | Cache Write: 3,000                      │
│ Total cost: $0.8234                                          │
╰──────────────────────────────────────────────────────────────╯
```

## Features

- **Multi-agent**: Claude Code, Codex CLI, OpenCode, Hermes
- **Zero config**: Discovers logs automatically
- **Rich output**: CLI tables, JSON, Markdown
- **Cost-aware**: Cache read pricing (Anthropic: 90% discount)
- **Projections**: Monthly cost estimates based on recent usage

## Supported log formats

| Agent       | Log format          | Status |
|-------------|---------------------|--------|
| Claude Code | JSONL               | ✅     |
| Codex CLI   | JSONL               | ✅     |
| OpenCode    | JSONL               | ✅     |
| Hermes      | JSON/JSONL          | ✅     |

## Model pricing

Built-in pricing for Claude 3.x, GPT-4o, Gemini 1.5. Auto-fallback for unknown models.

## License

MIT
