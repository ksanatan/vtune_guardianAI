"""
VTune GuardianAI - Unit Tests
================================
Tests for individual analysis nodes and core functionality.
"""

import pytest
from pathlib import Path

from guardian.config import GuardianConfig
from guardian.agents.state import GuardianState, FileChange, Issue


# ── Config Tests ──

class TestGuardianConfig:
    """Tests for configuration management."""

    def test_default_config(self):
        """Default config should have sensible defaults."""
        config = GuardianConfig()
        assert config.github_model == "o3"
        assert config.github_fallback_model == "o3-mini"
        assert config.severity_threshold == "warning"
        assert config.max_files == 50
        assert config.report_format == "terminal"
        assert config.enable_static_analysis is True
        assert config.enable_ai_review is True

    def test_active_llm_info(self):
        config = GuardianConfig(github_model="o3", github_fallback_model="o3-mini")
        info = config.get_active_llm_info()
        assert "GitHub Models" in info
        assert "o3" in info
        assert "o3-mini" in info

    def test_active_llm_info_no_fallback(self):
        config = GuardianConfig(github_model="o3", github_fallback_model="")
        info = config.get_active_llm_info()
        assert "GitHub Models" in info
        assert "o3" in info
        assert "fallback" not in info


# ── State Tests ──

class TestGuardianState:
    """Tests for agent state management."""

    def test_default_state(self):
        state = GuardianState()
        assert state.file_changes == []
        assert state.total_files_changed == 0
        assert state.has_cpp_changes is False

    def test_file_change_creation(self):
        fc = FileChange(
            file_path="src/main.cpp",
            change_type="modified",
            diff_content="+added line\n-removed line",
            language="cpp",
            lines_added=1,
            lines_deleted=1,
        )
        assert fc.file_path == "src/main.cpp"
        assert fc.language == "cpp"

    def test_issue_creation(self):
        issue = Issue(
            id="test-001",
            severity="critical",
            category="memory_leak",
            file_path="src/collector.cpp",
            line_number=42,
            title="Potential memory leak",
            description="malloc() called without corresponding free()",
            suggestion="Use std::unique_ptr or add free() in destructor",
            source="memory_leak",
        )
        assert issue.severity == "critical"
        assert issue.line_number == 42


# ── File Classifier Tests ──

class TestFileClassifier:
    """Tests for file classification logic."""

    def test_cpp_detection(self):
        from guardian.nodes.git_diff import _detect_language
        assert _detect_language("src/main.cpp") == "cpp"
        assert _detect_language("include/header.h") == "h"
        assert _detect_language("src/module.cc") == "cpp"
        assert _detect_language("include/types.hpp") == "hpp"

    def test_python_detection(self):
        from guardian.nodes.git_diff import _detect_language
        assert _detect_language("scripts/build.py") == "python"

    def test_scons_detection(self):
        from guardian.nodes.git_diff import _detect_language
        assert _detect_language("SConstruct") == "scons"
        assert _detect_language("component.parts") == "scons"

    def test_unknown_detection(self):
        from guardian.nodes.git_diff import _detect_language
        assert _detect_language("README") == "unknown"


# ── Security Pattern Tests ──

class TestSecurityPatterns:
    """Tests for security vulnerability pattern detection."""

    def test_dangerous_c_patterns(self):
        import re
        from guardian.nodes.security_check import DANGEROUS_C_PATTERNS

        dangerous_code = 'gets(buffer);'
        matched = False
        for pattern, severity, title, desc, bad_code, fix_code in DANGEROUS_C_PATTERNS:
            if re.search(pattern, dangerous_code):
                matched = True
                assert severity == "critical"
                break
        assert matched, "gets() should be detected as dangerous"

    def test_dangerous_python_patterns(self):
        import re
        from guardian.nodes.security_check import DANGEROUS_PYTHON_PATTERNS

        dangerous_code = 'result = eval(user_input)'
        matched = False
        for pattern, severity, title, desc, bad_code, fix_code in DANGEROUS_PYTHON_PATTERNS:
            if re.search(pattern, dangerous_code):
                matched = True
                assert severity == "critical"
                break
        assert matched, "eval() should be detected as dangerous"

    def test_safe_code_no_match(self):
        import re
        from guardian.nodes.security_check import DANGEROUS_C_PATTERNS

        safe_code = 'fgets(buffer, sizeof(buffer), stdin);'
        for pattern, severity, title, desc, bad_code, fix_code in DANGEROUS_C_PATTERNS:
            assert not re.search(pattern, safe_code), f"Safe code matched: {title}"


# ── Helpers Tests ──

class TestHelpers:
    """Tests for utility helper functions."""

    def test_truncate_diff_short(self):
        from guardian.utils.helpers import truncate_diff
        short = "a" * 100
        assert truncate_diff(short) == short

    def test_truncate_diff_long(self):
        from guardian.utils.helpers import truncate_diff
        long_diff = "a" * 10000
        result = truncate_diff(long_diff, max_chars=1000)
        assert len(result) < len(long_diff)
        assert "TRUNCATED" in result

    def test_count_lines_in_diff(self):
        from guardian.utils.helpers import count_lines_in_diff
        diff = """--- a/file.c
+++ b/file.c
-old line
+new line
+another new line
 context"""
        added, deleted = count_lines_in_diff(diff)
        assert added == 2
        assert deleted == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
