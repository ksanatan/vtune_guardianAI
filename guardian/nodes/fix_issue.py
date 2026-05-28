"""
VTune GuardianAI - Fix Issue Node
====================================
Takes a specific defect (file + line + issue type) and generates
a minimal, precise fix using LLM analysis of the surrounding code.

Supports: C/C++, Python, Java, Go, Rust, and any text-based source file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from rich.console import Console

console = Console()


@dataclass
class FixResult:
    """Result of a fix attempt."""
    success: bool
    file_path: str
    line_number: int
    issue_type: str
    original_code: str = ""
    fixed_code: str = ""
    explanation: str = ""
    error: str = ""
    start_line: int = 0
    end_line: int = 0


# ── Prompt templates ──

FIX_SYSTEM_PROMPT = """You are a senior software engineer specializing in static analysis defect remediation.
Your job is to fix ONE specific defect with a MINIMAL code change.

Rules:
1. Fix ONLY the reported defect — do not refactor, rename, or "improve" anything else.
2. Preserve the existing coding style exactly (indentation, braces, naming).
3. The fix must compile and not introduce new warnings.
4. If the fix requires adding a null check, use the project's existing patterns (e.g., if the codebase uses early-return, use early-return).
5. Do NOT add comments like "// Fixed by AI" — just fix the code silently.
6. If the defect cannot be safely fixed without more context, say CANNOT_FIX and explain why.

Respond in EXACTLY this format:

ORIGINAL:
```
<the exact source lines that need to change — copy them verbatim from the input>
```
FIXED:
```
<the corrected version of those same lines>
```
EXPLANATION: <one sentence explaining what was wrong and how you fixed it>

