"""
VTune GuardianAI - Security Check Node
=========================================
Scans code changes for security vulnerabilities.
Uses pattern matching + LLM for comprehensive security analysis.
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

# ── Known Dangerous Patterns ──

DANGEROUS_C_PATTERNS = [
    (r'\bgets\s*\(', "critical", "Use of gets()", "gets() is inherently unsafe - no buffer boundary check. Use fgets() instead.", "gets(buffer)", "fgets(buffer, sizeof(buffer), stdin)"),
    (r'\bstrcpy\s*\(', "warning", "Use of strcpy()", "strcpy() can cause buffer overflow. Use strncpy() or strlcpy() instead.", "strcpy(dest, src)", "strncpy(dest, src, sizeof(dest) - 1); dest[sizeof(dest) - 1] = '\\0'"),
    (r'\bstrcat\s*\(', "warning", "Use of strcat()", "strcat() can cause buffer overflow. Use strncat() or strlcat() instead.", "strcat(dest, src)", "strncat(dest, src, sizeof(dest) - strlen(dest) - 1)"),
    (r'\bsprintf\s*\(', "warning", "Use of sprintf()", "sprintf() can cause buffer overflow. Use snprintf() instead.", "sprintf(buf, fmt, ...)", "snprintf(buf, sizeof(buf), fmt, ...)"),
    (r'\bscanf\s*\(\s*"[^"]*%s', "warning", "Unsafe scanf with %s", "scanf with %s has no length limit. Use %Ns with a max length.", 'scanf("%s", buf)', 'scanf("%63s", buf)  // limit to buffer size - 1'),
    (r'\bsystem\s*\(', "warning", "Use of system()", "system() can be exploited for command injection. Use exec family instead.", "system(cmd)", "execvp(args[0], args)  // use exec family with argument list"),
    (r'\bpopen\s*\(', "warning", "Use of popen()", "popen() can be exploited for command injection. Validate input carefully.", "popen(cmd, mode)", "// Validate and sanitize cmd, or use pipe()+fork()+exec()"),
    (r'\bexecl\s*\(.*\bgetenv\b', "critical", "Command exec with environment variable", "Using unvalidated environment variables in exec calls is dangerous.", "execl(getenv(\"SHELL\"), ...)", "// Validate environment variable before use:\nconst char* shell = getenv(\"SHELL\");\nif (shell && is_valid_path(shell)) execl(shell, ...)"),
    (r'#pragma\s+warning\s*\(\s*disable', "info", "Pragma warning disable", "Disabling compiler warnings may hide real issues.", "#pragma warning(disable: XXXX)", "// Fix the underlying warning instead of suppressing it"),
    (r'\bTODO\b.*\b(hack|workaround|fixme)\b', "info", "TODO/HACK marker", "Unresolved TODO/HACK found in changed code.", "// TODO: hack/workaround", "// Resolve the TODO before merging to mainline"),
]

DANGEROUS_PYTHON_PATTERNS = [
    (r'\beval\s*\(', "critical", "Use of eval()", "eval() executes arbitrary code. Use ast.literal_eval() for data parsing.", "eval(user_input)", "ast.literal_eval(user_input)"),
    (r'\bexec\s*\(', "critical", "Use of exec()", "exec() executes arbitrary code. Avoid if possible.", "exec(code_string)", "# Avoid exec(). Use a safe DSL, importlib, or predefined handlers"),
    (r'\bpickle\.loads?\s*\(', "warning", "Use of pickle.load()", "Unpickling untrusted data can execute arbitrary code. Use json instead.", "pickle.load(f)", "json.load(f)  # or use a safe serialization format"),
    (r'\byaml\.load\s*\((?!.*Loader)', "warning", "Unsafe yaml.load()", "yaml.load() without Loader param can execute code. Use yaml.safe_load().", "yaml.load(f)", "yaml.safe_load(f)"),
    (r'subprocess\..*shell\s*=\s*True', "warning", "Subprocess with shell=True", "shell=True enables shell injection. Use shell=False with argument list.", "subprocess.run(cmd, shell=True)", "subprocess.run(cmd.split(), shell=False)"),
    (r'\bos\.system\s*\(', "warning", "Use of os.system()", "os.system() is vulnerable to shell injection. Use subprocess instead.", "os.system(cmd)", "subprocess.run(cmd.split(), check=True)"),
    (r'(password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', "critical", "Hardcoded credential", "Hardcoded credentials detected. Use environment variables or secrets manager.", 'API_KEY = "hardcoded_value"', 'API_KEY = os.environ.get("API_KEY")'),
    (r'\b__import__\s*\(', "warning", "Dynamic import with __import__", "Dynamic imports can be exploited. Use importlib if necessary.", "__import__(module_name)", "importlib.import_module(module_name)"),
]

SECURITY_REVIEW_PROMPT = """You are a security expert reviewing code changes for Intel VTune Profiler.
Analyze the following diff for security vulnerabilities.

