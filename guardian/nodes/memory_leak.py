"""
VTune GuardianAI - Memory Leak Detection Node
================================================
Uses LLM to analyze C/C++ code changes for memory leak patterns.
Detects: malloc/free mismatches, dangling pointers, uninitialized memory,
resource leaks, RAII violations, smart pointer misuse.
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

MEMORY_LEAK_SYSTEM_PROMPT = """You are an expert C/C++ memory safety analyzer for Intel VTune Profiler codebase.
Analyze the following code diff for memory-related issues.

Focus on detecting:
1. **Memory Leaks**: malloc/new without corresponding free/delete
2. **Dangling Pointers**: Use-after-free, returning pointers to local variables
3. **Double Free**: Freeing memory that has already been freed
4. **Uninitialized Memory**: Using variables before initialization
5. **Buffer Overflows**: Writing past allocated buffer boundaries
6. **Resource Leaks**: File handles, sockets, mutex locks not properly released
7. **RAII Violations**: Raw pointers where smart pointers should be used
8. **Smart Pointer Misuse**: Circular references, using raw pointer from shared_ptr

For each issue found, respond in this EXACT format (one per issue):
ISSUE_START
SEVERITY: critical|warning|info
LINE: <line_number_or_0>
TITLE: <short_title>
DESCRIPTION: <detailed_description>
SUGGESTION: <how_to_fix>
CODE: <relevant_problematic_code_snippet>
FIX_CODE: <the_fixed_version_of_the_code_snippet>
ISSUE_END

If no memory issues are found, respond with: NO_ISSUES_FOUND

Be thorough but avoid false positives. Only report real concerns."""


def memory_leak_node(
    state: GuardianState,
    config: GuardianConfig,
    llm: Optional[BaseChatModel] = None,
) -> dict:
    """
    Analyze C/C++ code changes for memory leak patterns using LLM.
    """
    console.print("  🧠 [bold cyan]Node 3b:[/bold cyan] Detecting memory leak patterns...")

    if not llm:
        console.print("    [yellow]⚠ LLM not available, skipping memory leak detection[/yellow]")
        return {"memory_leak_issues": []}

    if not state.cpp_files:
        console.print("    No C/C++ files to analyze for memory leaks.")
        return {"memory_leak_issues": []}

    issues = []

    for fc in state.cpp_files:
        if fc.change_type == "deleted" or not fc.diff_content:
            continue

        # Truncate very large diffs to fit in context
        diff_content = fc.diff_content[:8000]

        try:
            messages = [
                SystemMessage(content=MEMORY_LEAK_SYSTEM_PROMPT),
                HumanMessage(content=f"File: {fc.file_path}\n\nDiff:\n```\n{diff_content}\n```"),
            ]

            response = llm.invoke(messages)
            response_text = response.content

            # Parse LLM response
            file_issues = _parse_memory_issues(response_text, fc.file_path)
            issues.extend(file_issues)

        except Exception as e:
            console.print(f"    [yellow]⚠ Memory analysis error for {fc.file_path}: {e}[/yellow]")

    console.print(f"    Found [bold]{len(issues)}[/bold] memory-related issue(s)")

    return {"memory_leak_issues": issues}


def _parse_memory_issues(response: str, file_path: str) -> list[Issue]:
    """Parse the LLM response into Issue objects."""
    issues = []

    if "NO_ISSUES_FOUND" in response:
        return []

    # Split by ISSUE_START/ISSUE_END markers
    blocks = response.split("ISSUE_START")

    for block in blocks[1:]:  # Skip everything before the first ISSUE_START
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

        title = _extract_field(issue_text, "TITLE", "Memory issue detected")
        description = _extract_field(issue_text, "DESCRIPTION", "Potential memory issue found")
        suggestion = _extract_field(issue_text, "SUGGESTION", "Review the memory management")
        code_snippet = _extract_field(issue_text, "CODE", "")
        fix_code_snippet = _extract_field(issue_text, "FIX_CODE", "")

        issues.append(Issue(
            id=f"memory-{uuid.uuid4().hex[:8]}",
            severity=severity,
            category="memory_leak",
            file_path=file_path,
            line_number=line_num,
            title=title,
            description=description,
            suggestion=suggestion,
            source="memory_leak",
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
