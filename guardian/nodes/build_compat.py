"""
VTune GuardianAI - Build Compatibility Check Node
===================================================
Checks SCons/Parts build file changes for common issues.
Specific to the VTune build system (SCons + Intel Parts).
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from rich.console import Console

from guardian.agents.state import GuardianState, Issue
from guardian.config import GuardianConfig

console = Console()

BUILD_REVIEW_PROMPT = """You are an expert in SCons build system and Intel's Parts build framework.
Analyze the following build file changes for the Intel VTune Profiler project.

Common issues to check:
1. **Version Conflicts**: Component version changes that may break dependencies
2. **Missing Dependencies**: New includes/imports without adding dependency in build config
3. **Build Order Issues**: Circular dependencies or incorrect build ordering
4. **Platform Issues**: Changes that may break Linux/Windows/macOS builds
5. **SConstruct Errors**: Incorrect Python syntax in SCons files
6. **Parts Framework**: Incorrect use of Parts API (Part(), DependsOn(), etc.)

For each issue, respond in EXACTLY this format:
ISSUE_START
SEVERITY: critical|warning|info
LINE: <line_number_or_0>
TITLE: <short_title>
DESCRIPTION: <detailed_description>
SUGGESTION: <how_to_fix>
CODE: <relevant_code_snippet>
ISSUE_END

If no build issues are found, respond with: NO_ISSUES_FOUND"""

# Known patterns that indicate build problems
BUILD_ISSUE_PATTERNS = [
    (r"version.*=.*['\"]0\.0\.0['\"]", "warning", "Placeholder version 0.0.0", "Component version set to 0.0.0 - this should be updated before push."),
    (r"#\s*(import|include).*commented\s*out", "info", "Commented-out import", "Commented-out import found - clean up if not needed."),
    (r"env\.Install.*\.\.\/\.\.", "warning", "Install to parent directory", "Installing to parent directory may affect other components."),
]


def build_compat_node(
    state: GuardianState,
    config: GuardianConfig,
    llm: Optional[BaseChatModel] = None,
) -> dict:
    """
    Check build file changes for compatibility issues.
    Focuses on SCons/Parts build system used by VTune.
    """
    console.print("  🏗️  [bold cyan]Node 3e:[/bold cyan] Checking build compatibility...")

    issues = []

    build_files = state.build_files
    if not build_files:
        console.print("    No build files changed.")
        return {"build_compat_issues": []}

    # Phase 1: Pattern-based checks
    for fc in build_files:
        if fc.change_type == "deleted" or not fc.diff_content:
            continue

        added_lines = [
            line[1:] for line in fc.diff_content.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        added_content = "\n".join(added_lines)

        for pattern, severity, title, description in BUILD_ISSUE_PATTERNS:
            if re.search(pattern, added_content, re.IGNORECASE):
                issues.append(Issue(
                    id=f"build-{uuid.uuid4().hex[:8]}",
                    severity=severity,
                    category="build_compat",
                    file_path=fc.file_path,
                    line_number=0,
                    title=title,
                    description=description,
                    suggestion=description,
                    source="build_compat",
                ))

    # Phase 2: LLM-based build review
    if llm and build_files:
        combined_diffs = "\n\n".join(
            f"=== {fc.file_path} ===\n{fc.diff_content[:3000]}"
            for fc in build_files
            if fc.diff_content and fc.change_type != "deleted"
        )

        if combined_diffs:
            try:
                messages = [
                    SystemMessage(content=BUILD_REVIEW_PROMPT),
                    HumanMessage(content=f"Build file changes:\n\n{combined_diffs}"),
                ]

                response = llm.invoke(messages)
                llm_issues = _parse_build_issues(response.content, build_files[0].file_path)
                issues.extend(llm_issues)

            except Exception as e:
                console.print(f"    [yellow]⚠ LLM build review error: {e}[/yellow]")

    console.print(f"    Found [bold]{len(issues)}[/bold] build compatibility issue(s)")

    return {"build_compat_issues": issues}


def _parse_build_issues(response: str, default_file: str) -> list[Issue]:
    """Parse LLM build review response into Issues."""
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

        issues.append(Issue(
            id=f"build-llm-{uuid.uuid4().hex[:8]}",
            severity=severity,
            category="build_compat",
            file_path=default_file,
            line_number=line_num,
            title=_extract_field(issue_text, "TITLE", "Build issue"),
            description=_extract_field(issue_text, "DESCRIPTION", "Potential build issue"),
            suggestion=_extract_field(issue_text, "SUGGESTION", "Review build configuration"),
            source="build_compat",
            code_snippet=_extract_field(issue_text, "CODE", ""),
        ))

    return issues


def _extract_field(text: str, field_name: str, default: str = "") -> str:
    """Extract a field value from structured LLM response."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(f"{field_name}:"):
            return line[len(f"{field_name}:"):].strip()
    return default