Focus on:
1. **Injection Attacks**: SQL injection, command injection, code injection
2. **Buffer Issues**: Buffer overflows, format string vulnerabilities
3. **Authentication/Authorization**: Weak auth, missing access checks
4. **Sensitive Data**: Hardcoded secrets, logging sensitive info, insecure storage
5. **Input Validation**: Missing or insufficient input validation
6. **Cryptography**: Weak algorithms, improper use of crypto
7. **Path Traversal**: Unsanitized file paths

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

If no security issues are found, respond with: NO_ISSUES_FOUND"""


def security_check_node(
    state: GuardianState,
    config: GuardianConfig,
    llm: Optional[BaseChatModel] = None,
) -> dict:
    """
    Scan code changes for security vulnerabilities using patterns + LLM.
    """
    console.print("  🔒 [bold cyan]Node 3d:[/bold cyan] Running security scan...")

    issues = []

    all_files = state.cpp_files + state.python_files + state.other_files

    # Phase 1: Pattern-based detection (fast, no LLM needed)
    for fc in all_files:
        if fc.change_type == "deleted" or not fc.diff_content:
            continue

        # Only check added lines
        added_lines = [
            line[1:] for line in fc.diff_content.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        added_content = "\n".join(added_lines)

        if fc.language in ("cpp", "c", "h", "hpp"):
            patterns = DANGEROUS_C_PATTERNS
        elif fc.language == "python":
            patterns = DANGEROUS_PYTHON_PATTERNS
        else:
            patterns = []

        for pattern, severity, title, description, bad_code, fix_code in patterns:
            matches = re.finditer(pattern, added_content, re.IGNORECASE)
            for match in matches:
                # Approximate line number
                line_num = added_content[:match.start()].count("\n") + 1

                issues.append(Issue(
                    id=f"security-{uuid.uuid4().hex[:8]}",
                    severity=severity,
                    category="security",
                    file_path=fc.file_path,
                    line_number=line_num,
                    title=title,
                    description=description,
                    suggestion=description,
                    source="security",
                    code_snippet=match.group(0),
                    fix_code_snippet=fix_code,
                ))

    # Phase 2: LLM-based security review (deeper analysis)
    if llm:
        for fc in all_files:
            if fc.change_type == "deleted" or not fc.diff_content:
                continue

            # Only do LLM security review for non-trivial changes
            if fc.lines_added < 5:
                continue

            try:
                messages = [
                    SystemMessage(content=SECURITY_REVIEW_PROMPT),
                    HumanMessage(
                        content=f"File: {fc.file_path} (Language: {fc.language})\n\nDiff:\n```\n{fc.diff_content[:6000]}\n```"
                    ),
                ]

                response = llm.invoke(messages)
                llm_issues = _parse_security_issues(response.content, fc.file_path)
                issues.extend(llm_issues)

            except Exception as e:
                console.print(f"    [yellow]⚠ LLM security review error for {fc.file_path}: {e}[/yellow]")

    console.print(f"    Found [bold]{len(issues)}[/bold] security issue(s)")

    return {"security_issues": issues}


def security_pattern_scan(
    state: GuardianState,
    config: GuardianConfig,
) -> dict:
    """
    Fast regex-only security pattern scan — no LLM calls.
    Used by the optimized combined-analysis graph.
    """
    console.print("  🔒 [bold cyan]Security Patterns:[/bold cyan] Fast regex scan...")

    issues = []
    all_files = state.cpp_files + state.python_files + state.other_files

    for fc in all_files:
        if fc.change_type == "deleted" or not fc.diff_content:
            continue

        added_lines = [
            line[1:] for line in fc.diff_content.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        added_content = "\n".join(added_lines)

        if fc.language in ("cpp", "c", "h", "hpp"):
            patterns = DANGEROUS_C_PATTERNS
        elif fc.language == "python":
            patterns = DANGEROUS_PYTHON_PATTERNS
        else:
            patterns = []

        for pattern, severity, title, description, bad_code, fix_code in patterns:
            matches = re.finditer(pattern, added_content, re.IGNORECASE)
            for match in matches:
                line_num = added_content[:match.start()].count("\n") + 1

                issues.append(Issue(
                    id=f"security-{uuid.uuid4().hex[:8]}",
                    severity=severity,
                    category="security",
                    file_path=fc.file_path,
                    line_number=line_num,
                    title=title,
                    description=description,
                    suggestion=description,
                    source="security",
                    code_snippet=match.group(0),
                    fix_code_snippet=fix_code,
                ))

    console.print(f"    Found [bold]{len(issues)}[/bold] pattern-based security issue(s)")
    return {"security_issues": issues}


def _parse_security_issues(response: str, file_path: str) -> list[Issue]:
    """Parse LLM security response into Issues."""
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
            id=f"security-llm-{uuid.uuid4().hex[:8]}",
            severity=severity,
            category="security",
            file_path=file_path,
            line_number=line_num,
            title=_extract_field(issue_text, "TITLE", "Security issue"),
            description=_extract_field(issue_text, "DESCRIPTION", "Potential security issue"),
            suggestion=_extract_field(issue_text, "SUGGESTION", "Review for security"),
            source="security",
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
