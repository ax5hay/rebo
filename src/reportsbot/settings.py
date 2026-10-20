"""Runtime settings. Environment variables only (or a .env file next to the process).

Everything here is deployment wiring or a safety limit. Nothing describes the target
database's meaning: that is learned (see docs/04-learning-and-trust.md).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REPORTSBOT_", env_file=".env", extra="ignore")

    # Wiring
    database_url: str = Field(..., description="SQLAlchemy URL of the database to report on. Use a read-only user.")
    openrouter_api_key: str = Field("", description="OpenRouter key. Without it only bootstrap-without-describe works.")
    model: str = "anthropic/claude-sonnet-5.5"
    fast_model: str = "anthropic/claude-haiku-5.5"
    state_dir: Path = Path("data")

    # Safety limits (never learned)
    row_limit: int = 500
    probe_row_limit: int = 20
    query_timeout_s: int = 30
    allow_tables: str = ""  # comma-separated allowlist; empty = every table the DB user can see
    deny_columns: str = ""  # extra regex of columns never selectable, on top of auto-detected secrets
    max_tool_calls: int = 25

    # Learning thresholds
    share_threshold: int = 3  # distinct users confirming the same SQL before it is proposed org-wide
    embeddings: bool = True  # use fastembed if installed; keyword search always works

    @property
    def state_db(self) -> Path:
        return self.state_dir / "state.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