If you cannot fix it:
CANNOT_FIX: <reason>
"""


def _build_fix_prompt(
    file_path: str,
    line_number: int,
    issue_type: str,
    source_context: str,
    language: str,
    start_line: int,
    end_line: int,
) -> str:
    """Build the human message for the fix prompt."""
    return (
        f"Defect Type: {issue_type}\n"
        f"File: {file_path} (Language: {language})\n"
        f"Reported at line: {line_number}\n"
        f"Context shown: lines {start_line}–{end_line}\n"
        f"\nSource code:\n```{language}\n{source_context}\n```\n"
        f"\nFix the '{issue_type}' defect at line {line_number}. "
        f"Return ONLY the minimal lines that need to change."
    )


def fix_single_issue(
    repo_path: str,
    file_path: str,
    line_number: int,
    issue_type: str,
    llm: BaseChatModel,
    context_lines: int = 30,
) -> FixResult:
    """
    Generate a fix for a single defect.

    Args:
        repo_path: Root of the repository.
        file_path: Relative path to the file containing the defect.
        line_number: 1-based line number of the defect.
        issue_type: Human-readable defect description (e.g., "Using invalid iterator").
        llm: LangChain-compatible chat model.
        context_lines: Number of lines before/after the defect to include as context.

    Returns:
        FixResult with original/fixed code blocks, or error info.
    """
    full_path = Path(repo_path) / file_path
    if not full_path.exists():
        return FixResult(
            success=False, file_path=file_path, line_number=line_number,
            issue_type=issue_type, error=f"File not found: {file_path}",
        )

    # Read source file
    try:
        all_lines = full_path.read_text(errors="ignore").splitlines()
    except Exception as e:
        return FixResult(
            success=False, file_path=file_path, line_number=line_number,
            issue_type=issue_type, error=f"Cannot read file: {e}",
        )

    total_lines = len(all_lines)
    if line_number < 1 or line_number > total_lines:
        return FixResult(
            success=False, file_path=file_path, line_number=line_number,
            issue_type=issue_type,
            error=f"Line {line_number} out of range (file has {total_lines} lines)",
        )

    # Extract context: ±context_lines around the defect
    start = max(0, line_number - 1 - context_lines)
    end = min(total_lines, line_number + context_lines)
    context_block = all_lines[start:end]

    # Add line numbers for LLM reference
    numbered_context = "\n".join(
        f"{i + start + 1:5d} | {line}"
        for i, line in enumerate(context_block)
    )

    # Detect language from extension
    language = _detect_lang(file_path)

    # Build and send prompt
    prompt = _build_fix_prompt(
        file_path=file_path,
        line_number=line_number,
        issue_type=issue_type,
        source_context=numbered_context,
        language=language,
        start_line=start + 1,
        end_line=end,
    )

    try:
        messages = [
            SystemMessage(content=FIX_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        response = llm.invoke(messages)
        return _parse_fix_response(response.content, file_path, line_number, issue_type, start + 1, end)

    except Exception as e:
        return FixResult(
            success=False, file_path=file_path, line_number=line_number,
            issue_type=issue_type, error=f"LLM error: {e}",
        )


def apply_fix(repo_path: str, fix_result: FixResult) -> tuple[bool, str]:
    """
    Apply a fix to the source file on disk.

    Finds the ORIGINAL block in the file and replaces it with FIXED block.
    Uses exact string matching — if the original block doesn't match, fails safely.

    Args:
        repo_path: Root of the repository.
        fix_result: A successful FixResult.

    Returns:
        Tuple of (success: bool, message: str).
    """
    if not fix_result.success:
        return False, f"Cannot apply failed fix: {fix_result.error}"

    full_path = Path(repo_path) / fix_result.file_path
    if not full_path.exists():
        return False, f"File not found: {fix_result.file_path}"

    try:
        content = full_path.read_text(errors="ignore")
    except Exception as e:
        return False, f"Cannot read file: {e}"

    original = fix_result.original_code.strip()
    fixed = fix_result.fixed_code.strip()

    if not original:
        return False, "Empty original code block — cannot apply"

    # Strip line numbers if present (LLM sometimes includes them)
    original_clean = _strip_line_numbers(original)
    fixed_clean = _strip_line_numbers(fixed)

    # Try exact match first
    if original_clean in content:
        new_content = content.replace(original_clean, fixed_clean, 1)
    else:
        # Try with whitespace normalization (trailing spaces etc.)
        original_normalized = _normalize_whitespace(original_clean)
        lines = content.splitlines()
        matched = False
        for i in range(len(lines)):
            # Try matching block starting at this line
            block_size = len(original_clean.splitlines())
            if i + block_size <= len(lines):
                candidate = "\n".join(lines[i:i + block_size])
                if _normalize_whitespace(candidate) == original_normalized:
                    lines[i:i + block_size] = fixed_clean.splitlines()
                    matched = True
                    break
        if not matched:
            return False, (
                "Could not find original code block in file. "
                "The code may have changed since analysis. Manual fix required."
            )
        new_content = "\n".join(lines)
        # Preserve final newline if original had one
        if content.endswith("\n") and not new_content.endswith("\n"):
            new_content += "\n"

    try:
        full_path.write_text(new_content)
        return True, f"Fix applied to {fix_result.file_path}"
    except Exception as e:
        return False, f"Cannot write file: {e}"


def _parse_fix_response(
    response: str,
    file_path: str,
    line_number: int,
    issue_type: str,
    start_line: int,
    end_line: int,
) -> FixResult:
    """Parse the LLM response into a FixResult."""

    # Check for CANNOT_FIX
    if "CANNOT_FIX" in response:
        reason_match = re.search(r"CANNOT_FIX[:\s]*(.*)", response, re.DOTALL)
        reason = reason_match.group(1).strip()[:200] if reason_match else "LLM cannot fix this issue"
        return FixResult(
            success=False, file_path=file_path, line_number=line_number,
            issue_type=issue_type, error=reason,
        )

    # Extract ORIGINAL block
    original_match = re.search(
        r"ORIGINAL:\s*```[^\n]*\n(.*?)```", response, re.DOTALL
    )
    if not original_match:
        return FixResult(
            success=False, file_path=file_path, line_number=line_number,
            issue_type=issue_type, error="Could not parse ORIGINAL block from LLM response",
        )

    # Extract FIXED block
    fixed_match = re.search(
        r"FIXED:\s*```[^\n]*\n(.*?)```", response, re.DOTALL
    )
    if not fixed_match:
        return FixResult(
            success=False, file_path=file_path, line_number=line_number,
            issue_type=issue_type, error="Could not parse FIXED block from LLM response",
        )

    # Extract explanation
    explanation_match = re.search(r"EXPLANATION:\s*(.*?)(?:\n|$)", response)
    explanation = explanation_match.group(1).strip() if explanation_match else ""

    original_code = original_match.group(1).rstrip()
    fixed_code = fixed_match.group(1).rstrip()

    if not original_code or not fixed_code:
        return FixResult(
            success=False, file_path=file_path, line_number=line_number,
            issue_type=issue_type, error="Empty code blocks in LLM response",
        )

    return FixResult(
        success=True,
        file_path=file_path,
        line_number=line_number,
        issue_type=issue_type,
        original_code=original_code,
        fixed_code=fixed_code,
        explanation=explanation,
        start_line=start_line,
        end_line=end_line,
    )


def _strip_line_numbers(code: str) -> str:
    """Remove line number prefixes like '  123 | ' from code lines."""
    lines = code.splitlines()
    stripped = []
    for line in lines:
        match = re.match(r"^\s*\d+\s*\|\s?", line)
        if match:
            stripped.append(line[match.end():])
        else:
            stripped.append(line)
    return "\n".join(stripped)


def _normalize_whitespace(text: str) -> str:
    """Normalize trailing whitespace for comparison."""
    return "\n".join(line.rstrip() for line in text.splitlines())


def _detect_lang(file_path: str) -> str:
    """Detect language name for prompts."""
    ext_map = {
        ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".c": "c",
        ".h": "cpp", ".hpp": "cpp", ".hxx": "cpp",
        ".py": "python", ".pyw": "python",
        ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
        ".java": "java", ".rs": "rust", ".go": "go",
        ".rb": "ruby", ".swift": "swift", ".kt": "kotlin",
        ".cs": "csharp", ".scala": "scala",
        ".sh": "bash", ".bash": "bash", ".zsh": "zsh",
        ".cmake": "cmake", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".xml": "xml", ".sql": "sql",
    }
    ext = Path(file_path).suffix.lower()
    name = Path(file_path).name

    if name in ("SConstruct", "SConscript"):
        return "python"
    if name == "Makefile":
        return "makefile"
    if name == "CMakeLists.txt":
        return "cmake"
    if name.endswith(".parts"):
        return "python"

    return ext_map.get(ext, "text")
