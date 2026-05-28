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
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="LLM provider: github, bedrock (Claude via AWS)"
    ),
    files: Optional[str] = typer.Option(
        None, "--files", "-f",
        help="Comma-separated list of files to scan (full-file analysis, not just diffs)."
    ),
    base: Optional[str] = typer.Option(
        None, "--base", "-b",
        help="Base branch/commit to diff against (e.g., master, main, HEAD~5)."
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
    if provider:
        config.llm_provider = provider
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
    if files:
        console.print(f"  📋 Scan Mode: [bold]Specific files ({len(files.split(','))} file(s))[/bold]")
    elif base:
        console.print(f"  📋 Scan Mode: [bold]Diff against {base}[/bold]")
    else:
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
def fix(
    repo: Optional[str] = typer.Option(
        None, "--repo", "-r",
        help="Path to the git repository. Defaults to current directory."
    ),
    file: Optional[str] = typer.Option(
        None, "--file", "-f",
        help="Relative path to the file containing the defect."
    ),
    line: Optional[int] = typer.Option(
        None, "--line", "-l",
        help="Line number of the defect (1-based)."
    ),
    issue: Optional[str] = typer.Option(
        None, "--issue", "-i",
        help="Issue type/description (e.g., 'RESOURCE_LEAK', 'Null pointer dereference')."
    ),
    apply: bool = typer.Option(
        False, "--apply",
        help="Apply the fix directly to the file (otherwise just shows the diff)."
    ),
    from_csv: Optional[str] = typer.Option(
        None, "--from-csv",
        help="Path to Coverity CSV export to batch-fix all defects."
    ),
    from_json: Optional[str] = typer.Option(
        None, "--from-json",
        help="Path to cov-format-errors JSON output to batch-fix all defects."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="LLM provider: github, bedrock (Claude via AWS)"
    ),
    max_fixes: int = typer.Option(
        50, "--max-fixes",
        help="Maximum number of defects to fix in batch mode."
    ),
    severity_filter: Optional[str] = typer.Option(
        None, "--severity",
        help="Only fix defects of this severity (High, Medium, Low) in batch mode."
    ),
):
    """
    🔧 Auto-fix Coverity/static-analysis defects using AI.

    Single defect mode:
        vtune-guardian fix --file src/collector.cpp --line 142 --issue "RESOURCE_LEAK"

    Batch mode from Coverity CSV:
        vtune-guardian fix --from-csv coverity_export.csv --apply

    Batch mode from JSON:
        vtune-guardian fix --from-json cov-errors.json --apply
    """
    _print_banner()
    start_time = time.time()

    # Load config
    config = GuardianConfig.load()
    if provider:
        config.llm_provider = provider

    # Determine repository path
    repo_path = Path(repo) if repo else Path.cwd()
    if not (repo_path / ".git").exists():
        current = repo_path
        found = False
        while current != current.parent:
            if (current / ".git").exists():
                repo_path = current
                found = True
                break
            current = current.parent
        if not found:
            console.print("[red]❌ Error:[/red] Not a git repository. Use --repo to specify the path.")
            raise typer.Exit(code=1)

    # Get LLM
    from guardian.llm.provider import get_llm
    try:
        llm = get_llm(config)
    except Exception as e:
        console.print(f"[red]❌ LLM init failed:[/red] {e}")
        raise typer.Exit(code=2)

    from guardian.nodes.fix_issue import fix_single_issue, apply_fix, FixResult
    from guardian.nodes.coverity_parser import (
        parse_coverity_csv, parse_coverity_json, get_issue_description, CoverityDefect,
    )

    # ── Batch mode from CSV/JSON ──
    if from_csv or from_json:
        try:
            if from_csv:
                defects = parse_coverity_csv(from_csv, repo_root=str(repo_path))
                source_label = from_csv
            else:
                defects = parse_coverity_json(from_json, repo_root=str(repo_path))
                source_label = from_json
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]❌ Parse error:[/red] {e}")
            raise typer.Exit(code=1)

        # Apply filters
        if severity_filter:
            defects = [d for d in defects if d.severity.lower() == severity_filter.lower()]

        if not defects:
            console.print("[yellow]No defects found matching criteria.[/yellow]")
            raise typer.Exit(code=0)

        defects = defects[:max_fixes]
        console.print(f"  📂 Repository: [bold]{repo_path}[/bold]")
        console.print(f"  📄 Source: [bold]{source_label}[/bold]")
        console.print(f"  🐛 Defects: [bold]{len(defects)}[/bold]")
        console.print()

        _run_batch_fix(defects, str(repo_path), llm, apply, start_time)
        return

    # ── Single defect mode ──
    if not file or not line or not issue:
        console.print(
            "[red]❌ Error:[/red] Single-fix mode requires --file, --line, and --issue.\n"
            "  Example: vtune-guardian fix --file src/foo.cpp --line 42 --issue RESOURCE_LEAK\n"
            "  Or use --from-csv / --from-json for batch mode."
        )
        raise typer.Exit(code=1)

    console.print(f"  📂 Repository: [bold]{repo_path}[/bold]")
    console.print(f"  📄 File: [bold]{file}[/bold]")
    console.print(f"  📍 Line: [bold]{line}[/bold]")
    console.print(f"  🐛 Issue: [bold]{issue}[/bold]")
    console.print()

    with console.status("[bold cyan]Generating fix..."):
        result = fix_single_issue(
            repo_path=str(repo_path),
            file_path=file,
            line_number=line,
            issue_type=get_issue_description(issue, issue),
            llm=llm,
        )

    _display_fix_result(result, str(repo_path), apply)

    elapsed = time.time() - start_time
    console.print(f"\n  ⏱️  Time: [bold]{elapsed:.1f}s[/bold]")


