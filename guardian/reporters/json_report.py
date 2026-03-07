"""
VTune GuardianAI - JSON Reporter
===================================
Generates JSON report files for CI/CD integration.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.console import Console

console = Console()


class JsonReporter:
    """Generates JSON report files."""

    def generate(self, result: dict, output_path: str | None = None) -> str:
        """
        Generate a JSON report.

        Args:
            result: Analysis results dict.
            output_path: Optional output file path. Defaults to reports/guardian-report-<timestamp>.json

        Returns:
            Path to the generated report file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        report = {
            "tool": "VTune GuardianAI",
            "version": "0.1.0",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_files_changed": result.get("total_files_changed", 0),
                "total_issues": result.get("total_issues", 0),
                "critical_count": result.get("critical_count", 0),
                "warning_count": result.get("warning_count", 0),
                "info_count": result.get("info_count", 0),
                "decision": result.get("decision", "pass"),
                "decision_reason": result.get("decision_reason", ""),
            },
            "issues": self._serialize_issues(result.get("all_issues", [])),
            "issues_by_source": {
                "static_analysis": self._serialize_issues(result.get("static_analysis_issues", [])),
                "memory_leak": self._serialize_issues(result.get("memory_leak_issues", [])),
                "ai_review": self._serialize_issues(result.get("ai_review_issues", [])),
                "security": self._serialize_issues(result.get("security_issues", [])),
                "build_compat": self._serialize_issues(result.get("build_compat_issues", [])),
                "best_practice": self._serialize_issues(result.get("best_practice_issues", [])),
            },
            "errors": result.get("errors", []),
        }

        # Determine output path
        if not output_path:
            reports_dir = Path("reports")
            reports_dir.mkdir(exist_ok=True)
            output_path = str(reports_dir / f"guardian-report-{timestamp}.json")

        # Write report
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        console.print(f"\n  📄 JSON report saved to: [bold]{output_path}[/bold]")
        return output_path

    def _serialize_issues(self, issues: list) -> list[dict]:
        """Convert issues to serializable dicts."""
        serialized = []
        for issue in issues:
            if hasattr(issue, "model_dump"):
                serialized.append(issue.model_dump())
            elif hasattr(issue, "__dict__"):
                serialized.append(issue.__dict__)
            elif isinstance(issue, dict):
                serialized.append(issue)
        return serialized
