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
from agentcost.budget import load_budget_config, save_budget_config
from agentcost.sarif import budget_to_sarif, sarif_to_string

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
    """Discover agent session data on this system."""
    # Check SQLite database first
    from agentcost.hermes_sqlite import HermesSQLiteParser
    sqlite_parser = HermesSQLiteParser()
    db_usages = sqlite_parser.parse()
    
    if log_paths:
        discovery = LogDiscovery([str(p) for p in log_paths])
    else:
        discovery = LogDiscovery()
    
    logs = discovery.discover()
    
    if agent:
        logs = {k: v for k, v in logs.items() if agent in k.lower()}
    
    if db_usages:
        console.print(f"\n[bold green]Hermes SQLite database:[/bold green] {len(db_usages)} usage records")
        date_range = sqlite_parser.get_date_range()
        if date_range[0] and date_range[1]:
            console.print(f"  Date range: {date_range[0].strftime('%Y-%m-%d')} to {date_range[1].strftime('%Y-%m-%d')}")
    
    if any(logs.values()):
        console.print("\n[bold green]Found log files:[/bold green]\n")
        for agent_type, paths in sorted(logs.items()):
            if paths:
                console.print(f"  [cyan]{agent_type}[/cyan]: {len(paths)} files")
    
    if not db_usages and not any(logs.values()):
        console.print("[yellow]No agent logs found.[/yellow]")
        return
    
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
@click.option("--sarif", "as_sarif", is_flag=True, help="Output SARIF 2.1.0 (for GitHub Code Scanning)")
def alert(log_paths, threshold, as_sarif):
    """Check if spending exceeds threshold today."""
    from datetime import datetime
    
    usages = _parse_all_logs(list(log_paths) if log_paths else None)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    usages = [u for u in usages if u.timestamp and u.timestamp >= today_start]
    
    total_cost = sum(calculate_cost(u) for u in usages)
    
    if as_sarif:
        from agentcost import __version__
        sarif_doc = budget_to_sarif(
            {"daily": threshold},
            {"daily": total_cost},
            tool_version=__version__,
        )
        click.echo(sarif_to_string(sarif_doc))
        sys.exit(1 if total_cost >= threshold else 0)
    
    if total_cost >= threshold:
        console.print(f"[bold red]ALERT: Today's spending {_format_currency(total_cost)} exceeds threshold {_format_currency(threshold)}[/bold red]")
        sys.exit(1)
    else:
        remaining = threshold - total_cost
        console.print(f"[green]Within budget: {_format_currency(total_cost)} / {_format_currency(threshold)}[/green]")
        console.print(f"[dim]Remaining: {_format_currency(remaining)}[/dim]")
        sys.exit(0)


@cli.command()
@click.option("--job", "-j", default=None, help="Specific job ID to analyze")
@click.option("--limit", "-l", default=5, help="Max output files per job")
@click.option("--json-output", "json_out", is_flag=True, help="Output as JSON")
def cron(job, limit, json_out):
    """Analyze Hermes cron outputs and estimate cost per task."""
    from agentcost.hermes_output import HermesOutputParser

    parser = HermesOutputParser()

    if job:
        usages = parser.parse_job_outputs(job, limit=limit)
    else:
        usages = []
        for jid in parser.list_jobs():
            usages.extend(parser.parse_job_outputs(jid, limit=limit))

    if not usages:
        console.print("[yellow]No cron outputs found.[/yellow]")
        return

    # Group by job/agent_id
    by_job = {}
    for u in usages:
        job_name = u.agent_id or "unknown"
        if job_name not in by_job:
            by_job[job_name] = []
        by_job[job_name].append(u)

    if json_out:
        output = {}
        for job_name, job_usages in sorted(by_job.items()):
            bd = summarize_usage(job_usages)
            output[job_name] = {
                "runs": bd.calls,
                "tokens": bd.total_tokens,
                "cost_usd": round(bd.total_cost_usd, 6),
            }
        click.echo(json.dumps(output, indent=2, default=str))
        return

    console.print(Panel(
        f"[bold]Cron Cost Analysis[/bold]\n"
        f"Jobs: [cyan]{len(by_job)}[/cyan] | "
        f"Total runs: [cyan]{len(usages)}[/cyan]",
        title="agentcost — Cron"
    ))

    table = Table(title="Cost per Cron Job")
    table.add_column("Job")
    table.add_column("Runs", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right")

    total_cost = 0
    for job_name, job_usages in sorted(by_job.items(), key=lambda x: summarize_usage(x[1]).total_cost_usd, reverse=True):
        bd = summarize_usage(job_usages)
        total_cost += bd.total_cost_usd
        table.add_row(
            job_name[:30],
            str(bd.calls),
            _format_tokens(bd.total_tokens),
            _format_currency(bd.total_cost_usd),
        )

    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{len(usages)}[/bold]",
        "",
        f"[bold]{_format_currency(total_cost)}[/bold]",
    )

    console.print(table)