def _run_batch_fix(defects: list, repo_path: str, llm, do_apply: bool, start_time: float):
    """Run batch fix across a list of CoverityDefect objects."""
    from guardian.nodes.fix_issue import fix_single_issue, apply_fix
    from guardian.nodes.coverity_parser import get_issue_description
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

    results = {"fixed": 0, "failed": 0, "skipped": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Fixing defects...", total=len(defects))

        for defect in defects:
            progress.update(task, description=f"[cyan]{defect.file_path}:{defect.line_number}[/cyan]")

            fix_result = fix_single_issue(
                repo_path=repo_path,
                file_path=defect.file_path,
                line_number=defect.line_number,
                issue_type=get_issue_description(defect.checker, defect.description),
                llm=llm,
            )

            if not fix_result.success:
                results["failed"] += 1
                console.print(
                    f"  [red]✗[/red] CID-{defect.cid} {defect.checker} "
                    f"@ {defect.file_path}:{defect.line_number} — {fix_result.error}"
                )
            elif do_apply:
                success, msg = apply_fix(repo_path, fix_result)
                if success:
                    results["fixed"] += 1
                    console.print(
                        f"  [green]✓[/green] CID-{defect.cid} {defect.checker} "
                        f"@ {defect.file_path}:{defect.line_number} — Applied"
                    )
                else:
                    results["failed"] += 1
                    console.print(
                        f"  [red]✗[/red] CID-{defect.cid} {defect.checker} "
                        f"@ {defect.file_path}:{defect.line_number} — {msg}"
                    )
            else:
                results["fixed"] += 1
                _display_fix_result(fix_result, repo_path, do_apply=False, compact=True)

            progress.advance(task)

    elapsed = time.time() - start_time
    console.print()
    console.print(Panel(
        f"[bold]Batch Fix Summary[/bold]\n"
        f"  ✅ Fixed:   {results['fixed']}\n"
        f"  ❌ Failed:  {results['failed']}\n"
        f"  ⏭️  Skipped: {results['skipped']}\n"
        f"  ⏱️  Time:    {elapsed:.1f}s",
        border_style="cyan",
    ))


def _display_fix_result(result, repo_path: str, do_apply: bool, compact: bool = False):
    """Display a single fix result."""
    from guardian.nodes.fix_issue import apply_fix

    if not result.success:
        console.print(f"  [red]❌ Cannot fix:[/red] {result.error}")
        return

    if compact:
        console.print(
            f"  [green]✓[/green] {result.file_path}:{result.line_number} — {result.explanation}"
        )
    else:
        from rich.syntax import Syntax
        console.print(f"\n[bold green]Fix generated:[/bold green] {result.explanation}\n")
        console.print("[dim]── Original ──[/dim]")
        console.print(Syntax(result.original_code, "text", theme="monokai", line_numbers=False))
        console.print("[dim]── Fixed ──[/dim]")
        console.print(Syntax(result.fixed_code, "text", theme="monokai", line_numbers=False))

    if do_apply:
        success, msg = apply_fix(repo_path, result)
        if success:
            console.print(f"  [green]✅ {msg}[/green]")
        else:
            console.print(f"  [red]❌ {msg}[/red]")


@app.command()
def config_show():
    """📋 Show current configuration."""
    _print_banner()
    config = GuardianConfig.load()

    console.print("[bold]Current Configuration:[/bold]\n")
    console.print(f"  Provider:          {config.llm_provider}")
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
