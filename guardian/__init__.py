"""
VTune GuardianAI - AI-Powered Pre-Push Code Guardian for Intel VTune Profiler
=============================================================================

An intelligent agent that analyzes code changes for bugs, memory leaks,
security vulnerabilities, and coding standard violations before code is
pushed to mainline.

Usage:
    vtune-guardian check              # Scan staged changes
    vtune-guardian check --all        # Scan all uncommitted changes
    vtune-guardian check --provider gemini  # Use Gemini API
"""

__version__ = "0.1.0"
__app_name__ = "VTune GuardianAI"
