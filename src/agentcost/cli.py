"""CLI for agentcost — token usage tracker."""

import json
import sys
from pathlib import Path
from typing import Optional, List

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agentcost.cost import TokenUsage, CostBreakdown, calculate_cost, summarize_usage
from agentcost.parsers import ClaudeCodeParser, CodexParser, HermesParser, OpenCodeParser
from agentcost.hermes_sqlite import HermesSQLiteParser
from agentcost.discovery import LogDiscovery
from agentcost.report import ReportGenerator

console = Console()


def _format_tokens(n: int) -> str:
    """Format token count with k/M suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def _format_currency(n: float) -> str:
    """Format USD amount."""
    if n < 0.01:
        return f"${n:.6f}"
    elif n < 1.0:
        return f"${n:.4f}"
    elif n < 100:
        return f"${n:.2f}"
    else:
        return f"${n:,.2f}"


def _parse_all_logs(log_paths: Optional[List[Path]] = None) -> List[TokenUsage]:
    """Parse all logs from given paths or auto-discover."""
    all_usages = []
    
    if log_paths:
        for path in log_paths:
            if path.is_file():
                all_usages.extend(_parse_file(path))
            elif path.is_dir():
                for subpath in path.rglob("*"):
                    if subpath.is_file() and subpath.suffix in (".jsonl", ".json", ".log"):
                        all_usages.extend(_parse_file(subpath))
    else:
        # First, try SQLite database (Hermes agent)
        sqlite_parser = HermesSQLiteParser()
        all_usages.extend(sqlite_parser.parse())
        
        # Then discover other logs
        discovery = LogDiscovery()
        logs = discovery.discover()
        for agent_type, paths in logs.items():
            parser = _get_parser(agent_type)
            for path in paths:
                all_usages.extend(parser.parse(path))
    
    return all_usages


def _parse_file(path: Path) -> List[TokenUsage]:
    """Parse a single file, choosing parser by path."""
    path_lower = str(path).lower()
    if "claude" in path_lower:
        parser = ClaudeCodeParser()
    elif "codex" in path_lower:
        parser = CodexParser()
    elif "opencode" in path_lower:
        parser = OpenCodeParser()
    else:
        parser = HermesParser()
    return parser.parse(path)


def _get_parser(agent_type: str):
    """Get parser by agent type string."""
    agent_type = agent_type.lower()
    if "claude" in agent_type:
        return ClaudeCodeParser()
    elif "codex" in agent_type:
        return CodexParser()
    elif "opencode" in agent_type:
        return OpenCodeParser()
    else:
        return HermesParser()


@click.group()
@click.version_option(package_name="agentcost")
def cli():
    """agentcost — token usage tracker for multi-agent AI sessions."""
    pass


@cli.command()
@click.option("--path", "-p", "log_paths", multiple=True, type=click.Path(path_type=Path),
              help="Log file paths or directories")
@click.option("--agent", "-a", default=None, type=click.Choice(["claude", "codex", "opencode", "hermes"]),
              help="Filter by agent")
def discover(log_paths, agent):
    """Discover agent log files on this system."""
    if log_paths:
        discovery = LogDiscovery([str(p) for p in log_paths])
    else:
        discovery = LogDiscovery()
    
    logs = discovery.discover()
    
    if agent:
        logs = {k: v for k, v in logs.items() if agent in k.lower()}
    
    if not any(logs.values()):
        console.print("[yellow]No log files found.[/yellow]")
        return
    
    console.print("\n[bold green]Found log files:[/bold green]\n")
    for agent_type, paths in sorted(logs.items()):
        if paths:
            console.print(f"  [cyan]{agent_type}[/cyan]: {len(paths)} files")
    
    console.print("\nRun 'agentcost today' to see usage summary.")


@cli.command()
@click.option("--path", "-p", "log_paths", multiple=True, type=click.Path(path_type=Path),
              help="Custom log paths")
@click.option("--json-output", "json_out", is_flag=True, help="Output as JSON")
def today(log_paths, json_out):
    """Show today's token usage."""
    usages = _parse_all_logs(list(log_paths) if log_paths else None)
    
    # Filter to today
    from datetime import datetime, timedelta
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    usages = [u for u in usages if u.timestamp and u.timestamp >= today_start]
    
    if not usages:
        console.print("[yellow]No agent activity found today.[/yellow]")
        return
    
    breakdown = summarize_usage(usages)
    
    if json_out:
        _output_json_breakdown(breakdown)
        return
    
    console.print(Panel(
        f"[bold]Today[/bold]\n"
        f"Calls: [cyan]{breakdown.calls}[/cyan] | "
        f"Tokens: [cyan]{_format_tokens(breakdown.total_tokens)}[/cyan] | "
        f"Cost: [bold]{_format_currency(breakdown.total_cost_usd)}[/bold]",
        title="agentcost — Today"
    ))
    
    # Model breakdown
    if usages:
        table = Table(title="By Model")
        table.add_column("Model")
        table.add_column("Calls", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Cost", justify="right")
        
        by_model = {}
        for u in usages:
            if u.model not in by_model:
                by_model[u.model] = {"calls": 0, "tokens": 0, "cost": 0}
            by_model[u.model]["calls"] += 1
            by_model[u.model]["tokens"] += u.total_tokens
            by_model[u.model]["cost"] += calculate_cost(u)
        
        for model, data in sorted(by_model.items(), key=lambda x: x[1]["cost"], reverse=True):
            table.add_row(model, str(data["calls"]), _format_tokens(data["tokens"]), _format_currency(data["cost"]))
        
        console.print(table)


@cli.command()
@click.option("--days", "-d", default=7, help="Number of days")
@click.option("--path", "-p", "log_paths", multiple=True, type=click.Path(path_type=Path),
              help="Custom log paths")
@click.option("--json-output", "json_out", is_flag=True, help="Output as JSON")
def week(days, log_paths, json_out):
    """Show usage for the last N days."""
    from datetime import datetime, timedelta
    
    usages = _parse_all_logs(list(log_paths) if log_paths else None)
    cutoff = datetime.now() - timedelta(days=days)
    usages = [u for u in usages if u.timestamp and u.timestamp >= cutoff]
    
    if not usages:
        console.print(f"[yellow]No agent activity found in the last {days} days.[/yellow]")
        return
    
    # Group by day
    by_day = {}
    for u in usages:
        day_key = u.timestamp.strftime("%Y-%m-%d")
        if day_key not in by_day:
            by_day[day_key] = []
        by_day[day_key].append(u)
    
    if json_out:
        output = {}
        for day, day_usages in sorted(by_day.items()):
            bd = summarize_usage(day_usages)
            output[day] = {
                "calls": bd.calls,
                "tokens": bd.total_tokens,
                "cost_usd": round(bd.total_cost_usd, 4),
            }
        click.echo(json.dumps(output, indent=2))
        return
    
    breakdown = summarize_usage(usages)
    
    console.print(Panel(
        f"[bold]Last {days} Days[/bold]\n"
        f"Calls: [cyan]{breakdown.calls}[/cyan] | "
        f"Tokens: [cyan]{_format_tokens(breakdown.total_tokens)}[/cyan] | "
        f"Cost: [bold]{_format_currency(breakdown.total_cost_usd)}[/bold]",
        title=f"agentcost — {days} Days"
    ))
    
    table = Table(title="Daily Breakdown")
    table.add_column("Date")
    table.add_column("Calls", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right")
    
    for day in sorted(by_day.keys(), reverse=True):
        bd = summarize_usage(by_day[day])
        table.add_row(day, str(bd.calls), _format_tokens(bd.total_tokens), _format_currency(bd.total_cost_usd))
    
    table.add_row("[bold]Total[/bold]", f"[bold]{breakdown.calls}[/bold]", 
                  f"[bold]{_format_tokens(breakdown.total_tokens)}[/bold]",
                  f"[bold]{_format_currency(breakdown.total_cost_usd)}[/bold]")
    
    console.print(table)
    
    # Projection
    if breakdown.calls > 0:
        daily_avg = breakdown.total_cost_usd / days
        monthly_proj = daily_avg * 30
        console.print(Panel(
            f"Daily avg: {_format_currency(daily_avg)}  |  Monthly projection: {_format_currency(monthly_proj)}",
            title="Projection"
        ))


@cli.command()
@click.option("--path", "-p", "log_paths", multiple=True, type=click.Path(path_type=Path),
              help="Custom log paths")
@click.option("--threshold", "-t", default=5.0, type=float, help="Alert threshold in USD")
def alert(log_paths, threshold):
    """Check if spending exceeds threshold today."""
    from datetime import datetime
    
    usages = _parse_all_logs(list(log_paths) if log_paths else None)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    usages = [u for u in usages if u.timestamp and u.timestamp >= today_start]
    
    total_cost = sum(calculate_cost(u) for u in usages)
    
    if total_cost >= threshold:
        console.print(f"[bold red]ALERT: Today's spending {_format_currency(total_cost)} exceeds threshold {_format_currency(threshold)}[/bold red]")
        sys.exit(1)
    else:
        remaining = threshold - total_cost
        console.print(f"[green]Within budget: {_format_currency(total_cost)} / {_format_currency(threshold)}[/green]")
        console.print(f"[dim]Remaining: {_format_currency(remaining)}[/dim]")
        sys.exit(0)


@cli.command()
@click.argument("log_path", required=False, type=click.Path(path_type=Path))
@click.option("--agent", "-a", default=None, help="Agent type (claude, codex, opencode, hermes)")
@click.option("--period", "-p", default="daily", type=click.Choice(["daily", "weekly", "monthly", "all"]))
@click.option("--format", "-f", "output_format", default="cli", type=click.Choice(["cli", "json", "markdown"]))
def analyze(log_path, agent, period, output_format):
    """Analyze a specific log file or all discovered logs."""
    if log_path:
        if agent == "claude":
            parser = ClaudeCodeParser()
        elif agent == "codex":
            parser = CodexParser()
        elif agent == "opencode":
            parser = OpenCodeParser()
        else:
            parser = HermesParser()
        
        usages = parser.parse(log_path)
    else:
        usages = _parse_all_logs()
    
    if not usages:
        console.print("[yellow]No usage data found.[/yellow]")
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


def _output_json_breakdown(breakdown):
    """Output as JSON."""
    output = {
        "calls": breakdown.calls,
        "total_tokens": breakdown.total_tokens,
        "input_tokens": breakdown.total_input,
        "output_tokens": breakdown.total_output,
        "cache_read_tokens": breakdown.total_cache_read,
        "cache_write_tokens": breakdown.total_cache_write,
        "total_cost_usd": round(breakdown.total_cost_usd, 4),
    }
    click.echo(json.dumps(output, indent=2))


def _output_report_cli(report, period):
    """Rich report output."""
    console.print(Panel(
        f"[bold]{report['period']}[/bold]\n"
        f"Calls: [cyan]{report['total_calls']}[/cyan] | "
        f"Tokens: [cyan]{_format_tokens(report['total_tokens'])}[/cyan]\n"
        f"Input: [green]{report['input_tokens']:,}[/green] | "
        f"Output: [yellow]{report['output_tokens']:,}[/yellow]\n"
        f"Cache Read: [dim]{report['cache_read_tokens']:,}[/dim] | "
        f"Cache Write: [dim]{report['cache_write_tokens']:,}[/dim]\n"
        f"Total cost: [bold]{_format_currency(report['total_cost_usd'])}[/bold]",
        title=f"Cost Report ({period})"
    ))


def _output_markdown_report(report):
    """Markdown report output."""
    click.echo(f"# Cost Report — {report['period']}\n")
    click.echo(f"- **Total Calls**: {report['total_calls']}")
    click.echo(f"- **Total Tokens**: {report['total_tokens']:,}")
    click.echo(f"- **Total Cost**: {_format_currency(report['total_cost_usd'])}\n")
    click.echo("| Model | Calls | Tokens | Cost |")
    click.echo("|-------|-------|--------|------|")
    for model, data in report.get("by_model", {}).items():
        click.echo(f"| {model} | {data['calls']} | {data['tokens']:,} | {_format_currency(data['cost_usd'])} |")


if __name__ == "__main__":
    cli()
