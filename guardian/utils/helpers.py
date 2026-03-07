"""
VTune GuardianAI - Utility Helpers
====================================
Common helper functions used across the project.
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple


def is_tool_available(tool_name: str) -> bool:
    """Check if a command-line tool is available on PATH."""
    return shutil.which(tool_name) is not None


def run_command(
    cmd: list[str],
    cwd: Optional[str] = None,
    timeout: int = 60,
) -> tuple[int, str, str]:
    """
    Run a shell command and return (returncode, stdout, stderr).

    Args:
        cmd: Command and arguments as a list.
        cwd: Working directory.
        timeout: Timeout in seconds.

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)


def truncate_diff(diff: str, max_chars: int = 8000) -> str:
    """
    Intelligently truncate a diff to fit within max_chars.
    Preserves the beginning and end of the diff.
    """
    if len(diff) <= max_chars:
        return diff

    half = max_chars // 2
    return (
        diff[:half]
        + f"\n\n... [TRUNCATED {len(diff) - max_chars} chars] ...\n\n"
        + diff[-half:]
    )


def get_file_content(repo_path: str, file_path: str, max_lines: int = 500) -> str:
    """
    Read file content from the repo.

    Args:
        repo_path: Root of the repository.
        file_path: Relative path to the file.
        max_lines: Maximum number of lines to read.

    Returns:
        File content as string.
    """
    full_path = Path(repo_path) / file_path
    if not full_path.exists():
        return ""

    try:
        lines = full_path.read_text(errors="ignore").splitlines()
        if len(lines) > max_lines:
            return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} more lines]"
        return "\n".join(lines)
    except Exception:
        return ""


def count_lines_in_diff(diff: str) -> tuple[int, int]:
    """
    Count added and deleted lines in a diff.

    Returns:
        Tuple of (lines_added, lines_deleted)
    """
    added = 0
    deleted = 0
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            deleted += 1
    return added, deleted


def get_source_context(
    repo_path: str,
    file_path: str,
    line_number: int,
    context_lines: int = 3,
) -> tuple[str, int, int]:
    """
    Read source code lines around a given line number for context display.

    Args:
        repo_path: Root of the repository.
        file_path: Relative path to the file.
        line_number: The line number of the issue (1-based).
        context_lines: Number of lines to include before and after.

    Returns:
        Tuple of (source_text, start_line, end_line).
        source_text includes line numbers as prefix.
    """
    full_path = Path(repo_path) / file_path
    if not full_path.exists() or line_number <= 0:
        return "", 0, 0

    try:
        lines = full_path.read_text(errors="ignore").splitlines()
        total = len(lines)

        start = max(0, line_number - 1 - context_lines)
        end = min(total, line_number + context_lines)

        numbered_lines = []
        for i in range(start, end):
            ln = i + 1
            marker = "→ " if ln == line_number else "  "
            numbered_lines.append(f"{marker}{ln:4d} │ {lines[i]}")

        return "\n".join(numbered_lines), start + 1, end

    except Exception:
        return "", 0, 0


def detect_language_from_path(file_path: str) -> str:
    """Detect the syntax highlight language from a file path."""
    ext_map = {
        ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".c": "c",
        ".h": "cpp", ".hpp": "cpp", ".hxx": "cpp",
        ".py": "python",
        ".js": "javascript", ".ts": "typescript",
        ".java": "java", ".rs": "rust", ".go": "go",
        ".cmake": "cmake", ".sh": "bash", ".bat": "batch",
    }
    ext = Path(file_path).suffix.lower()
    return ext_map.get(ext, "")
