"""
VTune GuardianAI - Best Practices Check Node
===============================================
Checks code changes against coding best practices
and style guidelines for the VTune codebase.
"""

from __future__ import annotations

import uuid
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from rich.console import Console

from guardian.agents.state import GuardianState, Issue
from guardian.config import GuardianConfig

console = Console()

BEST_PRACTICES_PROMPT = """You are a senior engineer enforcing coding best practices for Intel VTune Profiler.
Review the following code diff and check for best practice violations.

Focus on:
1. **Code Quality**: Magic numbers, overly complex functions, deep nesting
2. **Naming Conventions**: Poor variable/function names, inconsistent naming
3. **Documentation**: Missing comments for complex logic, outdated comments
4. **Error Messages**: Unhelpful error messages, missing error context
5. **DRY Principle**: Duplicated code, copy-paste patterns
6. **SOLID Principles**: Single responsibility violations, tight coupling
7. **Modern C++ (if C++)**: Using C-style casts, raw arrays, manual memory mgmt
8. **Logging**: Missing logging for important operations, excessive debug logs
9. **Testing**: Untestable code patterns, missing edge case handling

For each issue, respond in EXACTLY this format:
ISSUE_START
SEVERITY: critical|warning|info
LINE: <line_number_or_0>
TITLE: <short_title>
DESCRIPTION: <detailed_description>
SUGGESTION: <how_to_fix>
CODE: <relevant_problematic_code_snippet>
FIX_CODE: <the_fixed_version_of_the_code_snippet>
ISSUE_END

If no issues are found, respond with: NO_ISSUES_FOUND

Focus on actionable, meaningful feedback. Skip trivial style nitpicks."""


def best_practices_node(
    state: GuardianState,
    config: GuardianConfig,
    llm: Optional[BaseChatModel] = None,
) -> dict:
    """
    Check code changes against best practices using LLM.
    """
    console.print("  📏 [bold cyan]Node 3f:[/bold cyan] Checking best practices...")

    if not llm:
        console.print("    [yellow]⚠ LLM not available, skipping best practices check[/yellow]")
        return {"best_practice_issues": []}

    all_files = state.cpp_files + state.python_files + state.other_files
    if not all_files:
        console.print("    No files to check.")
        return {"best_practice_issues": []}

    issues = []

    # Combine diffs for batch analysis (more efficient)
    combined_diffs = ""
    file_paths = []

    for fc in all_files:
        if fc.change_type == "deleted" or not fc.diff_content:
            continue

        chunk = f"\n=== File: {fc.file_path} (Language: {fc.language}) ===\n{fc.diff_content[:3000]}\n"

        if len(combined_diffs) + len(chunk) > 8000:
            # Process current batch
            batch_issues = _analyze_best_practices(llm, combined_diffs, file_paths)
            issues.extend(batch_issues)
            combined_diffs = chunk
            file_paths = [fc.file_path]
        else:
            combined_diffs += chunk
            file_paths.append(fc.file_path)

    # Process remaining batch
    if combined_diffs:
        batch_issues = _analyze_best_practices(llm, combined_diffs, file_paths)
        issues.extend(batch_issues)

    console.print(f"    Found [bold]{len(issues)}[/bold] best practice issue(s)")

    return {"best_practice_issues": issues}


def _analyze_best_practices(
    llm: BaseChatModel,
    combined_diffs: str,
    file_paths: list[str],
) -> list[Issue]:
    """Analyze a batch of diffs for best practice violations."""
    try:
        messages = [
            SystemMessage(content=BEST_PRACTICES_PROMPT),
            HumanMessage(content=f"Code changes to review:\n\n{combined_diffs}"),
        ]

        response = llm.invoke(messages)
        return _parse_bp_issues(response.content, file_paths[0] if file_paths else "")

    except Exception as e:
        console.print(f"    [yellow]⚠ Best practices review error: {e}[/yellow]")
        return []


def _parse_bp_issues(response: str, default_file: str) -> list[Issue]:
    """Parse LLM best practices response into Issues."""
    issues = []

    if "NO_ISSUES_FOUND" in response:
        return []

    blocks = response.split("ISSUE_START")
    for block in blocks[1:]:
        if "ISSUE_END" not in block:
            continue

        issue_text = block.split("ISSUE_END")[0].strip()

        severity = _extract_field(issue_text, "SEVERITY", "info").lower()
        if severity not in ("critical", "warning", "info"):
            severity = "info"

        line_str = _extract_field(issue_text, "LINE", "0")
        try:
            line_num = int(line_str)
        except ValueError:
            line_num = 0

        issues.append(Issue(
            id=f"bp-{uuid.uuid4().hex[:8]}",
            severity=severity,
            category="best_practice",
            file_path=default_file,
            line_number=line_num,
            title=_extract_field(issue_text, "TITLE", "Best practice issue"),
            description=_extract_field(issue_text, "DESCRIPTION", "Best practice violation"),
            suggestion=_extract_field(issue_text, "SUGGESTION", "Follow best practices"),
            source="best_practice",
            code_snippet=_extract_field(issue_text, "CODE", ""),
            fix_code_snippet=_extract_field(issue_text, "FIX_CODE", ""),
        ))

    return issues


def _extract_field(text: str, field_name: str, default: str = "") -> str:
    """Extract a field value from structured LLM response."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(f"{field_name}:"):
            return line[len(f"{field_name}:"):].strip()
    return default
