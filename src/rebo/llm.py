"""Model registry: turn "<provider>:<model>" strings from rebo.yaml into Pydantic AI models.

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

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from pydantic_ai import UsageLimits
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import Model
from pydantic_ai.models.wrapper import WrapperModel

from .settings import Settings

log = logging.getLogger(__name__)
PROVIDERS = ("openrouter", "anthropic", "google", "lmstudio", "openai")
_MAX_TOKENS = 4096


@dataclass(frozen=True)
class Profile:
    """How one model family is driven. Defaults keep today's behaviour (docs/20 §2.1)."""
    thinking: bool | Literal["minimal", "low", "medium", "high"] | None = None  # None: provider default
    tool_call_factor: float = 1.0          # multiplies limits.tool_calls for turns on this model
    parallel_tool_calls: bool | None = None
    output: Literal["tool", "prompted"] = "tool"  # prompted: JSON in text, for models that fail tool calls
    output_retries: int = 2                # validator retries (SQL that fails) before the turn errors


# First entry whose key is a substring of the model name wins. Researched 2026-10-21 against
# Pydantic AI 2.58.0: the unified `thinking` setting maps to Gemini's thinking_level and to
# OpenRouter's reasoning effort. Gemini values are a first guess, to be measured (B-012).
PROFILES: list[tuple[str, Profile]] = [
    ("gemini-3", Profile(thinking="low", tool_call_factor=1.6, parallel_tool_calls=True)),
    ("gemma-4", Profile(output_retries=4)),
]


def profile(spec: str) -> Profile:
    name = parse(spec)[1].lower()
    return next((p for key, p in PROFILES if key in name), Profile())


def _tuned(spec: str) -> dict[str, Any]:
    p = profile(spec)
    out: dict[str, Any] = {"max_tokens": _MAX_TOKENS}
    if p.thinking is not None:
        out["thinking"] = p.thinking
    if p.parallel_tool_calls is not None:
        out["parallel_tool_calls"] = p.parallel_tool_calls
    return out


# USD per 1M tokens (input, cache read, output), OpenRouter list prices checked 2026-10-21 (docs/20). Also used
# by the usage dashboard (App.stats) for cost per day.
PRICES = {
    "anthropic/claude-haiku-5.5": (0.10, 0.01, 0.50),
    "anthropic/claude-sonnet-5.5": (2.00, 0.10, 10.00),
    "google/gemini-3.8-flash": (0.825, 0.0825, 4.125),
    "google/gemini-3.5-flash-lite": (0.30, 0.03, 2.50),
    # candidates measured as cheaper agent / light models (docs/20 §5b), OpenRouter list prices 2026-10-22.
    # Chinese-origin models are excluded by policy.
    "openai/gpt-6-luna-pro": (0.10, 0.01, 0.50),
    "openai/gpt-6-luna": (0.10, 0.01, 0.50),
    # Google direct (google: models), ai.google.dev/gemini-api/docs/pricing checked 2026-10-21: these prices hold
    # through 2026-12-31 and double on 2027-01-01.
    "gemini-3.8-flash": (0.75, 0.075, 3.75),
}


def cost(usage: dict) -> float | None:
    name = (usage.get("model") or "").split(":", 1)[-1]
    if name not in PRICES:
        return None
    pin, pcache, pout = PRICES[name]
    cached = usage.get("cache_read_tokens") or 0
    fresh = max((usage.get("input_tokens") or 0) - cached, 0)
    total = (fresh * pin + cached * pcache + (usage.get("output_tokens") or 0) * pout) / 1e6
    if isinstance(usage.get("before"), dict):  # a run discarded for escalation still cost money
        total += cost(usage["before"]) or 0.0
    return round(total, 5)


_GENAI_PROVIDER = {"openrouter": "openrouter", "anthropic": "anthropic", "google": "google", "openai": "openai"}


def genai_price(spec: str, input_tokens: int = 1_000_000, output_tokens: int = 100_000) -> float | None:
    """Price genai-prices (what Pydantic AI's cost_limit uses) gives a reference usage; None if unknown."""
    provider, name = parse(spec)
    if provider not in _GENAI_PROVIDER:
        return None
    try:
        from genai_prices import Usage, calc_price
        return float(calc_price(Usage(input_tokens=input_tokens, output_tokens=output_tokens), model_ref=name,
                                provider_id=_GENAI_PROVIDER[provider]).total_price)
    except Exception:
        return None


