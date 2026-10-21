"""The same bot on a made-up, non-JMS domain: only the config changes."""
import importlib.util
from pathlib import Path

from reportsbot.service import App
from reportsbot.settings import Settings, validate_yaml

ROOT = Path(__file__).resolve().parents[1]


def _build(tmp_path):
    spec = importlib.util.spec_from_file_location("demo_build", ROOT / "fixtures" / "demo_property" / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build(tmp_path / "greenleaf.db")


def test_demo_config_is_valid():
    validate_yaml((ROOT / "fixtures" / "demo_property" / "reportsbot.yaml").read_text(encoding="utf-8"))


def test_bot_learns_a_different_domain_from_the_database_alone(tmp_path):
    db = _build(tmp_path)
    app = App(Settings(database_url=f"sqlite:///{db}", state_dir=tmp_path / "state", embeddings=False))
    counts = app.bootstrap(progress=lambda *_: None)
    assert counts["tables"] == 9
    assert ("tenant", "password_hash") in app.catalog.sensitive
    hits = app.index.search_values("month to month")
    assert any(h["table"] == "lease_status" and h["value"] == "Active - Month to Month" for h in hits)
    assert app.index.search_schema("maintenance request priority")[0]["table"] == "maintenance"
    # maintenance.assigned_to -> staff has no declared key and no name hint: left for people to teach
    assert app.catalog.join_path("maintenance", "staff") is None or all(
        j["from_cols"] != "assigned_to" for j in app.catalog.join_path("maintenance", "staff"))
