"""
VTune GuardianAI - CLI Entry Point
====================================
Command-line interface using Typer for beautiful terminal interaction.

Usage:
    vtune-guardian check              # Scan staged changes
    vtune-guardian check --all        # Scan all uncommitted changes
    vtune-guardian check --repo /path/to/vtune/component
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from guardian import __version__, __app_name__
from guardian.config import GuardianConfig

app = typer.Typer(
    name="vtune-guardian",
    help="🛡️ VTune GuardianAI - AI-Powered Pre-Push Code Guardian",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()


def _print_banner():
    """Print the GuardianAI banner."""
    banner_text = Text()
    banner_text.append("🛡️  VTune GuardianAI", style="bold cyan")
    banner_text.append(f"  v{__version__}\n", style="dim")
    banner_text.append("AI-Powered Pre-Push Code Guardian for Intel VTune", style="italic")

    console.print(Panel(
        banner_text,
        border_style="cyan",
        padding=(1, 2),
    ))


@app.command()
def check(
    repo: Optional[str] = typer.Option(
        None, "--repo", "-r",
        help="Path to the git repository to analyze. Defaults to current directory."
    ),
    all_changes: bool = typer.Option(
        False, "--all", "-a",
        help="Scan all uncommitted changes (not just staged)."
    ),
    report: Optional[str] = typer.Option(
        None, "--report",
        help="Report format: terminal, json, html"
    ),
    severity: Optional[str] = typer.Option(
        None, "--severity", "-s",
        help="Minimum severity threshold: critical, warning, info"
    ),
    no_static: bool = typer.Option(
        False, "--no-static",
        help="Skip static analysis (cppcheck/clang-tidy)."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Enable verbose output."
    ),
):
    """
    🔍 Analyze code changes before pushing to mainline.

    Runs multiple analysis passes including static analysis, memory leak detection,
    AI code review, security scanning, and best practices enforcement.
    """
    _print_banner()
    start_time = time.time()

    # Load configuration
    config = GuardianConfig.load()

    # Override config with CLI options
    if report:
        config.report_format = report
    if severity:
        config.severity_threshold = severity
    if no_static:
        config.enable_static_analysis = False

    # Determine repository path
    repo_path = Path(repo) if repo else Path.cwd()
    if not (repo_path / ".git").exists():
        # Try to find .git in parent directories
        found = False
        current = repo_path
        while current != current.parent:
            if (current / ".git").exists():
                repo_path = current
                found = True
                break
            current = current.parent
        if not found:
            console.print("[red]❌ Error:[/red] Not a git repository. Use --repo to specify the path.")
            raise typer.Exit(code=1)

    config.vtune_repo_path = str(repo_path)

    console.print(f"  📂 Repository: [bold]{repo_path}[/bold]")
    console.print(f"  🤖 LLM: [bold]{config.get_active_llm_info()}[/bold]")
    console.print(f"  📋 Scan Mode: [bold]{'All changes' if all_changes else 'Staged changes only'}[/bold]")
    console.print()

    # Import and run the LangGraph agent
    from guardian.agents.graph import run_guardian_agent

    try:
        result = run_guardian_agent(config=config, scan_all=all_changes, verbose=verbose)
    except Exception as e:
        console.print(f"[red]❌ Agent Error:[/red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=2)

    # Generate report
    from guardian.reporters.terminal import TerminalReporter
    from guardian.reporters.json_report import JsonReporter
    from guardian.reporters.html_report import HtmlReporter

    reporters = {
        "terminal": TerminalReporter,
        "json": JsonReporter,
        "html": HtmlReporter,
    }

    reporter_cls = reporters.get(config.report_format, TerminalReporter)
    if reporter_cls == TerminalReporter:
        reporter = reporter_cls(repo_path=str(repo_path))
    else:
        reporter = reporter_cls()
    reporter.generate(result)

    # Final summary
    elapsed = time.time() - start_time
    total_issues = result.get("total_issues", 0)
    critical = result.get("critical_count", 0)

    # Format elapsed time nicely
    if elapsed >= 60:
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        time_str = f"{minutes}m {seconds:.1f}s"
    else:
        time_str = f"{elapsed:.1f}s"

    console.print()
    if critical > 0:
        console.print(Panel(
            f"[red bold]🚫 PUSH BLOCKED[/red bold]\n"
            f"Found [red]{critical}[/red] critical issue(s) out of {total_issues} total.\n"
            f"Fix critical issues before pushing.\n"
            f"⏱️  Analysis Time: [bold]{time_str}[/bold]",
            border_style="red",
        ))
        raise typer.Exit(code=1)
    elif total_issues > 0:
        console.print(Panel(
            f"[yellow bold]⚠️  PUSH WITH CAUTION[/yellow bold]\n"
            f"Found [yellow]{total_issues}[/yellow] issue(s), none critical.\n"
            f"Review warnings before pushing.\n"
            f"⏱️  Analysis Time: [bold]{time_str}[/bold]",
            border_style="yellow",
        ))
    else:
        console.print(Panel(
            f"[green bold]✅ ALL CLEAR - SAFE TO PUSH[/green bold]\n"
            f"No issues found. Code looks good!\n"
            f"⏱️  Analysis Time: [bold]{time_str}[/bold]",
            border_style="green",
        ))


@app.command()
def config_show():
    """📋 Show current configuration."""
    _print_banner()
    config = GuardianConfig.load()

    console.print("[bold]Current Configuration:[/bold]\n")
    console.print(f"  LLM:               {config.get_active_llm_info()}")
    console.print(f"  Severity:          {config.severity_threshold}")
    console.print(f"  Max Files:         {config.max_files}")
    console.print(f"  Report Format:     {config.report_format}")
    console.print(f"  Static Analysis:   {'✅' if config.enable_static_analysis else '❌'}")
    console.print(f"  Memory Leak Check: {'✅' if config.enable_memory_leak_check else '❌'}")
    console.print(f"  AI Review:         {'✅' if config.enable_ai_review else '❌'}")
    console.print(f"  Security Check:    {'✅' if config.enable_security_check else '❌'}")
    console.print(f"  Build Compat:      {'✅' if config.enable_build_compat_check else '❌'}")
    console.print(f"  Best Practices:    {'✅' if config.enable_best_practices else '❌'}")


@app.command()
def version():
    """📌 Show version information."""
    console.print(f"{__app_name__} v{__version__}")


if __name__ == "__main__":
    app()