def turn_limits(spec: str, *, tool_calls: int, cost_cap_usd: float) -> UsageLimits:
    """Usage limits for one turn on `spec`. A cost cap is meant in list prices (PRICES, checked against
    OpenRouter). Pydantic AI enforces cost_limit with genai-prices, which can differ (2026-10-21: Haiku 5.5
    5x higher, Gemini 3.8 Flash 9% lower), so the cap is scaled by their ratio. A model genai-prices does
    not know falls back to token limits from PRICES (80% of the cap for input, 20% for output); a model
    with no price at all (e.g. lmstudio:, local) gets no cost cap."""
    limits = UsageLimits(request_limit=40, tool_calls_limit=tool_calls)
    if cost_cap_usd <= 0:
        return limits
    ours, theirs = cost({"model": spec, "input_tokens": 1_000_000, "output_tokens": 100_000}), genai_price(spec)
    if theirs and ours:
        limits.cost_limit = Decimal(str(round(cost_cap_usd * theirs / ours, 6)))
    elif ours:
        pin, _, pout = PRICES[parse(spec)[1]]
        limits.input_tokens_limit = int(cost_cap_usd * 0.8 / pin * 1e6)
        limits.output_tokens_limit = int(cost_cap_usd * 0.2 / pout * 1e6)
    return limits


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
        return OpenRouterModel(name, provider=OpenRouterProvider(api_key=key, app_title="rebo"),
                               settings=OpenRouterModelSettings(**_tuned(spec),
                                                                openrouter_cache_instructions=True,
                                                                openrouter_cache_tool_definitions=True,
                                                                # the growing turn (tool results) too: each of a turn's
                                                                # 4-5 requests then re-reads it at the cached price. Claude
                                                                # only: for Gemini OpenRouter keeps just the last breakpoint.
                                                                **({"openrouter_cache_messages": True} if "anthropic/" in name else {})))
    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
        from pydantic_ai.providers.anthropic import AnthropicProvider
        return AnthropicModel(name, provider=AnthropicProvider(api_key=_env("ANTHROPIC_API_KEY")),
                              settings=AnthropicModelSettings(**_tuned(spec),
                                                              anthropic_cache_instructions="1h",
                                                              anthropic_cache_tool_definitions="1h",
                                                              anthropic_cache_messages="5m"))
    if provider == "google":
        from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
        from pydantic_ai.providers.google import GoogleProvider
        return GoogleModel(name, provider=GoogleProvider(api_key=_env("GEMINI_API_KEY", "GOOGLE_API_KEY")),
                           settings=GoogleModelSettings(**_tuned(spec)))
    # OpenAI-compatible: LM Studio (local, offline) or OpenAI itself.
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    from pydantic_ai.settings import ModelSettings
    if provider == "lmstudio":
        # LM Studio ignores the key but the OpenAI client requires one.
        prov = OpenAIProvider(base_url=settings.lmstudio_url, api_key="lm-studio", http_client=http_client)
    else:
        prov = OpenAIProvider(api_key=_env("OPENAI_API_KEY"), http_client=http_client)
    return OpenAIChatModel(name, provider=prov, settings=ModelSettings(**_tuned(spec)))


class PatientModel(WrapperModel):
    """Waits and retries when the provider answers "too many requests" (HTTP 429), honouring the delay
    it gives ("retry in 47s", retryDelay, Retry-After), up to `max_wait_s` in total per request, instead
    of failing the turn. Free tiers (Gemini: 5 requests/minute) and burst limits then slow a turn down
    rather than break it."""

    def __init__(self, wrapped: Model, max_wait_s: float = 300.0, default_delay_s: float = 30.0):
        super().__init__(wrapped)
        self.max_wait_s, self.default_delay_s = max_wait_s, default_delay_s

    @property
    def settings(self):  # the wrapped model's settings (caching, thinking, ...) stay visible
        return self.wrapped.settings

    def _delay(self, e: ModelHTTPError) -> float:
        text = f"{e.body} {getattr(e, 'headers', '')}"
        m = re.search(r"retry in ([0-9.]+)s|retryDelay'?\"?:? ?'?\"?([0-9.]+)s|retry-after'?:? ?'?([0-9.]+)", text, re.I)
        return float(next(g for g in m.groups() if g)) + 1 if m else self.default_delay_s

    async def request(self, messages, model_settings, model_request_parameters):
        waited = 0.0
        while True:
            try:
                return await self.wrapped.request(messages, model_settings, model_request_parameters)
            except ModelHTTPError as e:
                delay = self._delay(e) if e.status_code == 429 else None
                if delay is None or waited + delay > self.max_wait_s:
                    raise
                log.info("%s: rate limited, waiting %.0f s", self.wrapped.model_name, delay)
                await asyncio.sleep(delay)
                waited += delay


def _patient(spec: str, model: Model) -> Model:
    """Remote APIs get PatientModel (rate limits wait instead of failing); local LM Studio does not."""
    return model if parse(spec)[0] == "lmstudio" else PatientModel(model)


def build_model(spec: str, settings: Settings, fallbacks: list[str] | None = None, *,
                http_client: Any = None) -> Model:
    primary = _patient(spec, build_one(spec, settings, http_client=http_client))
    rest = [_patient(f, build_one(f, settings, http_client=http_client)) for f in (fallbacks or [])]
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
