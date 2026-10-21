"""Owner-only configuration editing and admin export/import of learned knowledge."""
import pytest
import yaml

from reportsbot import admin
from reportsbot.knowledge import User

USER, ADMIN, OWNER = User("alice"), User("ada", role="admin"), User("olga", role="owner")
GOOD = "database: sqlite:///x.db\nlimits: {rows: 100}\n"


@pytest.fixture()
def cfg(tmp_path, monkeypatch):
    p = tmp_path / "reportsbot.yaml"
    p.write_text("database: sqlite:///x.db\n", encoding="utf-8")
    monkeypatch.setenv("REPORTSBOT_CONFIG", str(p))
    return p


def test_only_owners_touch_configuration(app, cfg):
    for who in (USER, ADMIN):
        with pytest.raises(PermissionError):
            admin.get_config(app, who)
        with pytest.raises(PermissionError):
            admin.save_config(app, who, GOOD)
    assert admin.get_config(app, OWNER)["yaml"].startswith("database:")


def test_config_is_validated_audited_and_rolled_back(app, cfg):
    with pytest.raises(ValueError, match="unknown setting 'limts.rows'"):
        admin.save_config(app, OWNER, "database: x\nlimts: {rows: 1}\n")
    with pytest.raises(ValueError):
        admin.save_config(app, OWNER, "database: x\nlimits: {rows: lots}\n")
    with pytest.raises(ValueError, match="unknown setting 'openrouter_api_key'"):
        admin.save_config(app, OWNER, "database: x\nopenrouter_api_key: sk-123\n")  # secrets never in the file
    assert "Restart" in admin.save_config(app, OWNER, GOOD, note="smaller pages")["message"]
    assert cfg.read_text(encoding="utf-8") == GOOD
    ev = admin.get_config(app, OWNER)["history"][0]
    assert ev["actor"] == "olga" and ev["note"] == "smaller pages"
    admin.rollback_config(app, OWNER, ev["id"])
    assert cfg.read_text(encoding="utf-8") == "database: sqlite:///x.db\n"


def test_knowledge_export_edit_import_roundtrip(app):
    term = app.add_knowledge(ADMIN, kind="term", title="vip", body="spent over 1000")["item"]
    personal = app.add_knowledge(USER, kind="note", title="my region", body="north")["item"]
    with pytest.raises(PermissionError):
        admin.export_knowledge(app, USER)
    doc = yaml.safe_load(admin.export_knowledge(app, ADMIN))
    by_id = {i["id"]: i for i in doc["knowledge"]}
    by_id[term["id"]]["body"] = "spent over 500"          # edit
    by_id[personal["id"]]["status"] = "verified"          # share
    doc["knowledge"].append({"kind": "note", "title": "fiscal year", "body": "starts in April"})  # add
    doc["knowledge"].append({"id": "nope", "kind": "note", "title": "ghost"})                      # bad
    r = admin.import_knowledge(app, ADMIN, yaml.safe_dump(doc))
    assert (r["added"], r["updated"], r["shared"]) == (1, 1, 1) and len(r["errors"]) == 1
    assert app.knowledge.get(term["id"])["body"] == "spent over 500"
    assert app.knowledge.get(personal["id"])["status"] == "verified"
    app.restore(ADMIN, term["id"])                        # an import edit is undoable like any edit
    assert app.knowledge.get(term["id"])["body"] == "spent over 1000"


def test_admin_preview_shows_what_another_user_would_get(app):
    from fastapi.testclient import TestClient

    from reportsbot.api import create_app
    from reportsbot.knowledge import User
    app.knowledge.add(User("alice"), kind="term", title="paused", body="a customer on hold")
    client = TestClient(create_app(app, with_ui=False))
    r = client.get("/api/admin/preview", params={"user": "alice", "q": "paused customers"},
                   headers={"X-User-Id": "ada", "X-User-Role": "admin"})
    assert r.status_code == 200 and "a customer on hold" in r.json()["context"]
    assert r.json()["knowledge"][0]["owner"] == "alice" and "'alice'" in r.json()["context"]
    assert client.get("/api/admin/preview", params={"user": "alice", "q": "paused"},
                      headers={"X-User-Id": "bob"}).status_code == 403


def test_import_dry_run_lists_changes_and_changes_nothing(app):
    term = app.add_knowledge(ADMIN, kind="term", title="vip", body="spent over 1000")["item"]
    personal = app.add_knowledge(USER, kind="note", title="my note", body="north")["item"]
    doc = yaml.safe_load(admin.export_knowledge(app, ADMIN))
    by_id = {i["id"]: i for i in doc["knowledge"]}
    by_id[term["id"]]["body"] = "spent over 500"
    by_id[personal["id"]]["status"] = "verified"
    doc["knowledge"].append({"kind": "note", "title": "fiscal year", "body": "starts in April"})
    doc["knowledge"].append({"kind": "example", "title": "broken", "sql": "SELECT nope FROM customer"})
    before = app.store.all("SELECT id, status, body, updated_at FROM knowledge ORDER BY id")
    events = app.store.one("SELECT COUNT(*) AS n FROM knowledge_event")["n"]
    r = admin.import_knowledge(app, ADMIN, yaml.safe_dump(doc), dry_run=True)
    assert app.store.all("SELECT id, status, body, updated_at FROM knowledge ORDER BY id") == before
    assert app.store.one("SELECT COUNT(*) AS n FROM knowledge_event")["n"] == events
    assert {(c["action"], c["title"]) for c in r["changes"]} == {
        ("edit", "vip"), ("share", "my note"), ("add", "fiscal year")}
    edit = next(c for c in r["changes"] if c["action"] == "edit")
    assert edit["fields"] == {"body": ["spent over 1000", "spent over 500"]}
    assert len(r["errors"]) == 1 and "broken" in r["errors"][0] and "Nothing has changed" in r["message"]
