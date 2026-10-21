"""Runtime settings: one small YAML file (`rebo.yaml`, ~10 keys) + secrets from the environment.

Precedence: explicit arguments > environment variables (REBO_*) > rebo.yaml > defaults.
Nothing here describes what the data means: that is learned (docs/05-learning-and-trust.md).
The file format is documented in docs/13-operations.md and rebo.example.yaml.
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
    ("database_role",): "database_role",
    ("models", "agent"): "model",
    ("models", "fast"): "fast_model",
    ("models", "fallback"): "fallback_models",
    ("models", "escalate"): "escalate_model",
    ("models", "decide"): "decide_model",
    ("lmstudio_url",): "lmstudio_url",
    ("state_dir",): "state_dir",
    ("state_url",): "state_url",
    ("limits", "rows"): "row_limit",
    ("limits", "probe_rows"): "probe_row_limit",
    ("limits", "query_timeout_s"): "query_timeout_s",
    ("limits", "tool_calls"): "max_tool_calls",
    ("limits", "cost_per_turn_usd"): "cost_per_turn_usd",
    ("limits", "per_user_per_minute"): "per_user_per_minute",
    ("allowed_tables",): "allow_tables",
    ("protected_columns",): "deny_columns",
    ("sharing", "threshold"): "share_threshold",
    ("embeddings",): "embeddings",
    ("auth", "mode"): "auth_mode",
    ("auth", "issuer"): "jwt_issuer",
    ("adapters",): "adapters",
    ("notify_url",): "notify_url",
    ("checks", "agreement"): "agreement_check",
    ("checks", "shape"): "shape_check",
}


def load_env_file(path: str | Path = ".env") -> None:
    """Put API keys from .env (OPENROUTER_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, ...) into the
    process environment, where the model providers read them. Real environment variables win."""
    from dotenv import load_dotenv
    load_dotenv(path, override=False)


def config_path() -> Path:
    return Path(os.environ.get("REBO_CONFIG", "rebo.yaml"))


class _YamlSource(PydanticBaseSettingsSource):
    """Reads rebo.yaml and flattens the known keys; unknown keys are an error, so a typo
    never silently falls back to a default."""

    def get_field_value(self, field, field_name):  # pragma: no cover - required by the base class
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        path = config_path()
        if not path.is_file():
            return {}
        return flatten_yaml(path.read_text(encoding="utf-8"), str(path))


def flatten_yaml(text: str, source: str = "rebo.yaml") -> dict[str, Any]:
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
    """Raise ValueError if `text` is not a valid rebo.yaml (types included)."""
    flat = flatten_yaml(text)
    flat.setdefault("database_url", os.environ.get("REBO_DATABASE_URL", ""))
    if not flat["database_url"]:
        raise ValueError("'database' is required")
    try:
        Settings.model_validate(flat)
    except Exception as e:
        raise ValueError(str(e).splitlines()[0] + ": " + "; ".join(str(e).splitlines()[1:3])) from e


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REBO_", env_file=".env", extra="ignore")

    # 1. The database to report on (use a read-only user).
    database_url: str = Field(..., description="SQLAlchemy URL of the database to report on.")
    # 2. Models as "<provider>:<model>"; providers: openrouter, anthropic, google, lmstudio, openai.
    model: str = "openrouter:anthropic/claude-sonnet-5.5"
    fast_model: str = "openrouter:anthropic/claude-haiku-5.5"
    fallback_models: list[str] = Field(default_factory=list)
    escalate_model: str = ""  # re-run a failed turn once on this stronger model (cost cascade)
    decide_model: str = ""  # settles doubtful turns (clarify, trap, grain, review) from the agent model's lookups (docs/20 §5b)
    lmstudio_url: str = "http://127.0.0.1:1234/v1"
    # 3. Where the bot keeps what it learns.
    state_dir: Path = Path("data")
    state_url: str = ""  # postgresql://... to keep the state in Postgres instead (needs the "postgres" extra)
    # 4. Safety limits (never learned).
    row_limit: int = 500
    probe_row_limit: int = 20
    query_timeout_s: int = 30
    max_tool_calls: int = 25
    cost_per_turn_usd: float = 0.0   # 0 = no cap; list prices (llm.PRICES), see llm.turn_limits
    per_user_per_minute: int = 0     # 0 = no limit; questions one user may ask per minute
    allow_tables: str = ""  # comma-separated allowlist; empty = every table the DB user can see
    deny_columns: str = ""  # regex on table.column, on top of auto-detected secrets
    # 5. Learning.
    share_threshold: int = 3  # distinct people agreeing before an item is proposed for everyone
    embeddings: bool | str = True  # true: local default model; false: keyword only; a fastembed model; or a TEI URL
    # 6. Identity: "headers" (X-User-* from a trusted gateway) or "jwt" (HS256 bearer, e.g. JMS).
    auth_mode: str = "headers"
    jwt_issuer: str = "orchid"
    # 7. Optional host adapters, e.g. ["jms"] for the JMS chat contract (src/rebo/adapters/).
    adapters: list[str] | dict[str, dict[str, Any]] = Field(default_factory=list)  # [jms] or {jms: {option: …}}
    # 8. Optional webhook: POST {event, ...} on request created/resolved and item promoted/stale.
    notify_url: str = ""
    # 9. Optional extra check on low-confidence new reports: 2 candidate queries from the fast model,
    #    executed and compared with the report; disagreement goes to a judge (doc 04, B-048).
    agreement_check: bool = False
    # 10. Optional: after a new report, offer the agent the saved reports whose query has nearly the same
    #     shape (SQL skeleton) but were not in its context, once (doc 04, B-050).
    shape_check: bool = False
    database_role: str = ""  # e.g. "{user}": PostgreSQL role each person's queries run as (row-level security)

    # Secrets: environment only, never in the YAML file.
    openrouter_api_key: str = ""
    jwt_secret: str = ""

    def adapter_options(self, name: str) -> dict[str, Any]:
        """An adapter's own options, from `adapters: {name: {...}}` (a plain list gives none)."""
        return dict((self.adapters.get(name) or {}) if isinstance(self.adapters, dict) else {})

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
