"""
VTune GuardianAI - HTML Reporter
===================================
Generates beautiful HTML report files.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console

console = Console()

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VTune GuardianAI Report</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #1a1f36, #0a2540); border-radius: 12px; padding: 32px; margin-bottom: 24px; border: 1px solid #30363d; }
        .header h1 { color: #58a6ff; font-size: 28px; margin-bottom: 8px; }
        .header p { color: #8b949e; font-size: 14px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background: #161b22; border-radius: 8px; padding: 20px; border: 1px solid #30363d; text-align: center; }
        .card .number { font-size: 36px; font-weight: bold; }
        .card .label { color: #8b949e; font-size: 12px; text-transform: uppercase; margin-top: 4px; }
        .critical .number { color: #f85149; }
        .warning .number { color: #d29922; }
        .info .number { color: #58a6ff; }
        .pass .number { color: #3fb950; }
        .decision { padding: 16px 24px; border-radius: 8px; margin-bottom: 24px; font-size: 18px; font-weight: bold; text-align: center; }
        .decision.block { background: rgba(248,81,73,0.1); border: 2px solid #f85149; color: #f85149; }
        .decision.warn { background: rgba(210,153,34,0.1); border: 2px solid #d29922; color: #d29922; }
        .decision.pass-decision { background: rgba(63,185,80,0.1); border: 2px solid #3fb950; color: #3fb950; }
        .issues-section { margin-bottom: 24px; }
        .issues-section h2 { color: #c9d1d9; font-size: 20px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #30363d; }
        .issue { background: #161b22; border-radius: 8px; padding: 16px; margin-bottom: 8px; border-left: 4px solid; }
        .issue.critical { border-left-color: #f85149; }
        .issue.warning { border-left-color: #d29922; }
        .issue.info { border-left-color: #58a6ff; }
        .issue .issue-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .issue .issue-title { font-weight: bold; color: #c9d1d9; }
        .issue .badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
        .badge.critical { background: rgba(248,81,73,0.2); color: #f85149; }
        .badge.warning { background: rgba(210,153,34,0.2); color: #d29922; }
        .badge.info { background: rgba(88,166,255,0.2); color: #58a6ff; }
        .issue .meta { color: #8b949e; font-size: 12px; margin-bottom: 6px; }
        .issue .description { color: #b1bac4; font-size: 14px; line-height: 1.5; }
        .issue .suggestion { color: #3fb950; font-size: 13px; margin-top: 6px; }
        .code-block { margin: 10px 0; border-radius: 6px; overflow-x: auto; }
        .code-block-header { font-size: 12px; font-weight: bold; padding: 6px 12px; border-radius: 6px 6px 0 0; }
        .code-block-header.bad { background: rgba(248,81,73,0.15); color: #f85149; }
        .code-block-header.fix { background: rgba(63,185,80,0.15); color: #3fb950; }
        .code-block pre { margin: 0; padding: 12px 16px; background: #0d1117; border: 1px solid #30363d; border-radius: 0 0 6px 6px; font-family: 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace; font-size: 13px; line-height: 1.5; overflow-x: auto; white-space: pre; color: #c9d1d9; }
        .footer { text-align: center; color: #484f58; font-size: 12px; margin-top: 32px; padding-top: 16px; border-top: 1px solid #21262d; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛡️ VTune GuardianAI Report</h1>
            <p>Generated: {{timestamp}} | Files Analyzed: {{total_files}}</p>
        </div>

        <div class="decision {{decision_class}}">
            {{decision_text}}
        </div>

        <div class="summary">
            <div class="card"><div class="number">{{total_files}}</div><div class="label">Files Changed</div></div>
            <div class="card"><div class="number">{{total_issues}}</div><div class="label">Total Issues</div></div>
            <div class="card critical"><div class="number">{{critical}}</div><div class="label">Critical</div></div>
            <div class="card warning"><div class="number">{{warnings}}</div><div class="label">Warnings</div></div>
            <div class="card info"><div class="number">{{infos}}</div><div class="label">Info</div></div>
        </div>

        {{issues_html}}

        <div class="footer">
            VTune GuardianAI v0.1.0 | AI-Powered Pre-Push Code Guardian for Intel VTune
        </div>
    </div>
</body>
</html>"""


