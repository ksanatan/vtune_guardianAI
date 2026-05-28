"""
VTune GuardianAI - LLM Provider (GitHub Models + AWS Bedrock)
===============================================================
Creates LLM instances backed by GitHub Models or AWS Bedrock (Claude).

GitHub Models supports two modes:
  1. **Model Chain** (recommended): Cycles through a list of models
     (e.g. o3 → o3-mini → o4-mini → gpt-4.1-mini). When one exhausts
     its rate limit, the chain advances to the next model and **retries
     only the files that failed** — results already obtained from the
     previous model are kept.
  2. **Simple Fallback** (legacy): primary → single fallback, sticky switch.

AWS Bedrock:
  Uses AIDE bearer tokens decoded to AWS credentials for ChatBedrockConverse.
  Primary + fallback model support.
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


# ── Multi-Model Chain ────────────────────────────────────────────────────────

class ModelChainChatModel(BaseChatModel):
    """Cycles through a chain of models on rate-limit errors.

    Unlike FallbackChatModel (which does a sticky switch to one fallback),
    this walks through an ordered list of models. When model N is exhausted,
    it advances to model N+1 and retries the current call. Already-obtained
    results from model N are kept by the caller (combined_analysis_node).

    Attributes:
        models: Ordered list of ChatOpenAI instances.
        model_names: Matching list of human-readable model names.
        current_index: Index into `models` of the model currently in use.
    """

    models: List[BaseChatModel]
    model_names: List[str]
    current_index: int = 0

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "model_chain_chat_model"

    @property
    def current_model_name(self) -> str:
        """Return the name of the model currently being used."""
        return self.model_names[self.current_index]

    @property
    def has_next_model(self) -> bool:
        """Return True if there is another model in the chain."""
        return self.current_index < len(self.models) - 1

    def advance_to_next_model(self) -> bool:
        """Move to the next model in the chain.

        Returns True if advanced, False if already at the last model.
        """
        if self.has_next_model:
            old = self.model_names[self.current_index]
            self.current_index += 1
            new = self.model_names[self.current_index]
            console.print(
                f"  [yellow]⚠ Rate limited on {old} — advancing chain to {new}[/yellow]"
            )
            return True
        return False

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Try current model; on rate-limit error, advance chain and retry."""
        while self.current_index < len(self.models):
            try:
                model = self.models[self.current_index]
                return model._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except Exception as e:
                if _is_rate_limit_error(e) and self.has_next_model:
                    self.advance_to_next_model()
                    time.sleep(2)  # Brief cooldown
                    continue
                raise  # No more models or non-rate-limit error

        # Should not reach here, but just in case
        raise RuntimeError("All models in the chain are exhausted.")


# ── Legacy Simple Fallback ───────────────────────────────────────────────────

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


# ── Shared Helpers ───────────────────────────────────────────────────────────

def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if an exception should trigger a fallback to the backup model.

    Catches:
    - HTTP 429 rate limit / quota errors
    - HTTP 400 unsupported parameter errors (e.g. reasoning models require temperature=1)
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


def _is_reasoning_model(model_name: str) -> bool:
    """Reasoning models (o1, o3, o4 series) only support temperature=1."""
    return any(model_name.startswith(prefix) for prefix in ("o1", "o3", "o4"))


def _create_chat_model(model_name: str, config: GuardianConfig):
    """Create a single ChatOpenAI instance with correct temperature."""
    from langchain_openai import ChatOpenAI

    temp = 1 if _is_reasoning_model(model_name) else 0.1
    return ChatOpenAI(
        model=model_name,
        base_url=config.github_base_url,
        api_key=config.github_token,
        temperature=temp,
    )


def get_llm(config: GuardianConfig) -> BaseChatModel:
    """
    Create an LLM instance based on the configured provider.

    Routes to:
      - AWS Bedrock (Claude) if LLM_PROVIDER=bedrock
      - GitHub Models if LLM_PROVIDER=github

    Returns:
        A LangChain-compatible ChatModel instance.

    Raises:
        ValueError: If required credentials are not set.
    """
    if config.llm_provider == "bedrock":
        return _get_bedrock_llm(config)
    return _get_github_llm(config)


