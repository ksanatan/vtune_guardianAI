"""
VTune GuardianAI - Terminal Reporter
======================================
Beautiful terminal output using Rich library.
Shows issues with source code context and suggested fixes.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from rich.syntax import Syntax
from rich.columns import Columns

from guardian.utils.helpers import get_source_context, detect_language_from_path


console = Console()

SEVERITY_ICONS = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
}

SEVERITY_STYLES = {
    "critical": "bold red",
    "warning": "bold yellow",
    "info": "bold blue",
}

CATEGORY_LABELS = {
    "bug": "Bug",
    "memory_leak": "Memory Leak",
    "security": "Security",
    "style": "Style",
    "build_compat": "Build Compat",
    "best_practice": "Best Practice",
}

SOURCE_LABELS = {
    "static_analysis": "Static Analysis",
    "memory_leak": "Memory Leak AI",
    "ai_review": "AI Code Review",
    "security": "Security Scan",
    "build_compat": "Build Check",
    "best_practice": "Best Practices",
}


class TerminalReporter:
    """Generates beautiful terminal reports with code context and fix suggestions."""

    def __init__(self, repo_path: str = ""):
        self.repo_path = repo_path

    def generate(self, result: dict) -> None:
        """Generate and print the terminal report."""
        all_issues = result.get("all_issues", [])
        total_files = result.get("total_files_changed", 0)
        decision = result.get("decision", "pass")

        # Header
        console.print()
        console.print(Panel(
            "[bold]📊 Analysis Report[/bold]",
            border_style="cyan",
            padding=(0, 2),
        ))

        # Summary
        self._print_summary(result)

        if not all_issues:
            console.print("\n  [green bold]No issues found! Your code looks great. 🎉[/green bold]\n")
            return

        # Detailed issues with code context and fixes
        self._print_detailed_issues(all_issues)

        # Compact summary table by severity
        self._print_issues_table(all_issues, "critical", "🔴 Critical Issues")
        self._print_issues_table(all_issues, "warning", "🟡 Warnings")
        self._print_issues_table(all_issues, "info", "🔵 Info")

        # Issues by source (analysis node)
        self._print_source_summary(result)

    def _print_summary(self, result: dict) -> None:
        """Print the analysis summary."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold")
        table.add_column("Value")

        table.add_row("Files Analyzed", str(result.get("total_files_changed", 0)))
        table.add_row("Total Issues", str(result.get("total_issues", 0)))

        critical = result.get("critical_count", 0)
        warning = result.get("warning_count", 0)
        info = result.get("info_count", 0)

        critical_style = "bold red" if critical > 0 else "green"
        table.add_row("Critical", f"[{critical_style}]{critical}[/{critical_style}]")
        table.add_row("Warnings", f"[yellow]{warning}[/yellow]")
        table.add_row("Info", f"[blue]{info}[/blue]")

        decision = result.get("decision", "pass")
        if decision == "block":
            table.add_row("Decision", "[bold red]🚫 BLOCK PUSH[/bold red]")
        elif decision == "warn":
            table.add_row("Decision", "[bold yellow]⚠️  WARN[/bold yellow]")
        else:
            table.add_row("Decision", "[bold green]✅ PASS[/bold green]")

        console.print(table)

    def _print_detailed_issues(self, all_issues: list) -> None:
        """Print detailed issue cards with source code context and fix suggestions."""
        console.print()
        console.print(Panel(
            "[bold]🔍 Detailed Issue Report — Code & Fixes[/bold]",
            border_style="magenta",
            padding=(0, 2),
        ))

        for idx, issue in enumerate(all_issues, 1):
            self._print_issue_card(idx, issue)

    def _print_issue_card(self, idx: int, issue) -> None:
        """Print a single detailed issue card with code snippet and fix."""
        # Extract fields (support both object and dict)
        if hasattr(issue, 'severity'):
            severity = issue.severity
            category = issue.category
            file_path = issue.file_path
            line_number = issue.line_number
            title = issue.title
            description = issue.description
            suggestion = issue.suggestion
            code_snippet = issue.code_snippet
            fix_code_snippet = getattr(issue, 'fix_code_snippet', '')
            source = issue.source
        else:
            severity = issue.get("severity", "info")
            category = issue.get("category", "")
            file_path = issue.get("file_path", "")
            line_number = issue.get("line_number", 0)
            title = issue.get("title", "")
            description = issue.get("description", "")
            suggestion = issue.get("suggestion", "")
            code_snippet = issue.get("code_snippet", "")
            fix_code_snippet = issue.get("fix_code_snippet", "")
            source = issue.get("source", "")

        icon = SEVERITY_ICONS.get(severity, "⚪")
        style = SEVERITY_STYLES.get(severity, "bold")
        cat_label = CATEGORY_LABELS.get(category, category)
        source_label = SOURCE_LABELS.get(source, source)
        lang = detect_language_from_path(file_path)

        # Build the issue header
        header = Text()
        header.append(f"{icon} Issue #{idx} ", style=style)
        header.append(f"[{severity.upper()}] ", style=style)
        header.append(f"{title}", style="bold white")

        # Build content parts
        content_parts = []

        # Location & metadata
        location_line = f"📁 {file_path}"
        if line_number and line_number > 0:
            location_line += f":{line_number}"
        location_line += f"  │  🏷️ {cat_label}  │  🔍 {source_label}"
        content_parts.append(f"[dim]{location_line}[/dim]")
        content_parts.append("")

        # Description
        content_parts.append(f"[bold]Description:[/bold] {description}")
        content_parts.append("")

        # Suggestion (text)
        if suggestion:
            content_parts.append(f"[green bold]💡 Fix:[/green bold] [green]{suggestion}[/green]")
            content_parts.append("")

        body_text = "\n".join(content_parts)

        # Print the panel
        border_color = {"critical": "red", "warning": "yellow", "info": "blue"}.get(severity, "white")
        console.print(Panel(
            body_text,
            title=f" {header} ",
            title_align="left",
            border_style=border_color,
            padding=(1, 2),
        ))

        # Print code context from actual source file
        if self.repo_path and file_path and line_number and line_number > 0:
            source_context, start_ln, end_ln = get_source_context(
                self.repo_path, file_path, line_number, context_lines=3
            )
            if source_context:
                console.print(f"  [dim bold]❌ Problematic Code[/dim bold] [dim]({file_path}:{start_ln}-{end_ln})[/dim]")
                if lang:
                    # Extract just the raw lines for syntax highlighting
                    raw_lines = "\n".join(
                        line.split("│ ", 1)[1] if "│ " in line else line
                        for line in source_context.splitlines()
                    )
                    console.print(Syntax(
                        raw_lines, lang,
                        theme="monokai",
                        line_numbers=True,
                        start_line=start_ln,
                        highlight_lines={line_number},
                    ))
                else:
                    console.print(Panel(source_context, border_style="red dim", padding=(0, 1)))
                console.print()

        # Print the code_snippet from LLM if no source context was available
        elif code_snippet:
            console.print(f"  [dim bold]❌ Problematic Code[/dim bold]")
            if lang:
                console.print(Syntax(code_snippet, lang, theme="monokai", line_numbers=False))
            else:
                console.print(Panel(code_snippet, border_style="red dim", padding=(0, 1)))
            console.print()

        # Print fix code snippet
        if fix_code_snippet:
            console.print(f"  [green bold]✅ Suggested Fix[/green bold]")
            if lang:
                console.print(Syntax(fix_code_snippet, lang, theme="monokai", line_numbers=False))
            else:
                console.print(Panel(f"[green]{fix_code_snippet}[/green]", border_style="green dim", padding=(0, 1)))
            console.print()

    def _print_issues_table(self, all_issues: list, severity: str, header: str) -> None:
        """Print a compact summary table of issues filtered by severity."""
        issues = [i for i in all_issues if (i.severity if hasattr(i, 'severity') else i.get('severity')) == severity]
        if not issues:
            return

        console.print(f"\n  [bold]{header}[/bold] ({len(issues)})")
        console.print("  " + "─" * 60)

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("#", width=4)
        table.add_column("Category", width=14)
        table.add_column("File", width=30)
        table.add_column("Line", width=6)
        table.add_column("Issue", min_width=40)

        for idx, issue in enumerate(issues, 1):
            # Support both object and dict
            if hasattr(issue, 'category'):
                cat = issue.category
                fp = issue.file_path
                ln = str(issue.line_number) if issue.line_number else "-"
                title = issue.title
                desc = issue.description
                suggestion = issue.suggestion
            else:
                cat = issue.get("category", "")
                fp = issue.get("file_path", "")
                ln = str(issue.get("line_number", 0)) or "-"
                title = issue.get("title", "")
                desc = issue.get("description", "")
                suggestion = issue.get("suggestion", "")

            cat_label = CATEGORY_LABELS.get(cat, cat)
            icon = SEVERITY_ICONS.get(severity, "")

            issue_text = f"[bold]{title}[/bold]"
            if suggestion:
                issue_text += f"\n[green]💡 {suggestion[:120]}[/green]"

            table.add_row(
                f"{icon} {idx}",
                cat_label,
                fp[:30],
                ln if ln != "0" else "-",
                issue_text,
            )

        console.print(table)

    def _print_source_summary(self, result: dict) -> None:
        """Print a tree view of issues by analysis source."""
        console.print("\n  [bold]📋 Issues by Analysis Source[/bold]")
        console.print("  " + "─" * 60)

        tree = Tree("🛡️  VTune GuardianAI Analysis")

        sources = [
            ("static_analysis_issues", "🔬 Static Analysis"),
            ("memory_leak_issues", "🧠 Memory Leak Detection"),
            ("ai_review_issues", "🤖 AI Code Review"),
            ("security_issues", "🔒 Security Scan"),
            ("build_compat_issues", "🏗️  Build Compatibility"),
            ("best_practice_issues", "📏 Best Practices"),
        ]

        for key, label in sources:
            issues = result.get(key, [])
            count = len(issues)
            if count > 0:
                critical = sum(
                    1 for i in issues
                    if (i.severity if hasattr(i, 'severity') else i.get('severity')) == "critical"
                )
                style = "red" if critical > 0 else "yellow"
                branch = tree.add(f"[{style}]{label}: {count} issue(s)[/{style}]")
            else:
                tree.add(f"[green]{label}: ✅ Clean[/green]")

        console.print(tree)
        console.print()
