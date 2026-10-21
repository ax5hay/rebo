"""Owner-only configuration editing and admin export/import of learned knowledge."""
import pytest
import yaml

from rebo import admin
from rebo.knowledge import User

USER, ADMIN, OWNER = User("alice"), User("ada", role="admin"), User("olga", role="owner")
GOOD = "database: sqlite:///x.db\nlimits: {rows: 100}\n"


@pytest.fixture()
def cfg(tmp_path, monkeypatch):
    p = tmp_path / "rebo.yaml"
    p.write_text("database: sqlite:///x.db\n", encoding="utf-8")
    monkeypatch.setenv("REBO_CONFIG", str(p))
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

    from rebo.api import create_app
    from rebo.knowledge import User
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


def test_bulk_review_shares_or_rejects_several_with_one_note(app):
    from fastapi.testclient import TestClient

    from rebo.api import create_app
    a = app.add_knowledge(USER, kind="note", title="fiscal year", body="starts in April")["item"]
    b = app.add_knowledge(USER, kind="term", title="vip", body="spent over 1000")["item"]
    c = app.add_knowledge(USER, kind="note", title="noise", body="ignore")["item"]
    client = TestClient(create_app(app, with_ui=False))
    admin_h = {"X-User-Id": "ada", "X-User-Role": "admin"}
    r = client.post("/api/review/bulk", json={"item_ids": [a["id"], b["id"], "nope"], "action": "share",
                                              "note": "agreed in the Monday review"}, headers=admin_h).json()
    assert r["done"] == [a["id"], b["id"]] and len(r["errors"]) == 1
    assert {app.knowledge.get(i)["status"] for i in (a["id"], b["id"])} == {"verified"}
    assert "Monday review" in app.knowledge.history(a["id"])[-1]["note"]
    client.post("/api/review/bulk", json={"item_ids": [c["id"]], "action": "reject", "note": "duplicate"},
                headers=admin_h)
    assert app.knowledge.get(c["id"])["status"] == "retired"
    assert client.post("/api/review/bulk", json={"item_ids": [a["id"]], "action": "reject"},
                       headers={"X-User-Id": "alice"}).status_code == 403


def test_usage_stats_on_seeded_turns(app):
    import json

    t0 = 1_793_000_000.0  # 2026-10-26 UTC, ISO week 44
    usage = {"model": "openrouter:anthropic/claude-sonnet-5.5", "requests": 2, "input_tokens": 1_000_000,
             "output_tokens": 100_000, "cache_read_tokens": 0}
    seeds = [("paused customers", "report", "verified", "correct", usage, t0),
             ("Paused  customers", "report", "new", "wrong", usage, t0 + 3600),
             ("orders", "report", "new", None, {"model": "lmstudio:m", "requests": 1}, t0 + 8 * 86400),
             ("hello", "answer", None, None, {}, t0 + 8 * 86400)]
    with app.store.tx() as db:
        db.execute("INSERT INTO conversation(id, owner, created_at, updated_at) VALUES('c','alice',?,?)", (t0, t0))
        for who in ("eval", "eval-1a2b3c4d"):  # eval runs never count as use
            db.execute("INSERT INTO turn(id, conversation_id, owner, question, kind, payload, usage, created_at) "
                       "VALUES(?,?,?,?,?,?,?,?)", (f"e-{who}", "c", who, "paused customers", "report", "{}", "{}", t0))
        for n, (q, kind, label, fb, u, ts) in enumerate(seeds):
            db.execute("INSERT INTO turn(id, conversation_id, owner, question, kind, payload, provenance, feedback, "
                       "usage, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (f"t{n}", "c", "alice", q, kind, "{}", json.dumps({"label": label}) if label else None, fb,
                        json.dumps(u), ts))
    item = app.add_knowledge(USER, kind="note", title="flaky", body="x")["item"]
    app.store.db.execute("UPDATE knowledge SET rejections=3 WHERE id=?", (item["id"],))
    app.store.db.commit()
    app.create_request(USER, kind="fix_knowledge", text="please fix", item_id=item["id"])
    with pytest.raises(PermissionError):
        app.stats(USER)
    st = app.stats(ADMIN, days=100_000)
    assert st["confirmation_by_week"]["2026-W44"] == {"reports": 2, "confirmed": 1, "rejected": 1,
                                                      "confirmation_rate": 0.5}
    assert st["provenance"] == {"new": 2, "verified": 1}
    assert st["top_questions"][0] == {"question": "paused customers", "count": 2}
    assert st["most_reported_wrong"][0]["title"] == "flaky"
    assert st["open_requests"][0]["age_days"] >= 0 and st["unpriced_model_turns"] == 1
    assert st["cost_per_day_usd"] == {"2026-10-26": 2 * (2.00 + 1.00)}   # 1M in at $2 + 0.1M out at $10, twice


