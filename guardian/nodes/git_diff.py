"""
VTune GuardianAI - Git Diff Node
==================================
Extracts changed files and diffs from the git repository.
This is the first node in the pipeline.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import git
from rich.console import Console

from guardian.agents.state import GuardianState, FileChange, Issue
from guardian.config import GuardianConfig

console = Console()


def git_diff_node(state: GuardianState, config: GuardianConfig) -> dict:
    """
    Extract git diffs from the repository.

    If scan_all=True, gets all uncommitted changes.
    If scan_all=False, gets only staged changes.
    """
    console.print("  📂 [bold cyan]Node 1:[/bold cyan] Extracting git diff...")

    repo_path = state.repo_path
    if not repo_path:
        return {"errors": state.errors + ["No repository path specified."]}

    try:
        repo = git.Repo(repo_path)
    except git.InvalidGitRepositoryError:
        return {"errors": state.errors + [f"Not a valid git repository: {repo_path}"]}
    except Exception as e:
        return {"errors": state.errors + [f"Error opening repository: {e}"]}

    file_changes = []

    try:
        if state.scan_all:
            # Get all uncommitted changes (staged + unstaged)
            # Compare working tree to HEAD
            diffs = repo.head.commit.diff(None)
            # Also get untracked files
            untracked = repo.untracked_files
        else:
            # Get only staged changes
            diffs = repo.index.diff("HEAD")
            untracked = []

        for diff in diffs:
            change_type = _get_change_type(diff)
            file_path = diff.b_path if diff.b_path else diff.a_path

            # Get the actual diff content (use -U25 for extra context around changes)
            try:
                if state.scan_all:
                    diff_content = repo.git.diff("HEAD", "-U25", "--", file_path)
                else:
                    diff_content = repo.git.diff("--cached", "-U25", "--", file_path)
            except Exception:
                diff_content = ""

            # Count lines
            lines_added = diff_content.count("\n+") if diff_content else 0
            lines_deleted = diff_content.count("\n-") if diff_content else 0

            file_change = FileChange(
                file_path=file_path,
                change_type=change_type,
                diff_content=diff_content,
                language=_detect_language(file_path),
                lines_added=lines_added,
                lines_deleted=lines_deleted,
            )
            file_changes.append(file_change)

        # Add untracked files
        for untracked_file in untracked:
            try:
                content = Path(repo_path, untracked_file).read_text(errors="ignore")
                diff_content = f"+++ {untracked_file}\n" + "\n".join(
                    f"+{line}" for line in content.splitlines()[:200]  # Limit to 200 lines
                )
            except Exception:
                diff_content = ""

            file_change = FileChange(
                file_path=untracked_file,
                change_type="added",
                diff_content=diff_content,
                language=_detect_language(untracked_file),
                lines_added=len(diff_content.splitlines()),
                lines_deleted=0,
            )
            file_changes.append(file_change)

    except Exception as e:
        return {"errors": state.errors + [f"Error extracting diffs: {e}"]}

    # Enforce max files limit
    if len(file_changes) > config.max_files:
        console.print(
            f"  [yellow]⚠ {len(file_changes)} files changed, limiting to {config.max_files}[/yellow]"
        )
        file_changes = file_changes[:config.max_files]

    # Check for language types
    languages = {fc.language for fc in file_changes}
    has_cpp = bool(languages & {"cpp", "c", "h", "hpp"})
    has_python = "python" in languages
    has_scons = any(
        fc.file_path.endswith(("SConstruct", "SConscript", ".parts"))
        or "scons" in fc.file_path.lower()
        for fc in file_changes
    )

    console.print(f"    Found [bold]{len(file_changes)}[/bold] changed file(s)")
    if has_cpp:
        cpp_count = sum(1 for fc in file_changes if fc.language in ("cpp", "c", "h", "hpp"))
        console.print(f"    C/C++ files: {cpp_count}")
    if has_python:
        py_count = sum(1 for fc in file_changes if fc.language == "python")
        console.print(f"    Python files: {py_count}")

    return {
        "file_changes": file_changes,
        "total_files_changed": len(file_changes),
        "has_cpp_changes": has_cpp,
        "has_python_changes": has_python,
        "has_scons_changes": has_scons,
    }


def _get_change_type(diff) -> str:
    """Convert git diff change type to human-readable string."""
    if diff.new_file:
        return "added"
    elif diff.deleted_file:
        return "deleted"
    elif diff.renamed_file:
        return "renamed"
    else:
        return "modified"


def _detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext_map = {
        ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
        ".c": "c",
        ".h": "h", ".hpp": "hpp", ".hxx": "hpp",
        ".py": "python",
        ".js": "javascript", ".ts": "typescript",
        ".java": "java",
        ".xml": "xml", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".sh": "shell", ".bash": "shell", ".bat": "batch",
        ".cmake": "cmake",
        ".md": "markdown", ".txt": "text",
        ".parts": "scons",
    }

    path = Path(file_path)

    # Special filenames
    if path.name in ("SConstruct", "SConscript"):
        return "scons"
    if path.name == "Makefile":
        return "make"
    if path.name == "CMakeLists.txt":
        return "cmake"

    return ext_map.get(path.suffix.lower(), "unknown")
