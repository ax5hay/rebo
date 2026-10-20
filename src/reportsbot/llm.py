"""Model registry: turn "<provider>:<model>" strings from reportsbot.yaml into Pydantic AI models.

  openrouter:anthropic/claude-sonnet-5.5   any OpenRouter model (Claude, Gemini, ...)  OPENROUTER_API_KEY
  anthropic:claude-sonnet-5-5              Anthropic API directly                       ANTHROPIC_API_KEY
  google:<gemini model id>                 Gemini API directly                           GEMINI_API_KEY / GOOGLE_API_KEY
  lmstudio:<loaded model id>               LM Studio's OpenAI-compatible server (offline) lmstudio_url
  openai:<model>                           OpenAI API                                    OPENAI_API_KEY

A string without a prefix but with a "/" (e.g. "anthropic/claude-sonnet-5.5") means OpenRouter.
Each model gets provider-appropriate settings (prompt caching where the provider supports it).
With `fallback` models configured, a FallbackModel tries them in order when the primary API fails.
See docs/20-llm-providers.md.
"""
from __future__ import annotations

import os
from typing import Any

from pydantic_ai.models import Model

from .settings import Settings

PROVIDERS = ("openrouter", "anthropic", "google", "lmstudio", "openai")
_MAX_TOKENS = 4096


def _env(*names: str) -> str:
    return next((os.environ[n] for n in names if os.environ.get(n)), "")


def parse(spec: str) -> tuple[str, str]:
    spec = spec.strip()
    provider, sep, name = spec.partition(":")
    if sep and provider in PROVIDERS:
        return provider, name
    if "/" in spec:
        return "openrouter", spec
    raise ValueError(f"Model '{spec}' needs a provider prefix, one of: {', '.join(PROVIDERS)}")


def build_one(spec: str, settings: Settings, *, http_client: Any = None) -> Model:
    provider, name = parse(spec)
    if provider == "openrouter":
        from pydantic_ai.models.openrouter import OpenRouterModel, OpenRouterModelSettings
        from pydantic_ai.providers.openrouter import OpenRouterProvider
        key = settings.openrouter_api_key or _env("OPENROUTER_API_KEY")
        return OpenRouterModel(name, provider=OpenRouterProvider(api_key=key, app_title="reportsbot"),
                               settings=OpenRouterModelSettings(max_tokens=_MAX_TOKENS,
                                                                openrouter_cache_instructions=True,
                                                                openrouter_cache_tool_definitions=True))
    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
        from pydantic_ai.providers.anthropic import AnthropicProvider
        return AnthropicModel(name, provider=AnthropicProvider(api_key=_env("ANTHROPIC_API_KEY")),
                              settings=AnthropicModelSettings(max_tokens=_MAX_TOKENS,
                                                              anthropic_cache_instructions=True,
                                                              anthropic_cache_tool_definitions=True))
    if provider == "google":
        from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
        from pydantic_ai.providers.google import GoogleProvider
        return GoogleModel(name, provider=GoogleProvider(api_key=_env("GEMINI_API_KEY", "GOOGLE_API_KEY")),
                           settings=GoogleModelSettings(max_tokens=_MAX_TOKENS))
    # OpenAI-compatible: LM Studio (local, offline) or OpenAI itself.
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    from pydantic_ai.settings import ModelSettings
    if provider == "lmstudio":
        # LM Studio ignores the key but the OpenAI client requires one.
        prov = OpenAIProvider(base_url=settings.lmstudio_url, api_key="lm-studio", http_client=http_client)
    else:
        prov = OpenAIProvider(api_key=_env("OPENAI_API_KEY"), http_client=http_client)
    return OpenAIChatModel(name, provider=prov, settings=ModelSettings(max_tokens=_MAX_TOKENS))


def build_model(spec: str, settings: Settings, fallbacks: list[str] | None = None, *,
                http_client: Any = None) -> Model:
    primary = build_one(spec, settings, http_client=http_client)
    rest = [build_one(f, settings, http_client=http_client) for f in (fallbacks or [])]
    if not rest:
        return primary
    from pydantic_ai.models.fallback import FallbackModel
    return FallbackModel(primary, *rest)


def credentials_present(spec: str, settings: Settings) -> bool:
    provider, _ = parse(spec)
    return {"openrouter": bool(settings.openrouter_api_key or _env("OPENROUTER_API_KEY")),
            "anthropic": bool(_env("ANTHROPIC_API_KEY")),
            "google": bool(_env("GEMINI_API_KEY", "GOOGLE_API_KEY")),
            "openai": bool(_env("OPENAI_API_KEY")),
            "lmstudio": True}[provider]
