"""
VTune GuardianAI - LLM Provider (GitHub Models)
=================================================
Creates the LLM instance backed by GitHub Copilot / GitHub Models.
Uses the OpenAI-compatible endpoint at models.inference.ai.azure.com.

Includes automatic fallback: if the primary model (e.g. o4-mini) hits
rate limits or parameter errors, it auto-switches to the fallback model
(e.g. gpt-4o) for that call and continues seamlessly.
"""

from __future__ import annotations

import time
from typing import Any, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from rich.console import Console

from guardian.config import GuardianConfig

console = Console()


class FallbackChatModel(BaseChatModel):
    """A wrapper that catches rate-limit errors and falls back to another model.

    When the primary model returns HTTP 429 (rate limited) or similar errors,
    this wrapper automatically retries with the fallback model and logs the switch.
    """

    primary: BaseChatModel
    fallback: BaseChatModel
    primary_name: str = "primary"
    fallback_name: str = "fallback"
    _switched_to_fallback: bool = False

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "fallback_chat_model"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Try primary model first; on rate-limit error, fall back."""
        if not self._switched_to_fallback:
            try:
                return self.primary._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except Exception as e:
                if _is_rate_limit_error(e):
                    console.print(
                        f"  [yellow]⚠ Rate limited on {self.primary_name} — "
                        f"switching to {self.fallback_name}[/yellow]"
                    )
                    self._switched_to_fallback = True
                    # Brief pause before retry
                    time.sleep(2)
                    return self.fallback._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                raise  # Re-raise non-rate-limit errors

        # Already switched — use fallback directly
        return self.fallback._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if an exception should trigger a fallback to the backup model.

    Catches:
    - HTTP 429 rate limit / quota errors
    - HTTP 400 unsupported parameter errors (e.g. o4-mini doesn't support temperature)
    - Model-specific incompatibility errors
    """
    error_str = str(exc).lower()
    fallback_indicators = [
        "429",
        "rate limit",
        "rate_limit",
        "too many requests",
        "quota exceeded",
        "quota_exceeded",
        "resource_exhausted",
        "throttled",
        "unsupported_value",
        "unsupported value",
        "does not support",
        "invalid_request_error",
        "unknown_model",
        "model_not_found",
    ]
    return any(indicator in error_str for indicator in fallback_indicators)


def get_llm(config: GuardianConfig) -> BaseChatModel:
    """
    Create a GitHub Models LLM instance with automatic fallback.

    Primary model (e.g. o4-mini) is tried first.  If it hits rate limits
    or unsupported-parameter errors, automatically falls back to the
    fallback model (e.g. gpt-4o).

    Uses the OpenAI-compatible endpoint authenticated with a GitHub PAT.

    Args:
        config: GuardianConfig with GitHub Models settings.

    Returns:
        A LangChain-compatible ChatModel instance.

    Raises:
        ValueError: If GITHUB_TOKEN is not set.
    """
    if not config.github_token:
        raise ValueError(
            "GITHUB_TOKEN is required. "
            "Create a PAT at: https://github.com/settings/tokens\n"
            "Required scope: 'copilot' (or use a fine-grained token with Models access)"
        )

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ImportError(
            "langchain-openai is required. "
            "Install with: pip install langchain-openai"
        )

    def _is_reasoning_model(model_name: str) -> bool:
        """Reasoning models (o1, o3, o4 series) only support temperature=1."""
        return any(model_name.startswith(prefix) for prefix in ("o1", "o3", "o4"))

    primary = ChatOpenAI(
        model=config.github_model,
        base_url=config.github_base_url,
        api_key=config.github_token,
        temperature=1,  # Reasoning models (o1/o3/o4) only support temperature=1
    )

    # If a fallback model is configured, wrap with FallbackChatModel
    if config.github_fallback_model and config.github_fallback_model != config.github_model:
        fallback_temp = 1 if _is_reasoning_model(config.github_fallback_model) else 0.1
        fallback = ChatOpenAI(
            model=config.github_fallback_model,
            base_url=config.github_base_url,
            api_key=config.github_token,
            temperature=fallback_temp,
        )
        console.print(
            f"  [dim]🔄 Fallback enabled: {config.github_model} → {config.github_fallback_model}[/dim]"
        )
        return FallbackChatModel(
            primary=primary,
            fallback=fallback,
            primary_name=config.github_model,
            fallback_name=config.github_fallback_model,
        )

    return primary