@cli.command()
@click.argument("action", type=click.Choice(["set", "check", "show"]))
@click.option("--daily", type=float, default=None, help="Daily budget in USD")
@click.option("--weekly", type=float, default=None, help="Weekly budget in USD")
@click.option("--monthly", type=float, default=None, help="Monthly budget in USD")
@click.option("--sarif", "as_sarif", is_flag=True, help="Output SARIF 2.1.0 (for GitHub Code Scanning)")
def budget(action, daily, weekly, monthly, as_sarif):
    """Manage spending budgets and check thresholds."""
    if action == "set":
        save_budget_config(daily, weekly, monthly)
        console.print("[green]Budget thresholds saved to ~/.agentcost/config.toml[/green]")
        if daily:
            console.print(f"  Daily: ${daily:.2f}")
        if weekly:
            console.print(f"  Weekly: ${weekly:.2f}")
        if monthly:
            console.print(f"  Monthly: ${monthly:.2f}")
    elif action == "show":
        config = load_budget_config()
        if not config:
            console.print("[yellow]No budget thresholds set.[/yellow]")
            return
        console.print("[bold]Budget Thresholds:[/bold]")
        if "daily" in config:
            console.print(f"  Daily: ${config['daily']:.2f}")
        if "weekly" in config:
            console.print(f"  Weekly: ${config['weekly']:.2f}")
        if "monthly" in config:
            console.print(f"  Monthly: ${config['monthly']:.2f}")
    elif action == "check":
        from datetime import datetime, timedelta
        config = load_budget_config()
        if not config:
            console.print("[yellow]No budget thresholds set. Run 'agentcost budget set' first.[/yellow]")
            sys.exit(1)

        usages = _parse_all_logs()
        if not usages:
            console.print("[yellow]No usage data found.[/yellow]")
            sys.exit(0)

        now = datetime.now()
        exit_code = 0
        actuals = {}

        if "daily" in config:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_usages = [u for u in usages if u.timestamp and u.timestamp >= today_start]
            today_cost = sum(calculate_cost(u) for u in today_usages)
            actuals["daily"] = today_cost
            if today_cost > config["daily"]:
                exit_code = 1

        if "weekly" in config:
            week_start = now - timedelta(days=7)
            week_usages = [u for u in usages if u.timestamp and u.timestamp >= week_start]
            week_cost = sum(calculate_cost(u) for u in week_usages)
            actuals["weekly"] = week_cost
            if week_cost > config["weekly"]:
                exit_code = 1

        if "monthly" in config:
            month_start = now - timedelta(days=30)
            month_usages = [u for u in usages if u.timestamp and u.timestamp >= month_start]
            month_cost = sum(calculate_cost(u) for u in month_usages)
            actuals["monthly"] = month_cost
            if month_cost > config["monthly"]:
                exit_code = 1

        if as_sarif:
            from agentcost import __version__
            sarif_doc = budget_to_sarif(config, actuals, tool_version=__version__)
            click.echo(sarif_to_string(sarif_doc))
            sys.exit(exit_code)

        # CLI output
        if "daily" in config:
            today_cost = actuals["daily"]
            if today_cost > config["daily"]:
                console.print(f"[red]DAILY BUDGET EXCEEDED: ${today_cost:.4f} / ${config['daily']:.2f}[/red]")
            else:
                console.print(f"[green]Daily: ${today_cost:.4f} / ${config['daily']:.2f}[/green]")

        if "weekly" in config:
            week_cost = actuals["weekly"]
            if week_cost > config["weekly"]:
                console.print(f"[red]WEEKLY BUDGET EXCEEDED: ${week_cost:.4f} / ${config['weekly']:.2f}[/red]")
            else:
                console.print(f"[green]Weekly: ${week_cost:.4f} / ${config['weekly']:.2f}[/green]")

        if "monthly" in config:
            month_cost = actuals["monthly"]
            if month_cost > config["monthly"]:
                console.print(f"[red]MONTHLY BUDGET EXCEEDED: ${month_cost:.4f} / ${config['monthly']:.2f}[/red]")
            else:
                console.print(f"[green]Monthly: ${month_cost:.4f} / ${config['monthly']:.2f}[/green]")

        sys.exit(exit_code)


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


