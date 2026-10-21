"""Runtime settings: one small YAML file (`reportsbot.yaml`, ~10 keys) + secrets from the environment.

Precedence: explicit arguments > environment variables (REPORTSBOT_*) > reportsbot.yaml > defaults.
Nothing here describes what the data means: that is learned (docs/05-learning-and-trust.md).
The file format is documented in docs/13-operations.md and reportsbot.example.yaml.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

# YAML path -> flat setting name. These are the only keys the file accepts.
_YAML_KEYS = {
    ("database",): "database_url",
    ("models", "agent"): "model",
    ("models", "fast"): "fast_model",
    ("models", "fallback"): "fallback_models",
    ("models", "escalate"): "escalate_model",
    ("lmstudio_url",): "lmstudio_url",
    ("state_dir",): "state_dir",
    ("limits", "rows"): "row_limit",
    ("limits", "probe_rows"): "probe_row_limit",
    ("limits", "query_timeout_s"): "query_timeout_s",
    ("limits", "tool_calls"): "max_tool_calls",
    ("allowed_tables",): "allow_tables",
    ("protected_columns",): "deny_columns",
    ("sharing", "threshold"): "share_threshold",
    ("embeddings",): "embeddings",
    ("auth", "mode"): "auth_mode",
    ("auth", "issuer"): "jwt_issuer",
    ("adapters",): "adapters",
    ("notify_url",): "notify_url",
}


def load_env_file(path: str | Path = ".env") -> None:
    """Put API keys from .env (OPENROUTER_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, ...) into the
    process environment, where the model providers read them. Real environment variables win."""
    from dotenv import load_dotenv
    load_dotenv(path, override=False)


def config_path() -> Path:
    return Path(os.environ.get("REPORTSBOT_CONFIG", "reportsbot.yaml"))


class _YamlSource(PydanticBaseSettingsSource):
    """Reads reportsbot.yaml and flattens the known keys; unknown keys are an error, so a typo
    never silently falls back to a default."""

    def get_field_value(self, field, field_name):  # pragma: no cover - required by the base class
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        path = config_path()
        if not path.is_file():
            return {}
        return flatten_yaml(path.read_text(encoding="utf-8"), str(path))


def flatten_yaml(text: str, source: str = "reportsbot.yaml") -> dict[str, Any]:
    """YAML text -> flat setting values. Unknown keys raise (so do secrets: they are not YAML keys)."""
    doc = yaml.safe_load(text) or {}
    if not isinstance(doc, dict):
        raise ValueError(f"{source}: the file must be a mapping of settings")
    out: dict[str, Any] = {}

    def walk(node: dict, prefix: tuple[str, ...]) -> None:
        for k, v in node.items():
            key = (*prefix, str(k))
            if key in _YAML_KEYS:
                out[_YAML_KEYS[key]] = v
            elif isinstance(v, dict):
                walk(v, key)
            else:
                raise ValueError(f"{source}: unknown setting '{'.'.join(key)}'")

    walk(doc, ())
    if isinstance(out.get("allow_tables"), list):
        out["allow_tables"] = ",".join(out["allow_tables"])
    return out


def validate_yaml(text: str) -> None:
    """Raise ValueError if `text` is not a valid reportsbot.yaml (types included)."""
    flat = flatten_yaml(text)
    flat.setdefault("database_url", os.environ.get("REPORTSBOT_DATABASE_URL", ""))
    if not flat["database_url"]:
        raise ValueError("'database' is required")
    try:
        Settings.model_validate(flat)
    except Exception as e:
        raise ValueError(str(e).splitlines()[0] + ": " + "; ".join(str(e).splitlines()[1:3])) from e


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REPORTSBOT_", env_file=".env", extra="ignore")

    # 1. The database to report on (use a read-only user).
    database_url: str = Field(..., description="SQLAlchemy URL of the database to report on.")
    # 2. Models as "<provider>:<model>"; providers: openrouter, anthropic, google, lmstudio, openai.
    model: str = "openrouter:anthropic/claude-sonnet-5.5"
    fast_model: str = "openrouter:anthropic/claude-haiku-5.5"
    fallback_models: list[str] = Field(default_factory=list)
    escalate_model: str = ""  # re-run a failed turn once on this stronger model (cost cascade)
    lmstudio_url: str = "http://127.0.0.1:1234/v1"
    # 3. Where the bot keeps what it learns.
    state_dir: Path = Path("data")
    # 4. Safety limits (never learned).
    row_limit: int = 500
    probe_row_limit: int = 20
    query_timeout_s: int = 30
    max_tool_calls: int = 25
    allow_tables: str = ""  # comma-separated allowlist; empty = every table the DB user can see
    deny_columns: str = ""  # regex on table.column, on top of auto-detected secrets
    # 5. Learning.
    share_threshold: int = 3  # distinct people agreeing before an item is proposed for everyone
    embeddings: bool = True   # local vectors when fastembed is installed; keyword search always works
    # 6. Identity: "headers" (X-User-* from a trusted gateway) or "jwt" (HS256 bearer, e.g. JMS).
    auth_mode: str = "headers"
    jwt_issuer: str = "orchid"
    # 7. Optional host adapters, e.g. ["jms"] for the JMS chat contract (src/reportsbot/adapters/).
    adapters: list[str] = Field(default_factory=list)
    # 8. Optional webhook: POST {event, ...} on request created/resolved and item promoted/stale.
    notify_url: str = ""

    # Secrets: environment only, never in the YAML file.
    openrouter_api_key: str = ""
    jwt_secret: str = ""

    @property
    def state_db(self) -> Path:
        return self.state_dir / "state.db"

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings,
                                   file_secret_settings):
        return (init_settings, env_settings, dotenv_settings, _YamlSource(settings_cls), file_secret_settings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_env_file()
    return Settings()  # type: ignore[call-arg]
