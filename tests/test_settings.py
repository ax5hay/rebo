import pytest

from reportsbot.settings import Settings

YAML = """
database: sqlite:///x.db
models: {agent: "google:gemini-x", fallback: ["lmstudio:qwen"]}
limits: {rows: 50, tool_calls: 9}
allowed_tables: [a, b]
sharing: {threshold: 5}
auth: {mode: jwt}
"""


@pytest.fixture()
def cfg(tmp_path, monkeypatch):
    p = tmp_path / "reportsbot.yaml"
    p.write_text(YAML, encoding="utf-8")
    monkeypatch.setenv("REPORTSBOT_CONFIG", str(p))
    for k in ("REPORTSBOT_DATABASE_URL", "REPORTSBOT_ROW_LIMIT", "REPORTSBOT_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)  # no stray .env
    return p


def test_yaml_keys_map_to_settings(cfg):
    s = Settings()
    assert s.database_url == "sqlite:///x.db"
    assert s.model == "google:gemini-x" and s.fallback_models == ["lmstudio:qwen"]
    assert (s.row_limit, s.max_tool_calls, s.share_threshold) == (50, 9, 5)
    assert s.allow_tables == "a,b" and s.auth_mode == "jwt"
    assert s.fast_model.startswith("openrouter:")  # untouched keys keep defaults


def test_environment_overrides_yaml(cfg, monkeypatch):
    monkeypatch.setenv("REPORTSBOT_ROW_LIMIT", "7")
    assert Settings().row_limit == 7


def test_unknown_key_is_an_error(cfg):
    cfg.write_text(YAML + "\nlimts: {rows: 1}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown setting 'limts.rows'"):
        Settings()


def test_api_keys_in_dotenv_reach_the_model_registry(tmp_path, monkeypatch):
    from reportsbot.llm import credentials_present
    from reportsbot.settings import load_env_file
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("REPORTSBOT_OPENROUTER_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=test-key-from-dotenv\n", encoding="utf-8")
    s = Settings(database_url="sqlite://")
    assert not credentials_present("openrouter:anthropic/claude-sonnet-5.5", s)
    load_env_file(tmp_path / ".env")
    assert credentials_present("openrouter:anthropic/claude-sonnet-5.5", s)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)  # do not leak into other tests


def test_example_config_stays_small():
    """AGENTS.md §3.3: the example configuration holds at most 20 settings."""
    from pathlib import Path

    from reportsbot.settings import flatten_yaml
    text = (Path(__file__).resolve().parents[1] / "reportsbot.example.yaml").read_text(encoding="utf-8")
    assert len(flatten_yaml(text)) <= 20


def test_identity_from_the_login_proxy_headers(app):
    from fastapi.testclient import TestClient

    from reportsbot.api import create_app
    client = TestClient(create_app(app, with_ui=False))
    assert client.get("/api/defaults", headers={"X-Forwarded-Email": "ann@example.com"}).status_code == 200
    app.set_default(__import__("reportsbot.knowledge", fromlist=["User"]).User("ann@example.com"), "period", "2026")
    mine = client.get("/api/defaults", headers={"X-Forwarded-Email": "ann@example.com",
                                                "X-Forwarded-User": "ann"}).json()
    assert mine and mine[0]["value"] == "2026"
    assert client.get("/api/defaults").status_code == 401                     # no identity at all
