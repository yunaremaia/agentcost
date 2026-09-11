"""CLI for agentcost — token usage tracker."""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agentcost.cost import TokenUsage, CostBreakdown, calculate_cost, summarize_usage
from agentcost.parsers import ClaudeCodeParser, CodexParser, HermesParser
from agentcost.discovery import LogDiscovery
from agentcost.report import ReportGenerator

console = Console()


@click.group()
@click.version_option(package_name="agentcost")
def cli():
    """agentcost — token usage tracker for multi-agent AI sessions."""
    pass


@cli.command()
@click.option("--path", "-p", "log_paths", multiple=True, type=click.Path(exists=True, path_type=Path),
              help="Log file paths (default: auto-discover)")
@click.option("--format", "-f", "output_format", default="cli",
              type=click.Choice(["cli", "json", "markdown"]))
def discover(log_paths: tuple, output_format: str):
    """Discover and parse agent log files."""
    discovery = LogDiscovery()
    all_logs = {p: [] for p in log_paths} if log_paths else {}
    
    if not log_paths:
        logs = discovery.discover()
        all_logs = {k: v for k, v in logs.items() if v}
    
    if not all_logs:
        console.print("[yellow]No log files found.[/yellow]")
        return
    
    # Parse logs
    all_usages = []
    for path in all_logs if isinstance(all_logs, dict) else []:
        if isinstance(path, Path):
            if "claude" in str(path).lower():
                parser = ClaudeCodeParser()
            elif "codex" in str(path).lower():
                parser = CodexParser()
            else:
                parser = HermesParser()
            all_usages.extend(parser.parse(path))
    
    if output_format == "json":
        _output_json(all_usages)
    elif output_format == "markdown":
        _output_markdown(all_usages)
    else:
        _output_cli(all_usages)


@cli.command()
@click.argument("log_path", type=click.Path(exists=True, path_type=Path))
@click.option("--agent", "-a", default="claude", type=click.Choice(["claude", "codex", "hermes"]))
@click.option("--period", "-p", default="daily", type=click.Choice(["daily", "weekly", "monthly", "all"]))
@click.option("--format", "-f", "output_format", default="cli",
              type=click.Choice(["cli", "json", "markdown"]))
def analyze(log_path: Path, agent: str, period: str, output_format: str):
    """Analyze a specific log file."""
    if agent == "claude":
        parser = ClaudeCodeParser()
    elif agent == "codex":
        parser = CodexParser()
    else:
        parser = HermesParser()
    
    usages = parser.parse(log_path)
    if not usages:
        console.print("[yellow]No usage data found in log file.[/yellow]")
        return
    
    gen = ReportGenerator()
    if period == "daily":
        report = gen.daily_summary(usages)
    elif period == "weekly":
        report = gen.weekly_summary(usages)
    elif period == "monthly":
        report = gen.monthly_summary(usages)
    else:
        report = gen._build_summary(usages, "All Time")
    
    if output_format == "json":
        click.echo(json.dumps(report, indent=2, default=str))
    elif output_format == "markdown":
        _output_markdown_report(report)
    else:
        _output_report_cli(report, period)


@cli.command()
def project():
    """Project monthly cost based on recent usage."""
    console.print("[yellow]Projection requires log data. Run 'analyze' first.[/yellow]")


def _output_cli(usages: list):
    """Rich CLI output."""
    if not usages:
        console.print("[yellow]No usage data.[/yellow]")
        return
    
    breakdown = summarize_usage(usages)
    console.print(Panel(
        f"[bold]agentcost v0.1.0[/bold] — {breakdown.calls} calls\n"
        f"Total tokens: [cyan]{breakdown.total_tokens:,}[/cyan]\n"
        f"Input: [green]{breakdown.total_input:,}[/green] | "
        f"Output: [yellow]{breakdown.total_output:,}[/yellow]\n"
        f"Cache Read: [dim]{breakdown.total_cache_read:,}[/dim] | "
        f"Cache Write: [dim]{breakdown.total_cache_write:,}[/dim]\n"
        f"Total cost: [bold]${breakdown.total_cost_usd:.4f}[/bold]",
        title="Usage Summary"
    ))


def _output_json(usages: list):
    """JSON output."""
    click.echo(json.dumps([{
        "model": u.model,
        "input": u.input_tokens,
        "output": u.output_tokens,
        "cache_read": u.cache_read_tokens,
        "cache_write": u.cache_write_tokens,
        "cost": calculate_cost(u),
    } for u in usages], indent=2))


def _output_markdown(usages: list):
    """Markdown table output."""
    breakdown = summarize_usage(usages)
    click.echo("# Agent Cost Report\n")
    click.echo(f"- **Total Calls**: {breakdown.calls}")
    click.echo(f"- **Total Tokens**: {breakdown.total_tokens:,}")
    click.echo(f"- **Total Cost**: ${breakdown.total_cost_usd:.4f}\n")
    click.echo("| Model | Calls | Tokens | Cost |")
    click.echo("|-------|-------|--------|------|")


def _output_report_cli(report: dict, period: str):
    """Rich report output."""
    console.print(Panel(
        f"[bold]agentcost[/bold] — {report['period']}\n"
        f"Calls: [cyan]{report['total_calls']}[/cyan] | "
        f"Tokens: [cyan]{report['total_tokens']:,}[/cyan]\n"
        f"Input: [green]{report['input_tokens']:,}[/green] | "
        f"Output: [yellow]{report['output_tokens']:,}[/yellow]\n"
        f"Cache Read: [dim]{report['cache_read_tokens']:,}[/dim] | "
        f"Cache Write: [dim]{report['cache_write_tokens']:,}[/dim]\n"
        f"Total cost: [bold]${report['total_cost_usd']:.4f}[/bold]",
        title=f"Cost Report ({period})"
    ))


def _output_markdown_report(report: dict):
    """Markdown report output."""
    click.echo(f"# Cost Report — {report['period']}\n")
    click.echo(f"- **Total Calls**: {report['total_calls']}")
    click.echo(f"- **Total Tokens**: {report['total_tokens']:,}")
    click.echo(f"- **Total Cost**: ${report['total_cost_usd']:.4f}\n")
    click.echo("| Model | Calls | Tokens | Cost |")
    click.echo("|-------|-------|--------|------|")
    for model, data in report.get("by_model", {}).items():
        click.echo(f"| {model} | {data['calls']} | {data['tokens']:,} | ${data['cost_usd']:.4f} |")


if __name__ == "__main__":
    cli()
