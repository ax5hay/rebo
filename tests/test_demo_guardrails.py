"""Public-demo guardrails (all off by default): the highest role a sign-in can claim, a per-visitor rate
limit by client address, and a daily model budget for the whole site after which only free routes answer."""
import json

from fastapi.testclient import TestClient

from rebo.api import create_app
from rebo.knowledge import User
from rebo.store import new_id, now


def test_owner_is_capped_to_admin_when_max_role_is_admin(app):
    app.settings.max_role = "admin"
    client = TestClient(create_app(app, with_ui=False))
    me = client.get("/api/me", headers={"X-User-Id": "eve", "X-User-Role": "owner"}).json()
    assert me["role"] == "admin" and not me["is_owner"]
    assert client.get("/api/health").json()["max_role"] == "admin"   # the welcome screen hides Owner


def test_a_visitor_is_limited_by_address_whatever_name_they_use(app):
    app.settings.per_visitor_per_minute = 2
    client = TestClient(create_app(app, with_ui=False))
    codes = [client.post("/api/ask", json={"text": "x"}, headers={"X-User-Id": f"name{i}", "CF-Connecting-IP": "203.0.113.9"}).status_code
             for i in range(3)]
    assert codes[2] == 429


async def test_over_the_daily_budget_new_questions_are_not_sent_to_the_model(app):
    app.settings.daily_budget_usd = 0.01
    with app.store.tx() as db:   # earlier spend today, above the cap
        db.execute("INSERT INTO conversation(id, owner, created_at, updated_at) VALUES(?,?,?,?)", ("c0", "x", now(), now()))
        db.execute("INSERT INTO turn(id, conversation_id, owner, question, kind, payload, usage, created_at) VALUES(?,?,?,?,?,?,?,?)",
                   (new_id("turn"), "c0", "x", "q", "answer", "{}", json.dumps({"model": "openrouter:anthropic/claude-sonnet-5.5",
                                                                                 "input_tokens": 100000, "output_tokens": 1000}), now()))

    class NoModel:
        def __getattr__(self, name):
            raise AssertionError("the model was asked")
    app.__dict__.update(agent=NoModel())
    r = await app.ask(User("ada"), "something new nobody saved")
    assert r["kind"] == "answer" and "allowance" in r["text"]
