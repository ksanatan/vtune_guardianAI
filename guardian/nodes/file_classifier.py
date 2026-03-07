"""
VTune GuardianAI - File Classifier Node
=========================================
Classifies changed files by language/type and routes them
to appropriate analysis nodes.
"""

from __future__ import annotations

from rich.console import Console

from guardian.agents.state import GuardianState, FileChange
from guardian.config import GuardianConfig

console = Console()

# Language groups
CPP_LANGUAGES = {"cpp", "c", "h", "hpp"}
PYTHON_LANGUAGES = {"python"}
BUILD_LANGUAGES = {"scons", "cmake", "make"}


def file_classifier_node(state: GuardianState, config: GuardianConfig) -> dict:
    """
    Classify file changes into categories for routing to analysis nodes.

    Categories:
        - C/C++ files → static analysis, memory leak, AI review
        - Python files → security check, AI review
        - Build files → build compatibility check
        - Other files → AI review, best practices
    """
    console.print("  🏷️  [bold cyan]Node 2:[/bold cyan] Classifying files...")

    cpp_files = []
    python_files = []
    build_files = []
    other_files = []

    for fc in state.file_changes:
        if fc.change_type == "deleted":
            # Still classify but mark for limited analysis
            pass

        if fc.language in CPP_LANGUAGES:
            cpp_files.append(fc)
        elif fc.language in PYTHON_LANGUAGES:
            python_files.append(fc)
        elif fc.language in BUILD_LANGUAGES:
            build_files.append(fc)
        else:
            other_files.append(fc)

    if cpp_files:
        console.print(f"    📁 C/C++: {len(cpp_files)} file(s)")
    if python_files:
        console.print(f"    📁 Python: {len(python_files)} file(s)")
    if build_files:
        console.print(f"    📁 Build: {len(build_files)} file(s)")
    if other_files:
        console.print(f"    📁 Other: {len(other_files)} file(s)")

    return {
        "cpp_files": cpp_files,
        "python_files": python_files,
        "build_files": build_files,
        "other_files": other_files,
    }
