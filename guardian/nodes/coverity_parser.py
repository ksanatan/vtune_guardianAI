"""
VTune GuardianAI - Coverity CSV/JSON Parser
=============================================
Parses Coverity defect exports (CSV from Coverity Connect or JSON from cov-format-errors)
into structured defects that can be fed to the fix pipeline.

Supported formats:
- Coverity Connect CSV export (View > Export)
- cov-format-errors --json output
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CoverityDefect:
    """A single Coverity defect parsed from export data."""
    cid: int                      # Coverity Issue ID
    checker: str                  # e.g., "RESOURCE_LEAK", "NULL_RETURNS"
    file_path: str                # Relative file path
    line_number: int              # 1-based line number
    function: str = ""            # Enclosing function name
    description: str = ""         # Human-readable description
    severity: str = ""            # High / Medium / Low
    category: str = ""            # Quality / Security / etc.
    action: str = ""              # Triaged action (Fix, Ignore, etc.)
    status: str = ""              # New, Triaged, Fixed, etc.
    owner: str = ""               # Assigned owner


# Map common Coverity checkers to human-readable issue descriptions
CHECKER_MAP: dict[str, str] = {
    # Resource management
    "RESOURCE_LEAK": "Resource leak: allocated resource not freed on all paths",
    "USE_AFTER_FREE": "Use of memory/resource after it has been freed",
    "DOUBLE_FREE": "Resource freed more than once",
    "OVERRUN": "Buffer overrun: write past end of buffer",
    "UNINIT": "Use of uninitialized variable",
    "UNINIT_CTOR": "Constructor does not initialize all fields",
    # Null pointer
    "NULL_RETURNS": "Dereferencing value that may be NULL (from function return)",
    "FORWARD_NULL": "Null pointer passed forward and dereferenced later",
    "REVERSE_INULL": "Null check after dereference (implies possible null deref above)",
    "CHECKED_RETURN": "Return value of function not checked for error",
    # Concurrency
    "LOCK": "Locking/unlocking issue (deadlock, double-lock, missing lock)",
    "MISSING_LOCK": "Accessing shared data without holding the required lock",
    "DATA_RACE": "Potential data race on shared resource",
    "ORDER_REVERSAL": "Lock order reversal may cause deadlock",
    # Logic
    "DEADCODE": "Code that can never be reached",
    "CONSTANT_EXPRESSION_RESULT": "Expression always evaluates to same constant",
    "COPY_PASTE_ERROR": "Possible copy-paste bug (repeated pattern with error)",
    "IDENTICAL_BRANCHES": "Both branches of conditional have identical code",
    # Integer
    "INTEGER_OVERFLOW": "Arithmetic operation may overflow",
    "NEGATIVE_RETURNS": "Signed value may be negative when unsigned expected",
    "TAINTED_SCALAR": "Externally controlled value used without validation",
    # Security
    "TAINTED_STRING": "Externally controlled string used without sanitization",
    "SQL_INJECTION": "SQL query built from unsanitized external input",
    "PATH_MANIPULATION": "File path built from unsanitized external input",
    "HARDCODED_CREDENTIALS": "Credentials hardcoded in source code",
    # C++ specific
    "CTOR_DTOR_LEAK": "Leak in constructor/destructor path",
    "VIRTUAL_DTOR": "Non-virtual destructor in base class with virtual methods",
    "BAD_OVERRIDE": "Method signature doesn't properly override base class virtual",
    "INVALIDATE_ITERATOR": "Using iterator after container has been modified",
    # Python specific
    "PY.MISSING_RETURN": "Function missing return statement on some path",
    "PY.NONE_CHECK": "Possible use of None without check",
    "PY.TYPE_MISMATCH": "Type mismatch in function call",
}


def get_issue_description(checker: str, raw_description: str = "") -> str:
    """Get a human-readable issue description for a Coverity checker."""
    if checker in CHECKER_MAP:
        return CHECKER_MAP[checker]
    if raw_description:
        return raw_description
    return checker.replace("_", " ").title()


def parse_coverity_csv(csv_path: str, repo_root: Optional[str] = None) -> list[CoverityDefect]:
    """
    Parse a Coverity Connect CSV export.

    Coverity CSV exports typically have columns like:
        CID, Checker, File, Function, Description, Severity, Action, ...

    The exact column names vary by Coverity Connect version and export configuration.
    This parser handles common variations.

    Args:
        csv_path: Path to the CSV file.
        repo_root: If provided, file paths are made relative to this root.

    Returns:
        List of CoverityDefect objects.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    defects: list[CoverityDefect] = []

    with open(path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    lines = content.splitlines()
    header_idx = _find_header_line(lines)
    if header_idx < 0:
        raise ValueError(
            f"Cannot find CSV header in {csv_path}. "
            "Expected columns like 'CID', 'Checker', 'File' etc."
        )

    csv_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(csv_text.splitlines())

    for row in reader:
        normalized = {k.strip().lower(): v.strip() for k, v in row.items() if k}
        defect = _parse_csv_row(normalized, repo_root)
        if defect:
            defects.append(defect)

    return defects


def parse_coverity_json(json_path: str, repo_root: Optional[str] = None) -> list[CoverityDefect]:
    """
    Parse cov-format-errors JSON output.

    Args:
        json_path: Path to the JSON file.
        repo_root: If provided, file paths are made relative to this root.

    Returns:
        List of CoverityDefect objects.
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    defects: list[CoverityDefect] = []
    issues = data.get("issues", data.get("rows", []))

    for idx, issue in enumerate(issues):
        try:
            checker = issue.get("checkerName", issue.get("checker", "UNKNOWN"))
            file_path = issue.get(
                "mainEventFilePathname",
                issue.get("strippedMainEventFilePathname", issue.get("file", "")),
            )
            line = int(issue.get("mainEventLineNumber", issue.get("lineNumber", issue.get("line", 0))))
            function = issue.get("functionDisplayName", issue.get("function", ""))
            cid = int(issue.get("cid", issue.get("CID", idx + 1)))

            if not file_path or line == 0:
                continue

            if repo_root:
                file_path = _make_relative(file_path, repo_root)

            description = get_issue_description(checker, issue.get("displayType", ""))

            defects.append(CoverityDefect(
                cid=cid,
                checker=checker,
                file_path=file_path,
                line_number=line,
                function=function,
                description=description,
                severity=issue.get("displayImpact", issue.get("severity", "")),
                category=issue.get("displayCategory", issue.get("category", "")),
            ))
        except (ValueError, KeyError, TypeError):
            continue

    return defects


def _find_header_line(lines: list[str]) -> int:
    """Find the line index that looks like a CSV header."""
    for i, line in enumerate(lines):
        lower = line.lower()
        if ("cid" in lower) and ("checker" in lower or "file" in lower):
            return i
        if "checker" in lower and "file" in lower and "line" in lower:
            return i
    return -1


def _parse_csv_row(row: dict[str, str], repo_root: Optional[str]) -> Optional[CoverityDefect]:
    """Parse a single normalized CSV row into a CoverityDefect."""
    cid_str = row.get("cid", row.get("issue key", row.get("defect id", "0")))
    try:
        cid = int(re.sub(r"[^\d]", "", cid_str)) if cid_str else 0
    except ValueError:
        cid = 0

    checker = row.get("checker", row.get("checker name", row.get("type", "")))
    if not checker:
        return None

    file_path = row.get("file", row.get("file path", row.get("location", "")))
    if not file_path:
        return None

    line_str = row.get("line", row.get("line number", row.get("linenum", "0")))
    try:
        line_number = int(re.sub(r"[^\d]", "", line_str)) if line_str else 0
    except ValueError:
        line_number = 0
    if line_number == 0:
        return None

    if repo_root:
        file_path = _make_relative(file_path, repo_root)

    function = row.get("function", row.get("function name", ""))
    severity = row.get("severity", row.get("impact", ""))
    category = row.get("category", row.get("classification", ""))
    action = row.get("action", row.get("triage", ""))
    status = row.get("status", row.get("state", ""))
    owner = row.get("owner", row.get("assigned to", ""))
    raw_desc = row.get("description", row.get("comment", ""))

    description = get_issue_description(checker, raw_desc)

    return CoverityDefect(
        cid=cid,
        checker=checker,
        file_path=file_path,
        line_number=line_number,
        function=function,
        description=description,
        severity=severity,
        category=category,
        action=action,
        status=status,
        owner=owner,
    )


def _make_relative(file_path: str, repo_root: str) -> str:
    """Attempt to make an absolute path relative to repo_root."""
    try:
        fp = Path(file_path)
        rr = Path(repo_root)
        if fp.is_absolute():
            return str(fp.relative_to(rr))
    except (ValueError, TypeError):
        pass
    return file_path
