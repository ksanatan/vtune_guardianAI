"""
VTune GuardianAI - Combined LLM Analysis Node
================================================
Merges memory leak, AI review, security (LLM part), and best practices
into ONE single LLM call for maximum speed on CPU-only machines.

Instead of 4 separate LLM invocations (~30 min on CPU), this does
everything in 1 call (~5-7 min on CPU).
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

COMBINED_SYSTEM_PROMPT = """You are an expert C/C++ and Python code security and quality analyzer.
Analyze the code diff below and find ALL bugs, security issues, memory problems, and bad practices.

CHECK FOR:
- Memory leaks (malloc without free, missing delete)
- Use-after-free (accessing freed pointers)
- Buffer overflows (strcpy, sprintf, gets without bounds)
- Hardcoded passwords, API keys, secrets in source code
- Command injection (system(), popen() with user input)
- Null pointer dereference
- Logic errors, off-by-one bugs
- Bad coding practices (magic numbers, no error handling)

OUTPUT FORMAT - For each issue use EXACTLY:
ISSUE_START
CATEGORY: memory_leak|bug|security|best_practice
SEVERITY: critical|warning|info
LINE: <line_number>
TITLE: <short title>
DESCRIPTION: <one sentence explanation>
SUGGESTION: <how to fix it>
CODE: <the bad code, 1-3 lines>
FIX_CODE: <the fixed code, 1-3 lines>
ISSUE_END

If no issues found respond with: NO_ISSUES_FOUND
Be thorough. Check every added line carefully. Do not miss hardcoded secrets or memory leaks."""


def combined_analysis_node(
    state: GuardianState,
    config: GuardianConfig,
    llm: Optional[BaseChatModel] = None,
) -> dict:
    """
    Run ALL LLM-based analysis in a single combined prompt.
    Returns issues split into the correct category buckets.
    """
    console.print("  🧠 [bold cyan]Node 3: Combined AI Analysis[/bold cyan] (memory + review + security + best practices)...")

    if not llm:
        console.print("    [yellow]⚠ LLM not available, skipping AI analysis[/yellow]")
        return {}

    all_files = state.cpp_files + state.python_files + state.other_files
    if not all_files:
        console.print("    No files to analyze.")
        return {}

    memory_issues = []
    ai_review_issues = []
    security_issues = []
    best_practice_issues = []

    for fc in all_files:
        if fc.change_type == "deleted" or not fc.diff_content:
            continue

        diff_content = fc.diff_content[:20000]

        try:
            messages = [
                SystemMessage(content=COMBINED_SYSTEM_PROMPT),
                HumanMessage(content=f"File: {fc.file_path} (Language: {fc.language})\n\nDiff:\n```\n{diff_content}\n```"),
            ]

            response = llm.invoke(messages)
            file_issues = _parse_combined_response(response.content, fc.file_path)

            # Sort into category buckets
            for issue in file_issues:
                if issue.category == "memory_leak":
                    memory_issues.append(issue)
                elif issue.category == "security":
                    security_issues.append(issue)
                elif issue.category == "best_practice":
                    best_practice_issues.append(issue)
                else:
                    ai_review_issues.append(issue)

        except Exception as e:
            console.print(f"    [yellow]⚠ Analysis error for {fc.file_path}: {e}[/yellow]")

    total = len(memory_issues) + len(ai_review_issues) + len(security_issues) + len(best_practice_issues)
    console.print(f"    Found [bold]{total}[/bold] issue(s): "
                  f"🧠 {len(memory_issues)} memory, "
                  f"🤖 {len(ai_review_issues)} bugs, "
                  f"🔒 {len(security_issues)} security, "
                  f"📏 {len(best_practice_issues)} best practice")

    return {
        "memory_leak_issues": memory_issues,
        "ai_review_issues": ai_review_issues,
        "security_issues": security_issues,
        "best_practice_issues": best_practice_issues,
    }


def _parse_combined_response(response: str, file_path: str) -> list[Issue]:
    """Parse the combined LLM response into Issue objects with correct categories."""
    issues = []

    if "NO_ISSUES_FOUND" in response:
        return []

    blocks = response.split("ISSUE_START")

    for block in blocks[1:]:
        if "ISSUE_END" not in block:
            continue

        issue_text = block.split("ISSUE_END")[0].strip()

        # Extract category
        category = _extract_field(issue_text, "CATEGORY", "bug").lower().strip()
        category_map = {
            "memory_leak": "memory_leak",
            "memory": "memory_leak",
            "bug": "bug",
            "security": "security",
            "best_practice": "best_practice",
            "best_practices": "best_practice",
            "style": "best_practice",
        }
        category = category_map.get(category, "bug")

        # Source mapping for display
        source_map = {
            "memory_leak": "memory_leak",
            "bug": "ai_review",
            "security": "security",
            "best_practice": "best_practice",
        }

        severity = _extract_field(issue_text, "SEVERITY", "warning").lower().strip()
        if severity not in ("critical", "warning", "info"):
            severity = "warning"

        line_str = _extract_field(issue_text, "LINE", "0")
        try:
            line_num = int(line_str.strip())
        except ValueError:
            line_num = 0

        title = _extract_field(issue_text, "TITLE", "Issue detected")
        description = _extract_field(issue_text, "DESCRIPTION", "Potential issue found")
        suggestion = _extract_field(issue_text, "SUGGESTION", "Review the code")
        code_snippet = _extract_field(issue_text, "CODE", "")
        fix_code_snippet = _extract_field(issue_text, "FIX_CODE", "")

        issues.append(Issue(
            id=f"combined-{uuid.uuid4().hex[:8]}",
            severity=severity,
            category=category,
            file_path=file_path,
            line_number=line_num,
            title=title,
            description=description,
            suggestion=suggestion,
            source=source_map.get(category, "ai_review"),
            code_snippet=code_snippet,
            fix_code_snippet=fix_code_snippet,
        ))

    return issues


def _extract_field(text: str, field_name: str, default: str = "") -> str:
    """Extract a field value from structured LLM response."""
    for line in text.splitlines():
        line_stripped = line.strip()
        if line_stripped.upper().startswith(f"{field_name.upper()}:"):
            return line_stripped[len(f"{field_name}:"):].strip()
    return default
