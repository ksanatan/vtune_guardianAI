"""
VTune GuardianAI - Configuration Management
============================================
Loads settings from .env file and environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv


def _find_env_file() -> Optional[Path]:
    """Search for .env file starting from current dir up to project root."""
    current = Path.cwd()
    while current != current.parent:
        env_path = current / ".env"
        if env_path.exists():
            return env_path
        current = current.parent
    # Also check the package directory
    pkg_dir = Path(__file__).parent.parent
    env_path = pkg_dir / ".env"
    if env_path.exists():
        return env_path
    return None


@dataclass
class GuardianConfig:
    """Central configuration for VTune GuardianAI."""

    # GitHub Copilot (GitHub Models) — sole LLM provider
    github_token: str = ""
    github_model: str = "o3"
    github_fallback_model: str = "o3-mini"
    github_base_url: str = "https://models.inference.ai.azure.com"

    # Static analysis tool paths
    cppcheck_path: str = "cppcheck"
    clang_tidy_path: str = "clang-tidy"

    # Guardian settings
    severity_threshold: str = "warning"  # "critical", "warning", "info"
    max_files: int = 50
    report_format: str = "terminal"  # "terminal", "json", "html"

    # VTune repo path (auto-detected or configurable)
    vtune_repo_path: str = ""

    # Analysis toggles
    enable_static_analysis: bool = True
    enable_memory_leak_check: bool = True
    enable_ai_review: bool = True
    enable_security_check: bool = True
    enable_build_compat_check: bool = True
    enable_best_practices: bool = True

    @classmethod
    def load(cls) -> "GuardianConfig":
        """Load configuration from .env file and environment variables."""
        env_file = _find_env_file()
        if env_file:
            load_dotenv(env_file)

        return cls(
            github_token=os.getenv("GITHUB_TOKEN", ""),
            github_model=os.getenv("GITHUB_MODEL", "o3"),
            github_fallback_model=os.getenv("GITHUB_FALLBACK_MODEL", "o3-mini"),
            github_base_url=os.getenv("GITHUB_BASE_URL", "https://models.inference.ai.azure.com"),
            cppcheck_path=os.getenv("CPPCHECK_PATH", "cppcheck"),
            clang_tidy_path=os.getenv("CLANG_TIDY_PATH", "clang-tidy"),
            severity_threshold=os.getenv("GUARDIAN_SEVERITY_THRESHOLD", "warning"),
            max_files=int(os.getenv("GUARDIAN_MAX_FILES", "50")),
            report_format=os.getenv("GUARDIAN_REPORT_FORMAT", "terminal"),
            vtune_repo_path=os.getenv("VTUNE_REPO_PATH", ""),
        )

    def get_active_llm_info(self) -> str:
        """Return a human-readable string of the active LLM configuration."""
        fallback_info = f" → fallback: {self.github_fallback_model}" if self.github_fallback_model else ""
        return f"GitHub Models ({self.github_model}{fallback_info}) @ {self.github_base_url}"
