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

    # LLM Provider selection: "github" or "bedrock"
    llm_provider: str = "bedrock"

    # GitHub Copilot (GitHub Models)
    github_token: str = ""
    github_model: str = "o3"
    github_fallback_model: str = "o3-mini"
    github_model_chain: str = ""  # Comma-separated: "o3,o3-mini,o4-mini,gpt-4.1-mini"
    github_base_url: str = "https://models.inference.ai.azure.com"

    # AWS Bedrock (Claude via SAI/AIDE)
    bedrock_bearer_token: str = ""
    bedrock_region: str = "us-east-2"
    bedrock_model: str = "global.anthropic.claude-sonnet-4-20250514-v1:0"
    bedrock_fallback_model: str = "us.anthropic.claude-3-5-haiku-20241022-v1:0"

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
            llm_provider=os.getenv("LLM_PROVIDER", "bedrock"),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            github_model=os.getenv("GITHUB_MODEL", "o3"),
            github_fallback_model=os.getenv("GITHUB_FALLBACK_MODEL", "o3-mini"),
            github_model_chain=os.getenv("GITHUB_MODEL_CHAIN", ""),
            github_base_url=os.getenv("GITHUB_BASE_URL", "https://models.inference.ai.azure.com"),
            bedrock_bearer_token=os.getenv("AWS_BEARER_TOKEN_BEDROCK", ""),
            bedrock_region=os.getenv("AWS_REGION", "us-east-2"),
            bedrock_model=os.getenv("BEDROCK_MODEL", "global.anthropic.claude-sonnet-4-20250514-v1:0"),
            bedrock_fallback_model=os.getenv("BEDROCK_FALLBACK_MODEL", "us.anthropic.claude-3-5-haiku-20241022-v1:0"),
            cppcheck_path=os.getenv("CPPCHECK_PATH", "cppcheck"),
            clang_tidy_path=os.getenv("CLANG_TIDY_PATH", "clang-tidy"),
            severity_threshold=os.getenv("GUARDIAN_SEVERITY_THRESHOLD", "warning"),
            max_files=int(os.getenv("GUARDIAN_MAX_FILES", "50")),
            report_format=os.getenv("GUARDIAN_REPORT_FORMAT", "terminal"),
            vtune_repo_path=os.getenv("VTUNE_REPO_PATH", ""),
        )

    def get_active_llm_info(self) -> str:
        """Return a human-readable string of the active LLM configuration."""
        if self.llm_provider == "bedrock":
            short_model = self.bedrock_model.split(".")[-1].split("-v")[0] if "." in self.bedrock_model else self.bedrock_model
            fallback_info = ""
            if self.bedrock_fallback_model and self.bedrock_fallback_model != self.bedrock_model:
                short_fb = self.bedrock_fallback_model.split(".")[-1].split("-v")[0] if "." in self.bedrock_fallback_model else self.bedrock_fallback_model
                fallback_info = f" → fallback: {short_fb}"
            return f"AWS Bedrock ({short_model}{fallback_info}) @ {self.bedrock_region}"
        else:
            if self.github_model_chain:
                models = [m.strip() for m in self.github_model_chain.split(",") if m.strip()]
                chain_str = " → ".join(models)
                return f"GitHub Models (chain: {chain_str}) @ {self.github_base_url}"
            fallback_info = f" → fallback: {self.github_fallback_model}" if self.github_fallback_model else ""
            return f"GitHub Models ({self.github_model}{fallback_info}) @ {self.github_base_url}"
