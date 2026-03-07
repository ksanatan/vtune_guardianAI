"""
VTune GuardianAI - AI Code Review Node
=========================================
Uses LLM for comprehensive AI-powered code review.
Covers: logic errors, race conditions, error handling,
API misuse, performance issues, and code quality.
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

AI_REVIEW_SYSTEM_PROMPT = """You are a senior code reviewer for Intel VTune Profiler — a performance analysis tool.
Analyze the following code diff thoroughly and identify bugs and quality issues.

Focus on:
1. **Logic Errors**: Incorrect conditions, off-by-one errors, wrong operators
2. **Race Conditions**: Thread safety issues, unprotected shared state
3. **Error Handling**: Missing error checks, swallowed exceptions, incorrect error propagation
4. **API Misuse**: Incorrect use of APIs, deprecated function calls
5. **Performance Issues**: Unnecessary copies, O(n²) where O(n) is possible, inefficient patterns
6. **Null/Nullptr**: Potential null pointer dereferences
7. **Integer Overflow**: Unchecked arithmetic that could overflow
8. **Resource Management**: Files, connections, locks not properly managed

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

Be precise. Avoid false positives. Focus on the CHANGED lines (lines starting with + in the diff).
Do NOT report issues in deleted code (lines starting with -)."""


def ai_review_node(
    state: GuardianState,
    config: GuardianConfig,
    llm: Optional[BaseChatModel] = None,
) -> dict:
    """
    Run AI-powered code review on all changed files using LLM.
    """
    console.print("  🤖 [bold cyan]Node 3c:[/bold cyan] Running AI code review...")

    if not llm:
        console.print("    [yellow]⚠ LLM not available, skipping AI review[/yellow]")
        return {"ai_review_issues": []}

    all_files = state.cpp_files + state.python_files + state.other_files

    if not all_files:
        console.print("    No files to review.")
        return {"ai_review_issues": []}

    issues = []

    # Batch small files together, process large ones individually
    batch = []
    batch_size = 0
    MAX_BATCH_SIZE = 6000  # characters

    for fc in all_files:
        if fc.change_type == "deleted" or not fc.diff_content:
            continue

        diff_len = len(fc.diff_content)

        if diff_len > MAX_BATCH_SIZE:
            # Process large file individually
            file_issues = _review_diff(llm, fc.file_path, fc.diff_content[:8000])
            issues.extend(file_issues)
        else:
            batch.append(fc)
            batch_size += diff_len

            if batch_size >= MAX_BATCH_SIZE:
                batch_issues = _review_batch(llm, batch)
                issues.extend(batch_issues)
                batch = []
                batch_size = 0

    # Process remaining batch
    if batch:
        batch_issues = _review_batch(llm, batch)
        issues.extend(batch_issues)

    console.print(f"    Found [bold]{len(issues)}[/bold] AI review issue(s)")

    return {"ai_review_issues": issues}


def _review_diff(llm: BaseChatModel, file_path: str, diff_content: str) -> list[Issue]:
    """Review a single file's diff."""
    try:
        messages = [
            SystemMessage(content=AI_REVIEW_SYSTEM_PROMPT),
            HumanMessage(content=f"File: {file_path}\n\nDiff:\n```\n{diff_content}\n```"),
        ]

        response = llm.invoke(messages)
        return _parse_review_issues(response.content, file_path)

    except Exception as e:
        console.print(f"    [yellow]⚠ AI review error for {file_path}: {e}[/yellow]")
        return []


def _review_batch(llm: BaseChatModel, files) -> list[Issue]:
    """Review a batch of small files together."""
    combined = "\n\n".join(
        f"=== File: {fc.file_path} ===\n{fc.diff_content}"
        for fc in files
    )

    try:
        messages = [
            SystemMessage(content=AI_REVIEW_SYSTEM_PROMPT),
            HumanMessage(content=f"Multiple files changed:\n\n{combined}"),
        ]

        response = llm.invoke(messages)

        # For batched reviews, try to map issues to specific files
        issues = []
        for fc in files:
            file_issues = _parse_review_issues(response.content, fc.file_path)
            # Only keep issues that reference this file
            for issue in file_issues:
                if issue.file_path == fc.file_path or not issue.file_path:
                    issue.file_path = fc.file_path
                    issues.append(issue)

        return issues

    except Exception as e:
        console.print(f"    [yellow]⚠ AI batch review error: {e}[/yellow]")
        return []


def _parse_review_issues(response: str, default_file: str) -> list[Issue]:
    """Parse the LLM response into Issue objects."""
    issues = []

    if "NO_ISSUES_FOUND" in response:
        return []

    blocks = response.split("ISSUE_START")

    for block in blocks[1:]:
        if "ISSUE_END" not in block:
            continue

        issue_text = block.split("ISSUE_END")[0].strip()

        severity = _extract_field(issue_text, "SEVERITY", "warning").lower()
        if severity not in ("critical", "warning", "info"):
            severity = "warning"

        line_str = _extract_field(issue_text, "LINE", "0")
        try:
            line_num = int(line_str)
        except ValueError:
            line_num = 0

        title = _extract_field(issue_text, "TITLE", "Code issue detected")
        description = _extract_field(issue_text, "DESCRIPTION", "Potential code issue")
        suggestion = _extract_field(issue_text, "SUGGESTION", "Review the code")
        code_snippet = _extract_field(issue_text, "CODE", "")
        fix_code_snippet = _extract_field(issue_text, "FIX_CODE", "")

        issues.append(Issue(
            id=f"ai-review-{uuid.uuid4().hex[:8]}",
            severity=severity,
            category="bug",
            file_path=default_file,
            line_number=line_num,
            title=title,
            description=description,
            suggestion=suggestion,
            source="ai_review",
            code_snippet=code_snippet,
            fix_code_snippet=fix_code_snippet,
        ))

    return issues


def _extract_field(text: str, field_name: str, default: str = "") -> str:
    """Extract a field value from the structured LLM response."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(f"{field_name}:"):
            return line[len(f"{field_name}:"):].strip()
    return default
