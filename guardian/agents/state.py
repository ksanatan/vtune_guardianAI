"""
VTune GuardianAI - Agent State Definitions
============================================
Defines the state schema for the LangGraph agent workflow.
All nodes read from and write to this shared state.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, List
from dataclasses import dataclass, field

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class FileChange(BaseModel):
    """Represents a single file change from git diff."""
    file_path: str = Field(description="Path to the changed file")
    change_type: str = Field(description="Type of change: added, modified, deleted, renamed")
    diff_content: str = Field(default="", description="The actual diff content")
    language: str = Field(default="unknown", description="Detected programming language")
    lines_added: int = Field(default=0, description="Number of lines added")
    lines_deleted: int = Field(default=0, description="Number of lines deleted")


class Issue(BaseModel):
    """Represents a single issue found during analysis."""
    id: str = Field(description="Unique issue identifier")
    severity: str = Field(description="Severity: critical, warning, info")
    category: str = Field(description="Category: bug, memory_leak, security, style, build_compat, best_practice")
    file_path: str = Field(default="", description="File where the issue was found")
    line_number: int = Field(default=0, description="Line number of the issue")
    title: str = Field(description="Short title of the issue")
    description: str = Field(description="Detailed description of the issue")
    suggestion: str = Field(default="", description="Suggested fix")
    source: str = Field(default="", description="Which analysis node found this: static, memory, ai, security, build, bestpractice")
    code_snippet: str = Field(default="", description="Relevant code snippet showing the problematic code")
    fix_code_snippet: str = Field(default="", description="Suggested fix as actual code that can replace the problematic code")


class GuardianState(BaseModel):
    """
    Central state for the VTune GuardianAI LangGraph workflow.

    This state is shared across all nodes in the graph. Each node reads
    what it needs and writes its results back to the state.
    """

    # ── Input ──
    repo_path: str = Field(default="", description="Path to the git repository")
    scan_all: bool = Field(default=False, description="Scan all changes vs staged only")
    verbose: bool = Field(default=False, description="Enable verbose logging")

    # ── Git Diff Node Output ──
    file_changes: list[FileChange] = Field(default_factory=list, description="List of file changes from git diff")
    total_files_changed: int = Field(default=0, description="Total number of files changed")
    has_cpp_changes: bool = Field(default=False, description="Whether C/C++ files were changed")
    has_python_changes: bool = Field(default=False, description="Whether Python files were changed")
    has_scons_changes: bool = Field(default=False, description="Whether SCons/build files were changed")

    # ── File Classifier Node Output ──
    cpp_files: list[FileChange] = Field(default_factory=list, description="C/C++ file changes")
    python_files: list[FileChange] = Field(default_factory=list, description="Python file changes")
    build_files: list[FileChange] = Field(default_factory=list, description="Build/SCons file changes")
    other_files: list[FileChange] = Field(default_factory=list, description="Other file changes")

    # ── Analysis Node Outputs (Annotated with reducer for parallel writes) ──
    static_analysis_issues: Annotated[list[Issue], operator.add] = Field(default_factory=list, description="Issues from static analysis")
    memory_leak_issues: Annotated[list[Issue], operator.add] = Field(default_factory=list, description="Issues from memory leak detection")
    ai_review_issues: Annotated[list[Issue], operator.add] = Field(default_factory=list, description="Issues from AI code review")
    security_issues: Annotated[list[Issue], operator.add] = Field(default_factory=list, description="Issues from security scan")
    build_compat_issues: Annotated[list[Issue], operator.add] = Field(default_factory=list, description="Issues from build compatibility")
    best_practice_issues: Annotated[list[Issue], operator.add] = Field(default_factory=list, description="Issues from best practices")

    # ── Aggregated Results ──
    all_issues: list[Issue] = Field(default_factory=list, description="All issues combined")
    total_issues: int = Field(default=0, description="Total issue count")
    critical_count: int = Field(default=0, description="Critical issue count")
    warning_count: int = Field(default=0, description="Warning issue count")
    info_count: int = Field(default=0, description="Info issue count")

    # ── Decision ──
    decision: str = Field(default="pass", description="Final decision: block, warn, pass")
    decision_reason: str = Field(default="", description="Reason for the decision")

    # ── Errors ──
    errors: list[str] = Field(default_factory=list, description="Errors encountered during analysis")