def _get_bedrock_llm(config: GuardianConfig) -> BaseChatModel:
    """Create an AWS Bedrock (Claude) LLM with fallback support."""
    if not config.bedrock_bearer_token:
        raise ValueError(
            "AWS_BEARER_TOKEN_BEDROCK is required for Bedrock provider.\n"
            "Generate token at: https://tokengen.aide.infra-host.com/"
        )

    try:
        from langchain_aws import ChatBedrockConverse
        import boto3
    except ImportError:
        raise ImportError(
            "langchain-aws and boto3 are required for Bedrock.\n"
            "Install with: pip install langchain-aws boto3"
        )

    # Decode AIDE bearer token to AWS credentials
    access_key, secret_key, session_token = _decode_bearer_token(config.bedrock_bearer_token)

    # Create boto3 session with decoded credentials
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
        region_name=config.bedrock_region,
    )
    bedrock_client = session.client("bedrock-runtime", region_name=config.bedrock_region)

    primary = ChatBedrockConverse(
        model=config.bedrock_model,
        client=bedrock_client,
        temperature=0.1,
        max_tokens=4096,
    )

    if config.bedrock_fallback_model and config.bedrock_fallback_model != config.bedrock_model:
        fallback = ChatBedrockConverse(
            model=config.bedrock_fallback_model,
            client=bedrock_client,
            temperature=0.1,
            max_tokens=4096,
        )
        console.print(
            f"  [dim]🔄 Bedrock fallback: {config.bedrock_model.split('.')[-1][:30]} → "
            f"{config.bedrock_fallback_model.split('.')[-1][:30]}[/dim]"
        )
        return FallbackChatModel(
            primary=primary,
            fallback=fallback,
            primary_name=config.bedrock_model,
            fallback_name=config.bedrock_fallback_model,
        )

    return primary


def _decode_bearer_token(token: str) -> tuple[str, str, str]:
    """
    Decode AIDE bearer token (ABSK format) to AWS credentials.

    AIDE tokens are base64-encoded strings in format:
        ABSK<base64(access_key:secret_key:session_token)>
    or sometimes:
        ABSK<base64(access_key:secret_key)>
    """
    import base64

    # Strip ABSK prefix if present
    raw = token
    if raw.startswith("ABSK"):
        raw = raw[4:]

    # Decode base64
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
    except Exception:
        # Might already be decoded or different format
        decoded = raw

    parts = decoded.split(":")
    if len(parts) >= 3:
        return parts[0], parts[1], ":".join(parts[2:])
    elif len(parts) == 2:
        return parts[0], parts[1], ""
    else:
        raise ValueError(
            "Cannot decode AIDE bearer token. "
            "Expected format: ABSK<base64(access_key:secret_key:session_token)>"
        )


def _get_github_llm(config: GuardianConfig) -> BaseChatModel:
    """Create a GitHub Models LLM with model chain or simple fallback."""
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

    # ── Mode 1: Model Chain ──────────────────────────────────────────────
    if config.github_model_chain:
        chain_names = [m.strip() for m in config.github_model_chain.split(",") if m.strip()]
        if len(chain_names) >= 2:
            chain_models = [_create_chat_model(name, config) for name in chain_names]
            console.print(
                f"  [dim]🔗 Model chain: {' → '.join(chain_names)}[/dim]"
            )
            return ModelChainChatModel(
                models=chain_models,
                model_names=chain_names,
            )

    # ── Mode 2: Legacy Primary + Fallback ────────────────────────────────
    primary = ChatOpenAI(
        model=config.github_model,
        base_url=config.github_base_url,
        api_key=config.github_token,
        temperature=1,  # Reasoning models (o1/o3/o4) only support temperature=1
    )

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
