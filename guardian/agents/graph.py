"""
VTune GuardianAI - LangGraph Agent Workflow
=============================================
Defines the main LangGraph graph that orchestrates all analysis nodes.

Flow:
  git_diff → file_classifier → [static_analysis, combined_ai, security_patterns, build_compat]
                              → aggregator → decision → END

OPTIMIZED: All 4 LLM analyses (memory, review, security-deep, best practices)
merged into ONE single LLM call to minimize CPU inference time.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import StateGraph, START, END
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from guardian.config import GuardianConfig
from guardian.agents.state import GuardianState

console = Console()


def _build_graph(config: GuardianConfig) -> StateGraph:
    """
    Build the LangGraph workflow for VTune GuardianAI.

    OPTIMIZED graph structure:
        START → git_diff → file_classifier → analysis_router
            → static_analysis     (cppcheck/clang-tidy, no LLM)
            → combined_ai         (ONE LLM call: memory + review + security + best practices)
            → security_patterns   (regex patterns only, no LLM)
            → build_compat        (LLM, only if build files changed)
        → aggregator → decision → END
    """
    from guardian.nodes.git_diff import git_diff_node
    from guardian.nodes.file_classifier import file_classifier_node
    from guardian.nodes.static_analysis import static_analysis_node
    from guardian.nodes.combined_analysis import combined_analysis_node
    from guardian.nodes.security_check import security_pattern_scan
    from guardian.nodes.build_compat import build_compat_node

    from guardian.llm.provider import get_llm

    # Create LLM instance
    llm = None
    try:
        llm = get_llm(config)
    except Exception as e:
        console.print(f"  [yellow]⚠ LLM initialization warning:[/yellow] {e}")
        console.print(f"  [yellow]  AI-based analysis will be limited.[/yellow]")

    # ── Define Nodes ──

    def node_git_diff(state: GuardianState) -> dict:
        return git_diff_node(state, config)

    def node_file_classifier(state: GuardianState) -> dict:
        return file_classifier_node(state, config)

    def node_static_analysis(state: GuardianState) -> dict:
        if config.enable_static_analysis and state.has_cpp_changes:
            return static_analysis_node(state, config)
        return {}

    def node_combined_ai(state: GuardianState) -> dict:
        """Single LLM call covering memory, review, security, and best practices."""
        if llm:
            return combined_analysis_node(state, config, llm)
        return {}

    def node_security_patterns(state: GuardianState) -> dict:
        """Fast regex-based security pattern scan (no LLM)."""
        if config.enable_security_check:
            return security_pattern_scan(state, config)
        return {}

    def node_build_compat(state: GuardianState) -> dict:
        if config.enable_build_compat_check and state.has_scons_changes:
            return build_compat_node(state, config, llm)
        return {}

    def node_aggregator(state: GuardianState) -> dict:
        """Combine all issues from all analysis nodes."""
        all_issues = (
            state.static_analysis_issues
            + state.memory_leak_issues
            + state.ai_review_issues
            + state.security_issues
            + state.build_compat_issues
            + state.best_practice_issues
        )

        # Deduplicate based on file+line+title
        seen = set()
        unique_issues = []
        for issue in all_issues:
            key = (issue.file_path, issue.line_number, issue.title)
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        critical = sum(1 for i in unique_issues if i.severity == "critical")
        warning = sum(1 for i in unique_issues if i.severity == "warning")
        info = sum(1 for i in unique_issues if i.severity == "info")

        return {
            "all_issues": unique_issues,
            "total_issues": len(unique_issues),
            "critical_count": critical,
            "warning_count": warning,
            "info_count": info,
        }

    def node_decision(state: GuardianState) -> dict:
        """Make final push decision based on severity."""
        if state.critical_count > 0:
            return {
                "decision": "block",
                "decision_reason": (
                    f"Found {state.critical_count} critical issue(s). "
                    f"Push should be blocked until critical issues are resolved."
                ),
            }
        elif state.warning_count > 0:
            return {
                "decision": "warn",
                "decision_reason": (
                    f"Found {state.warning_count} warning(s). "
                    f"Review recommended before pushing."
                ),
            }
        else:
            return {
                "decision": "pass",
                "decision_reason": "No significant issues found. Safe to push.",
            }

    # ── Build the Graph ──

    graph = StateGraph(GuardianState)

    # Add nodes
    graph.add_node("git_diff", node_git_diff)
    graph.add_node("file_classifier", node_file_classifier)
    graph.add_node("static_analysis", node_static_analysis)
    graph.add_node("combined_ai", node_combined_ai)
    graph.add_node("security_patterns", node_security_patterns)
    graph.add_node("build_compat", node_build_compat)
    graph.add_node("aggregator", node_aggregator)
    graph.add_node("decision", node_decision)

    # Define edges: START → git_diff → file_classifier
    graph.add_edge(START, "git_diff")
    graph.add_edge("git_diff", "file_classifier")

    # file_classifier → analysis nodes (fan-out)
    graph.add_edge("file_classifier", "static_analysis")
    graph.add_edge("file_classifier", "combined_ai")
    graph.add_edge("file_classifier", "security_patterns")
    graph.add_edge("file_classifier", "build_compat")

    # All analysis nodes → aggregator (fan-in)
    graph.add_edge("static_analysis", "aggregator")
    graph.add_edge("combined_ai", "aggregator")
    graph.add_edge("security_patterns", "aggregator")
    graph.add_edge("build_compat", "aggregator")

    # aggregator → decision → END
    graph.add_edge("aggregator", "decision")
    graph.add_edge("decision", END)

    return graph


def run_guardian_agent(config: GuardianConfig, scan_all: bool = False, verbose: bool = False) -> dict:
    """
    Run the VTune GuardianAI agent workflow.

    Args:
        config: GuardianConfig instance.
        scan_all: If True, scan all uncommitted changes. If False, staged only.
        verbose: Enable verbose output.

    Returns:
        Dictionary with analysis results.
    """
    console.print("  🏗️  Building analysis pipeline...")

    graph = _build_graph(config)
    app = graph.compile()

    # Initial state
    initial_state = GuardianState(
        repo_path=config.vtune_repo_path,
        scan_all=scan_all,
        verbose=verbose,
    )

    console.print("  🚀 Running analysis...\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing code changes...", total=None)

        # Run the graph
        final_state = app.invoke(initial_state.model_dump())

        progress.update(task, description="Analysis complete!", completed=True)

    # Convert to result dict for reporters
    return {
        "file_changes": final_state.get("file_changes", []),
        "total_files_changed": final_state.get("total_files_changed", 0),
        "all_issues": final_state.get("all_issues", []),
        "total_issues": final_state.get("total_issues", 0),
        "critical_count": final_state.get("critical_count", 0),
        "warning_count": final_state.get("warning_count", 0),
        "info_count": final_state.get("info_count", 0),
        "decision": final_state.get("decision", "pass"),
        "decision_reason": final_state.get("decision_reason", ""),
        "errors": final_state.get("errors", []),
        "static_analysis_issues": final_state.get("static_analysis_issues", []),
        "memory_leak_issues": final_state.get("memory_leak_issues", []),
        "ai_review_issues": final_state.get("ai_review_issues", []),
        "security_issues": final_state.get("security_issues", []),
        "build_compat_issues": final_state.get("build_compat_issues", []),
        "best_practice_issues": final_state.get("best_practice_issues", []),
    }