def test_config_preview_checks_database_and_models_without_saving(app, tmp_path, monkeypatch):
    cfg = tmp_path / "rebo.yaml"
    cfg.write_text("database: sqlite:///x.db\n", encoding="utf-8")
    monkeypatch.setenv("REBO_CONFIG", str(cfg))
    good = f"database: {app.settings.database_url}\nmodels:\n  agent: lmstudio:qwen\n"
    r = admin.save_config(app, OWNER, good, preview=True)
    assert r["ok"] and {"setting": "model", "from": app.settings.model, "to": "lmstudio:qwen"} in r["changes"]
    bad_db = f"database: sqlite:///{tmp_path}/no/such/dir/x.db\n"
    r = admin.save_config(app, OWNER, bad_db, preview=True)
    assert not r["ok"] and r["errors"][0].startswith("database: cannot connect")
    r = admin.save_config(app, OWNER, good.replace("lmstudio:qwen", "qwen"), preview=True)
    assert not r["ok"] and r["errors"][0].startswith("model:")
    assert cfg.read_text(encoding="utf-8") == "database: sqlite:///x.db\n"      # nothing saved
    assert app.store.one("SELECT COUNT(*) AS n FROM config_event")["n"] == 0
    with pytest.raises(PermissionError):
        admin.save_config(app, ADMIN, good, preview=True)


async def test_insights_conversations_and_me(app):
    import json

    from fastapi.testclient import TestClient

    from rebo.api import create_app
    from rebo.evals import record_run
    from test_llm import _completion, _scripted
    _scripted(app, [_completion("reply", {"text": "hi"})])
    first = await app.ask(USER, "hello")
    await app.ask(USER, "again", first["conversation_id"])
    record_run(app, kind="questions", cases="gold.jsonl", model="m", summary={"execution_match": "8/10"},
               results_file="r.json")
    client = TestClient(create_app(app, with_ui=False))
    alice = {"X-User-Id": "alice"}
    assert client.get("/api/me", headers=alice).json()["role"] == "user"
    convs = client.get("/api/conversations", headers=alice).json()
    assert convs[0]["turns"] == 2 and convs[0]["title"] == "hello"
    turns = client.get(f"/api/conversations/{first['conversation_id']}", headers=alice).json()
    assert [t["question"] for t in turns] == ["hello", "again"] and turns[0]["text"] == "hi"
    assert client.get(f"/api/conversations/{first['conversation_id']}", headers={"X-User-Id": "bob"}).status_code == 403
    assert client.get("/api/insights", headers=alice).status_code == 403
    ins = client.get("/api/insights", headers={"X-User-Id": "ada", "X-User-Role": "admin"}).json()
    states = {c["name"]: c["state"] for c in ins["checks"]}
    assert states["Reported database"] == "ok" and states["State store"] == "ok" and states["Catalog"] == "ok"
    assert states["Search index"] == "ok"            # embeddings are off in tests: keyword only is fine
    assert states["Agent model"] in ("ok", "fail")    # depends on whether this machine has a key
    assert ins["accuracy"][0]["summary"]["execution_match"] == "8/10" and "usage" in ins
    assert json.dumps(ins)                           # serialisable as the API returns it