@cli.command()
@click.option("--path", "-p", "log_paths", multiple=True, type=click.Path(path_type=Path),
              help="Custom log paths")
@click.option("--period", "-pe", default="daily", type=click.Choice(["daily", "weekly", "monthly"]),
              help="Period to compare")
@click.option("--format", "-f", "output_format", default="cli", type=click.Choice(["cli", "json", "markdown"]))
def compare(log_paths, period, output_format):
    """Compare costs across agents for a given period."""
    from datetime import datetime, timedelta
    
    log_paths = list(log_paths) if log_paths else None
    usages = _parse_all_logs(log_paths)
    
    if not usages:
        console.print("[yellow]No usage data found for comparison.[/yellow]")
        return
    
    # Filter by period
    if period == "daily":
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        cutoff = datetime.now() - timedelta(days=7)
    else:  # monthly
        cutoff = datetime.now() - timedelta(days=30)
    
    usages = [u for u in usages if u.timestamp and u.timestamp >= cutoff]
    
    if not usages:
        console.print(f"[yellow]No usage data found for the last {period}.[/yellow]")
        return
    
    # Group by agent
    by_agent = {}
    for u in usages:
        agent_name = u.agent_id or u.model or "unknown"
        if agent_name not in by_agent:
            by_agent[agent_name] = []
        by_agent[agent_name].append(u)
    
    # Build comparison
    comparison = []
    for agent_name, agent_usages in by_agent.items():
        bd = summarize_usage(agent_usages)
        comparison.append({
            "agent": agent_name,
            "calls": bd.calls,
            "tokens": bd.total_tokens,
            "cost_usd": round(bd.total_cost_usd, 4),
        })
    
    # Sort by cost descending
    comparison.sort(key=lambda x: x["cost_usd"], reverse=True)
    
    if output_format == "json":
        click.echo(json.dumps(comparison, indent=2))
    elif output_format == "markdown":
        click.echo(f"# Cost Comparison — {period.title()}\n")
        click.echo("| Agent | Calls | Tokens | Cost |")
        click.echo("|-------|-------|--------|------|")
        for c in comparison:
            click.echo(f"| {c['agent']} | {c['calls']} | {c['tokens']:,} | {_format_currency(c['cost_usd'])} |")
    else:
        console.print(Panel(
            f"[bold]Cost Comparison — {period.title()}[/bold]\n"
            f"Agents: [cyan]{len(comparison)}[/cyan]",
            title="agentcost — Compare"
        ))
        
        table = Table(title="Cost by Agent")
        table.add_column("Agent")
        table.add_column("Calls", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Cost", justify="right")
        
        for c in comparison:
            table.add_row(c["agent"], str(c["calls"]), _format_tokens(c["tokens"]), _format_currency(c["cost_usd"]))
        
        total_calls = sum(c["calls"] for c in comparison)
        total_tokens = sum(c["tokens"] for c in comparison)
        total_cost = sum(c["cost_usd"] for c in comparison)
        table.add_row("[bold]Total[/bold]", f"[bold]{total_calls}[/bold]",
                      f"[bold]{_format_tokens(total_tokens)}[/bold]",
                      f"[bold]{_format_currency(total_cost)}[/bold]")
        
        console.print(table)


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
