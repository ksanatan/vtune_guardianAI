"""
VTune GuardianAI - Static Analysis Node
=========================================
Runs cppcheck and clang-tidy on changed C/C++ files.
"""

from __future__ import annotations

import subprocess
import uuid
import tempfile
from pathlib import Path

from rich.console import Console

from guardian.agents.state import GuardianState, Issue
from guardian.config import GuardianConfig

console = Console()


def static_analysis_node(state: GuardianState, config: GuardianConfig) -> dict:
    """
    Run static analysis tools (cppcheck, clang-tidy) on C/C++ files.

    Returns issues found by the tools.
    """
    console.print("  🔬 [bold cyan]Node 3a:[/bold cyan] Running static analysis...")

    issues = []

    if not state.cpp_files:
        console.print("    No C/C++ files to analyze.")
        return {"static_analysis_issues": []}

    # Run cppcheck
    cppcheck_issues = _run_cppcheck(state, config)
    issues.extend(cppcheck_issues)

    # Run clang-tidy
    clang_tidy_issues = _run_clang_tidy(state, config)
    issues.extend(clang_tidy_issues)

    console.print(f"    Found [bold]{len(issues)}[/bold] static analysis issue(s)")

    return {"static_analysis_issues": issues}


def _run_cppcheck(state: GuardianState, config: GuardianConfig) -> list[Issue]:
    """Run cppcheck on changed C/C++ files."""
    issues = []

    # Check if cppcheck is available
    try:
        subprocess.run(
            [config.cppcheck_path, "--version"],
            capture_output=True, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        console.print("    [yellow]⚠ cppcheck not available, skipping[/yellow]")
        return []

    for fc in state.cpp_files:
        if fc.change_type == "deleted":
            continue

        file_path = Path(state.repo_path) / fc.file_path
        if not file_path.exists():
            continue

        try:
            result = subprocess.run(
                [
                    config.cppcheck_path,
                    "--enable=warning,performance,portability,style",
                    "--suppress=missingIncludeSystem",
                    "--template={file}:{line}:{severity}:{message}",
                    "--quiet",
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=state.repo_path,
            )

            # Parse cppcheck output
            for line in result.stderr.splitlines():
                parts = line.split(":", 3)
                if len(parts) >= 4:
                    file_name = parts[0]
                    try:
                        line_num = int(parts[1])
                    except ValueError:
                        line_num = 0
                    cppcheck_severity = parts[2].strip()
                    message = parts[3].strip()

                    severity = _map_cppcheck_severity(cppcheck_severity)

                    issues.append(Issue(
                        id=f"cppcheck-{uuid.uuid4().hex[:8]}",
                        severity=severity,
                        category="bug" if severity == "critical" else "style",
                        file_path=fc.file_path,
                        line_number=line_num,
                        title=f"cppcheck: {message[:80]}",
                        description=message,
                        suggestion="Review and fix the reported issue.",
                        source="static_analysis",
                    ))

        except subprocess.TimeoutExpired:
            console.print(f"    [yellow]⚠ cppcheck timeout on {fc.file_path}[/yellow]")
        except Exception as e:
            console.print(f"    [yellow]⚠ cppcheck error on {fc.file_path}: {e}[/yellow]")

    return issues


def _run_clang_tidy(state: GuardianState, config: GuardianConfig) -> list[Issue]:
    """Run clang-tidy on changed C/C++ files."""
    issues = []

    # Check if clang-tidy is available
    try:
        subprocess.run(
            [config.clang_tidy_path, "--version"],
            capture_output=True, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        console.print("    [yellow]⚠ clang-tidy not available, skipping[/yellow]")
        return []

    for fc in state.cpp_files:
        if fc.change_type == "deleted":
            continue

        file_path = Path(state.repo_path) / fc.file_path
        if not file_path.exists():
            continue

        # Only run on source files, not headers
        if file_path.suffix in (".h", ".hpp", ".hxx"):
            continue

        try:
            result = subprocess.run(
                [
                    config.clang_tidy_path,
                    str(file_path),
                    "--",  # Separator for compiler flags
                    "-std=c++17",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=state.repo_path,
            )

            # Parse clang-tidy output
            for line in result.stdout.splitlines():
                if ": warning:" in line or ": error:" in line:
                    try:
                        parts = line.split(":")
                        if len(parts) >= 5:
                            line_num = int(parts[1])
                            severity = "critical" if ": error:" in line else "warning"
                            message = ":".join(parts[4:]).strip()

                            issues.append(Issue(
                                id=f"clang-tidy-{uuid.uuid4().hex[:8]}",
                                severity=severity,
                                category="bug",
                                file_path=fc.file_path,
                                line_number=line_num,
                                title=f"clang-tidy: {message[:80]}",
                                description=message,
                                suggestion="Fix according to clang-tidy recommendation.",
                                source="static_analysis",
                            ))
                    except (ValueError, IndexError):
                        continue

        except subprocess.TimeoutExpired:
            console.print(f"    [yellow]⚠ clang-tidy timeout on {fc.file_path}[/yellow]")
        except Exception as e:
            console.print(f"    [yellow]⚠ clang-tidy error on {fc.file_path}: {e}[/yellow]")

    return issues


def _map_cppcheck_severity(cppcheck_severity: str) -> str:
    """Map cppcheck severity to GuardianAI severity."""
    mapping = {
        "error": "critical",
        "warning": "warning",
        "performance": "warning",
        "portability": "warning",
        "style": "info",
        "information": "info",
    }
    return mapping.get(cppcheck_severity.lower(), "info")
