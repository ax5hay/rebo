import pytest
import sqlglot
from sqlglot import exp

from reportsbot.knowledge import User
from reportsbot.safety import fill_params, parameterize


def test_literals_become_numbered_placeholders_and_round_trip():
    sql = ("SELECT full_name FROM customer WHERE status = 'paused' AND created >= '2026-01-01' "
           "AND customer_id > 5 LIMIT 10")
    template, values = parameterize(sql, "sqlite")
    assert values == ["paused", "2026-01-01", 5]
    assert ":p1" in template and "'paused'" not in template and "LIMIT 10" in template
    assert fill_params(template, "sqlite", values) == fill_params(template, "sqlite", ["paused", "2026-01-01", 5])
    assert "'closed'" in fill_params(template, "sqlite", ["closed", "2026-01-01", 5])


def test_a_value_cannot_change_the_query_shape():
    template, _ = parameterize("SELECT full_name FROM customer WHERE status = 'paused'", "sqlite")
    tree = sqlglot.parse_one(fill_params(template, "sqlite", ["x' OR '1'='1"]), read="sqlite")
    assert tree.find(exp.Or) is None and [lit.this for lit in tree.find_all(exp.Literal)] == ["x' OR '1'='1"]
    with pytest.raises(ValueError):
        fill_params(template + " AND status = :p9", "sqlite", ["a"])


def test_confirmed_example_stores_template_and_params(app):
    from test_learning import fake_turn
    alice = User("alice")
    t = fake_turn(app, alice, "SELECT full_name FROM customer WHERE status = 'paused'")
    app.feedback(alice, t, "correct")
    item = app.knowledge.visible(alice, "example")[0]
    assert item["params"] == ["paused"] and ":p1" in item["sql_template"]


def test_rerun_returns_fresh_rows_without_a_model(app):
    import json
    import sqlite3

    from fastapi.testclient import TestClient

    from reportsbot.api import create_app
    from test_learning import fake_turn
    alice = User("alice")
    t = fake_turn(app, alice, "SELECT full_name AS customer FROM customer WHERE status = 'paused'")
    con = sqlite3.connect(app.settings.database_url.removeprefix("sqlite:///"))
    con.execute("INSERT INTO customer(customer_id, full_name, status) VALUES (999, 'New Person', 'paused')")
    con.commit()
    con.close()
    client = TestClient(create_app(app, with_ui=False))     # no agent is configured: any model call would fail
    r = client.post(f"/api/turns/{t}/rerun", headers={"X-User-Id": "alice"}).json()
    assert r["kind"] == "report" and len(r["rows"]) == 11 and ["New Person"] in r["rows"]
    assert json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])["route"] == "rerun"
    assert client.post(f"/api/turns/{t}/rerun", headers={"X-User-Id": "bob"}).status_code == 403


def test_pin_puts_a_report_first_among_starters_and_unpin_removes_it(app):
    from fastapi.testclient import TestClient

    from reportsbot.api import create_app
    from test_learning import fake_turn
    alice = User("alice")
    t = fake_turn(app, alice, "SELECT full_name FROM customer WHERE status = 'paused'")
    other = fake_turn(app, alice, "SELECT full_name FROM customer")
    app.store.db.execute("UPDATE turn SET question='everyone' WHERE id=?", (other,))
    app.store.db.commit()
    app.feedback(alice, other, "correct")
    client = TestClient(create_app(app, with_ui=False))
    item = client.post(f"/api/turns/{t}/pin", headers={"X-User-Id": "alice"}).json()
    assert item["pinned"] == 1 and app.starter_questions(alice)[0] == "active customers"
    assert client.post(f"/api/turns/{t}/pin", headers={"X-User-Id": "alice"}).json()["id"] == item["id"]  # no duplicate
    assert client.delete(f"/api/knowledge/{item['id']}/pin", headers={"X-User-Id": "bob"}).status_code == 403
    client.delete(f"/api/knowledge/{item['id']}/pin", headers={"X-User-Id": "alice"})
    assert app.pinned(alice) == [] and [e["action"] for e in app.store.all(
        "SELECT action FROM knowledge_event WHERE item_id=? ORDER BY id", (item["id"],))][-2:] == ["pinned", "unpinned"]


def test_what_do_you_know_about(app):
    from fastapi.testclient import TestClient

    from reportsbot.api import create_app
    alice, bob = User("alice"), User("bob")
    app.knowledge.add(alice, kind="term", title="paused", body="a customer on hold")
    client = TestClient(create_app(app, with_ui=False))
    a = client.get("/api/knowledge/about", params={"q": "paused"}, headers={"X-User-Id": "alice"}).json()
    assert [i["title"] for i in a["knowledge"]["yours"]] == ["paused"] and a["knowledge"]["verified"] == []
    assert {"value": "paused", "table": "customer", "column": "status"}.items() <= a["values"][0].items()
    assert any(s["table"] == "customer" for s in client.get(
        "/api/knowledge/about", params={"q": "customer status"}, headers={"X-User-Id": "alice"}).json()["schema"])
    assert app.about(bob, "paused")["knowledge"]["yours"] == []          # personal knowledge stays personal


async def test_reply_cites_visible_items_only(app):
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    from reportsbot.agent import build_agent
    alice = User("alice")
    item = app.knowledge.add(alice, kind="term", title="paused", body="a customer on hold").item

    def model(messages, info):
        return ModelResponse(parts=[ToolCallPart("reply", {"text": "Paused means on hold.",
                                                           "used_knowledge": [item["id"], "te_unknown"]})])

    app.__dict__["agent"] = build_agent(FunctionModel(model))
    r = await app.ask(alice, "what does paused mean?")
    assert r["kind"] == "answer" and r["cites"] == [{"id": item["id"], "title": "paused", "trust": "yours"}]
    assert (await app.ask(User("bob"), "what does paused mean?"))["cites"] == []


async def test_personal_default_reaches_the_prompt_for_its_owner_only(app):
    from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel

    from reportsbot.agent import build_agent
    prompts = []

    def model(messages, info):
        prompts.append([p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart)][-1])
        return ModelResponse(parts=[ToolCallPart("reply", {"text": "ok"})])

    app.__dict__["agent"] = build_agent(FunctionModel(model))
    alice = User("alice")
    app.set_default(alice, "status", "active")
    app.set_default(alice, "status", "paused")          # replaces the earlier value
    assert [(d["name"], d["value"]) for d in app.my_defaults(alice)] == [("status", "paused")]
    await app.ask(alice, "customers")
    await app.ask(User("bob"), "customers")
    assert "<my_defaults>\nstatus: paused\n</my_defaults>" in prompts[0] and "<my_defaults>" not in prompts[1]
    assert prompts[0].index("<my_defaults>") < prompts[0].index("<learned_knowledge>")
