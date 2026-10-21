"""Direct editing of learned knowledge: who may edit what, validation, history and undo."""
import pytest

from rebo.knowledge import User

ALICE, BOB = User("alice"), User("bob")
ADMIN, OWNER = User("ada", role="admin"), User("olga", role="owner")
SQL = "SELECT full_name AS customer FROM customer WHERE status = 'active'"


def test_admin_adds_shared_knowledge_that_everyone_gets(app):
    r = app.add_knowledge(ADMIN, kind="term", title="good customer", body="active and ordered at least twice",
                          sql="customer.status = 'active'")
    assert "Added for everyone" in r["message"] and r["item"]["status"] == "verified"
    assert r["item"]["id"] in app.knowledge.visible_ids(BOB)
    assert app.add_knowledge(OWNER, kind="note", title="fiscal year", body="starts in April")["item"]["status"] == "verified"


def test_user_adds_personal_knowledge(app):
    r = app.add_knowledge(ALICE, kind="note", title="my region", body="I only care about the north")
    assert r["item"]["status"] == "active" and r["item"]["id"] not in app.knowledge.visible_ids(BOB)


def test_bad_sql_is_refused_for_examples_terms_and_joins(app):
    with pytest.raises(ValueError, match="can't be saved"):
        app.add_knowledge(ADMIN, kind="example", title="x", question="x", sql="SELECT nope FROM customer")
    with pytest.raises(ValueError, match="can't be saved"):
        app.add_knowledge(ADMIN, kind="join", title="x", sql="note.author_id = customer.nope")
    with pytest.raises(ValueError, match="can't be saved"):
        app.add_knowledge(ADMIN, kind="term", title="x", sql="customer.nope = 1")


def test_users_edit_only_their_own_unshared_items(app):
    mine = app.add_knowledge(ALICE, kind="note", title="my region", body="north")["item"]
    assert "Saved" in app.edit_knowledge(ALICE, mine["id"], {"body": "north and east"})["message"]
    with pytest.raises(PermissionError):
        app.edit_knowledge(BOB, mine["id"], {"body": "hijack"})
    shared = app.add_knowledge(ADMIN, kind="term", title="vip", body="spent over 1000")["item"]
    with pytest.raises(PermissionError, match="fix request"):
        app.edit_knowledge(ALICE, shared["id"], {"body": "spent over 10"})
    assert app.edit_knowledge(ADMIN, mine["id"], {"title": "region"})["item"]["title"] == "region"


def test_edit_reindexes_and_recomputes_sql_fields(app):
    ex = app.add_knowledge(ADMIN, kind="example", title="Active customers", question="active customers", sql=SQL)["item"]
    new_sql = "SELECT full_name AS customer FROM customer WHERE status = 'paused'"
    edited = app.edit_knowledge(ADMIN, ex["id"], {"sql": new_sql, "question": "paused customers"})["item"]
    assert edited["sql_canonical"] != ex["sql_canonical"] and edited["tables"] == ["customer"]
    assert [i["id"] for i in app.knowledge.search(BOB, "paused customers")] == [ex["id"]]


def test_undo_walks_back_edits_then_status(app):
    item = app.add_knowledge(ALICE, kind="note", title="t", body="v1")["item"]
    app.edit_knowledge(ALICE, item["id"], {"body": "v2"})
    app.edit_knowledge(ALICE, item["id"], {"body": "v3"})
    assert "previous wording" in app.restore(ALICE, item["id"])["message"]
    assert app.knowledge.get(item["id"])["body"] == "v2"
    app.restore(ALICE, item["id"])
    assert app.knowledge.get(item["id"])["body"] == "v1"
    actions = [e["action"] for e in app.knowledge.history(item["id"])]
    assert actions.count("edited") == 4  # two edits + two undo edits, all kept in the history