class HtmlReporter:
    """Generates HTML report files."""

    def generate(self, result: dict, output_path: str | None = None) -> str:
        """
        Generate an HTML report.

        Args:
            result: Analysis results dict.
            output_path: Optional output file path.

        Returns:
            Path to the generated report file.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        decision = result.get("decision", "pass")
        decision_map = {
            "block": ("block", "🚫 PUSH BLOCKED — Critical issues found"),
            "warn": ("warn", "⚠️ PUSH WITH CAUTION — Warnings found"),
            "pass": ("pass-decision", "✅ ALL CLEAR — Safe to push"),
        }
        decision_class, decision_text = decision_map.get(decision, ("pass-decision", "✅ PASS"))

        # Build issues HTML
        all_issues = result.get("all_issues", [])
        issues_html = self._build_issues_html(all_issues)

        # Fill template
        html = HTML_TEMPLATE
        html = html.replace("{{timestamp}}", timestamp)
        html = html.replace("{{total_files}}", str(result.get("total_files_changed", 0)))
        html = html.replace("{{total_issues}}", str(result.get("total_issues", 0)))
        html = html.replace("{{critical}}", str(result.get("critical_count", 0)))
        html = html.replace("{{warnings}}", str(result.get("warning_count", 0)))
        html = html.replace("{{infos}}", str(result.get("info_count", 0)))
        html = html.replace("{{decision_class}}", decision_class)
        html = html.replace("{{decision_text}}", decision_text)
        html = html.replace("{{issues_html}}", issues_html)

        # Write report
        if not output_path:
            reports_dir = Path("reports")
            reports_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(reports_dir / f"guardian-report-{ts}.html")

        with open(output_path, "w") as f:
            f.write(html)

        console.print(f"\n  🌐 HTML report saved to: [bold]{output_path}[/bold]")
        return output_path

    def _build_issues_html(self, issues: list) -> str:
        """Build HTML for all issues grouped by severity."""
        if not issues:
            return '<div class="issues-section"><h2>No Issues Found 🎉</h2></div>'

        html_parts = []

        for severity, label in [("critical", "🔴 Critical Issues"), ("warning", "🟡 Warnings"), ("info", "🔵 Info")]:
            severity_issues = [
                i for i in issues
                if (i.severity if hasattr(i, 'severity') else i.get('severity')) == severity
            ]

            if not severity_issues:
                continue

            html_parts.append(f'<div class="issues-section">')
            html_parts.append(f'<h2>{label} ({len(severity_issues)})</h2>')

            for issue in severity_issues:
                if hasattr(issue, 'title'):
                    title = issue.title
                    desc = issue.description
                    fp = issue.file_path
                    ln = issue.line_number
                    cat = issue.category
                    suggestion = issue.suggestion
                    code_snippet = issue.code_snippet
                    fix_code_snippet = getattr(issue, 'fix_code_snippet', '')
                else:
                    title = issue.get("title", "")
                    desc = issue.get("description", "")
                    fp = issue.get("file_path", "")
                    ln = issue.get("line_number", 0)
                    cat = issue.get("category", "")
                    suggestion = issue.get("suggestion", "")
                    code_snippet = issue.get("code_snippet", "")
                    fix_code_snippet = issue.get("fix_code_snippet", "")

                html_parts.append(f'<div class="issue {severity}">')
                html_parts.append(f'  <div class="issue-header">')
                html_parts.append(f'    <span class="issue-title">{self._escape(title)}</span>')
                html_parts.append(f'    <span class="badge {severity}">{severity.upper()}</span>')
                html_parts.append(f'  </div>')
                html_parts.append(f'  <div class="meta">{self._escape(fp)}:{ln} | {cat}</div>')
                html_parts.append(f'  <div class="description">{self._escape(desc)}</div>')
                if suggestion:
                    html_parts.append(f'  <div class="suggestion">💡 {self._escape(suggestion)}</div>')
                if code_snippet:
                    html_parts.append(f'  <div class="code-block">')
                    html_parts.append(f'    <div class="code-block-header bad">❌ Problematic Code</div>')
                    html_parts.append(f'    <pre>{self._escape(code_snippet)}</pre>')
                    html_parts.append(f'  </div>')
                if fix_code_snippet:
                    html_parts.append(f'  <div class="code-block">')
                    html_parts.append(f'    <div class="code-block-header fix">✅ Suggested Fix</div>')
                    html_parts.append(f'    <pre>{self._escape(fix_code_snippet)}</pre>')
                    html_parts.append(f'  </div>')
                html_parts.append(f'</div>')

            html_parts.append(f'</div>')

        return "\n".join(html_parts)

    @staticmethod
    def _escape(text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
