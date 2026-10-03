# Contributing to agentcost

`agentcost` is a Python CLI that reads AI coding agent logs (Claude Code, Codex CLI, OpenCode, Hermes, Cursor) and reports token usage and cost. Contributions are welcome.

## Prerequisites

- Python 3.10 or newer (CI runs 3.10, 3.11, 3.12, 3.13)
- `git`
- Only two runtime dependencies: `click` and `rich`

## Setup

```bash
git clone https://github.com/yunaremaia/agentcost.git
cd agentcost
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The `dev` extra installs `pytest` and `pytest-cov`. The editable install puts the `agentcost` command on your `PATH`:

```bash
agentcost --version               # agentcost, version 0.3.0
```

## Run the tests

This is the exact command CI runs:

```bash
python -m pytest tests/ -v --cov=agentcost --cov-report=term-missing
```

A healthy run ends with `170 passed`. For a quick loop while iterating:

```bash
python -m pytest tests/ -q
```

Current coverage is 71%.

### One known flaky test

`tests/test_init_command.py::TestInitCommand::test_init_project` fails when
`TMPDIR` is a long path. The test asserts the string `.agentcost.toml` appears in
the CLI output, but Rich wraps that line at the terminal width and splits the
filename when the temporary directory path is long. On CI the path
(`/tmp/pytest-of-runner/pytest-N/...`) is short enough to fit, so CI is green
while a deep local `TMPDIR` is not.

Widen the console to run it locally:

```bash
COLUMNS=200 python -m pytest tests/ -q     # 170 passed
```

## Linting

There is no linter or formatter configured. `pyproject.toml` defines no `[tool.ruff]`,
`[tool.black]`, or equivalent, no linter is in the `dev` extra, and CI runs
`pytest` only. Match the surrounding code style; a linter can be added in its own PR.

## Project layout

```
src/agentcost/
  cli.py             Click command tree (entry point: agentcost = agentcost.cli:cli)
  cost.py            Token → cost math, built-in model pricing
  parsers.py         Log parsers for Claude Code, Codex, Hermes, OpenCode
  cursor_parser.py   Cursor log parser
  hermes_output.py   Hermes cron output parser + TOOL_CALL_OVERHEAD_TOKENS
  hermes_sqlite.py   Hermes agent state database reader
  discovery.py       Locates agent log files on the system
  budget.py          Budget config + threshold checks
  persistence.py     SQLite history for past runs
  report.py          Table / JSON / Markdown rendering
  sarif.py           SARIF 2.1.0 output for GitHub Code Scanning
tests/               One test file per module area
action.yml           Composite GitHub Action (see GITHUB_ACTION_USAGE.md)
```

The public API is re-exported from `src/agentcost/__init__.py`; add new public
names there and to `__all__`.

## Making a change

Branch from `main` using `<type>/<short-description>`:

```bash
git checkout -b fix/parser-cache-write-tokens
```

Types in use: `fix/`, `feat/`, `docs/`, `chore/`, `ci/`.

Commits follow Conventional Commits, with an optional scope:

```
fix: reject invalid budget and alert thresholds
feat(cli): add --quiet flag across commands for CI and automated environments
docs: document everyday usage commands
```

Prefer the imperative mood and keep the subject under ~72 characters. Reference
the issue in the body or subject (`fixes #123`).

Add tests alongside the change — the suite lives in `tests/` and is split by module,
so a change to `src/agentcost/parsers.py` belongs in `tests/test_parser_validation.py`
or a new `tests/test_<area>.py`. New log formats, new model pricing, and new CLI flags
all need coverage.

Update `CHANGELOG.md` under `## [Unreleased]` for user-visible changes. It follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

Do not edit `version` in `pyproject.toml` or `__version__` in `__init__.py` — the
maintainer bumps those when cutting a release. Publishing happens automatically when
a GitHub release is created (`.github/workflows/publish.yml`).

Never commit API keys, tokens, or private agent logs. See [SECURITY.md](SECURITY.md).

## Opening a pull request

```bash
git push -u origin fix/parser-cache-write-tokens
gh pr create --fill
```

PRs are checked against `.github/PULL_REQUEST_TEMPLATE.md`: describe the change,
link the issue (`Fixes #`), tick the change type, and state how you tested it.
CI runs the test matrix on 3.10–3.13 and must be green.

## Good first issues

46 open issues are labeled
[`good first issue`](https://github.com/yunaremaia/agentcost/labels/good%20first%20issue)
— that is the best place to start. Comment to claim one before you begin so two
people do not work the same issue.

Bugs use the [bug report template](https://github.com/yunaremaia/agentcost/issues/new?template=bug_report.md).
Never report a vulnerability in a public issue — follow [SECURITY.md](SECURITY.md).
