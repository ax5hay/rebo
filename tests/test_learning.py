"""Trust lifecycle without an LLM: turns are inserted directly, then feedback is applied."""
import json

import pytest

from rebo.knowledge import User
from rebo.store import new_id, now

ALICE, BOB, CAROL, DAN = User("alice"), User("bob"), User("carol"), User("dan")
ADMIN = User("cora", role="admin")
SQL = "SELECT full_name AS customer, status FROM customer WHERE status = 'active'"


def fake_turn(app, user, sql=SQL, prov=None):
    tid = new_id("turn")
    with app.store.tx() as db:
        db.execute("INSERT INTO conversation(id, owner, created_at, updated_at) VALUES(?,?,?,?)",
                   (tid + "c", user.id, now(), now()))
        db.execute("INSERT INTO turn(id, conversation_id, owner, question, kind, payload, sql, provenance, created_at)"
                   " VALUES(?,?,?,?,?,?,?,?,?)",
                   (tid, tid + "c", user.id, "active customers", "report",
                    json.dumps({"title": "Active customers", "columns": ["customer", "status"], "rows": [[1, 2]],
                                "truncated": False}), sql, json.dumps(prov or {"item_ids": []}), now()))
    return tid


def _suggest(app, user, payload):
    sid = new_id("sg")
    with app.store.tx() as db:
        db.execute("INSERT INTO suggestion(id, turn_id, owner, payload, created_at) VALUES(?,?,?,?,?)",
                   (sid, "t", user.id, json.dumps(payload), now()))
    return sid


def test_confirm_creates_personal_item_visible_only_to_owner(app):
    r = app.feedback(ALICE, fake_turn(app, ALICE), "correct")
    assert "only tunes the bot for you" in r["message"]
    item = r["item"]
    assert item["status"] == "active" and item["scope"] == "personal"
    assert item["id"] in app.knowledge.visible_ids(ALICE)
    assert item["id"] not in app.knowledge.visible_ids(BOB)
    assert app._provenance(ALICE, SQL, [])["label"] == "yours"
    assert app._provenance(BOB, SQL, [])["label"] == "new"


def test_reconfirm_reinforces(app):
    app.feedback(ALICE, fake_turn(app, ALICE), "correct")
    r = app.feedback(ALICE, fake_turn(app, ALICE, SQL + "  LIMIT 50"), "correct")
    assert r["item"]["confirmations"] == 2


def test_three_independent_confirmations_auto_propose(app):
    app.feedback(ALICE, fake_turn(app, ALICE), "correct")
    app.feedback(BOB, fake_turn(app, BOB), "correct")
    r = app.feedback(CAROL, fake_turn(app, CAROL), "correct")
    assert "3 people" in r["message"]
    queue = app.review_queue(ADMIN)
    assert len(queue) == 1 and queue[0]["status"] == "proposed"
    with pytest.raises(PermissionError):
        app.review_queue(BOB)


def test_differently_written_sql_with_same_rows_counts_as_agreement(app):
    other = ("SELECT c.status, c.full_name FROM customer AS c "
             "WHERE c.status IN ('active') ORDER BY c.customer_id")
    different = "SELECT full_name, status FROM customer WHERE status = 'paused'"
    app.feedback(ALICE, fake_turn(app, ALICE), "correct")
    app.feedback(BOB, fake_turn(app, BOB, sql=other), "correct")
    r = app.feedback(CAROL, fake_turn(app, CAROL, sql=different), "correct")
    assert "have now confirmed" not in r["message"]  # a different result is not agreement
    r = app.feedback(DAN, fake_turn(app, DAN, sql=other + " "), "correct")
    assert "3 people" in r["message"]
    assert len(app.review_queue(ADMIN)) == 1


def test_promotion_makes_it_visible_to_everyone_and_only_curators_promote(app):
    item = app.feedback(ALICE, fake_turn(app, ALICE), "correct")["item"]
    with pytest.raises(PermissionError):
        app.promote(BOB, item["id"])
    r = app.promote(ADMIN, item["id"])
    assert "Shared" in r["message"]
    assert item["id"] in app.knowledge.visible_ids(DAN)
    assert app._provenance(DAN, SQL, [])["label"] == "verified"


def test_member_report_flags_then_second_report_quarantines(app):
    item = app.feedback(ALICE, fake_turn(app, ALICE), "correct")["item"]
    app.promote(ADMIN, item["id"])
    prov = {"item_ids": [item["id"]]}
    r1 = app.feedback(BOB, fake_turn(app, BOB, prov=prov), "wrong", "should include paused")
    assert app.knowledge.get(item["id"])["status"] == "verified"
    assert "noted your report" in r1["message"]
    app.feedback(CAROL, fake_turn(app, CAROL, prov=prov), "wrong", "same issue")
    assert app.knowledge.get(item["id"])["status"] == "quarantined"
    assert item["id"] not in app.knowledge.visible_ids(DAN)


def test_owner_rejecting_own_item_retires_it_and_undo_restores(app):
    item = app.feedback(ALICE, fake_turn(app, ALICE), "correct")["item"]
    app.feedback(ALICE, fake_turn(app, ALICE, prov={"item_ids": [item["id"]]}), "wrong", "")
    assert app.knowledge.get(item["id"])["status"] == "retired"
    app.restore(ALICE, item["id"])
    assert app.knowledge.get(item["id"])["status"] == "active"
    with pytest.raises(PermissionError):
        app.retire(BOB, item["id"])


def test_teaching_a_term_is_personal_and_replaces_own_previous(app):
    term = {"kind": "term", "title": "good customer", "body": "active and ordered twice", "sql": None}
    r = app.remember(ALICE, _suggest(app, ALICE, term), True)
    assert "Only you are affected" in r["message"]
    r2 = app.remember(ALICE, _suggest(app, ALICE, {**term, "body": "active only"}), True)
    assert "replaced" in r2["message"]
    assert [i["body"] for i in app.knowledge.visible(ALICE, "term")] == ["active only"]
    assert app.knowledge.visible(BOB, "term") == []


def test_teaching_against_shared_term_goes_to_review(app):
    term = {"kind": "term", "title": "good customer", "body": "active", "sql": None}
    item = app.remember(ALICE, _suggest(app, ALICE, term), True)["item"]
    app.promote(ADMIN, item["id"])
    r = app.remember(BOB, _suggest(app, BOB, {**term, "body": "spent over 100"}), True)
    assert "shared meaning" in r["message"]
    assert r["item"]["status"] == "proposed"


def test_shared_term_wins_in_retrieval_over_users_own_conflicting_version(app):
    term = {"kind": "term", "title": "good customer", "body": "active", "sql": None}
    item = app.remember(ALICE, _suggest(app, ALICE, term), True)["item"]
    app.promote(ADMIN, item["id"])
    app.remember(BOB, _suggest(app, BOB, {**term, "body": "spent over 100"}), True)
    found = [i for i in app.knowledge.search(BOB, "good customer") if i["kind"] == "term"]
    assert [i["body"] for i in found] == ["active"]


def test_learned_join_feeds_join_path_for_its_owner_only(app):
    j = {"kind": "join", "title": "note author", "body": "notes are written by customers",
         "sql": "note.author_id = customer.customer_id"}
    app.remember(ALICE, _suggest(app, ALICE, j), True)
    path = app.catalog.join_path("note", "customer", app.knowledge.learned_joins(ALICE))
    assert path and path[0]["source"] == "learned"
    bob_path = app.catalog.join_path("note", "customer", app.knowledge.learned_joins(BOB))
    assert not bob_path or bob_path[0]["source"] != "learned"


def test_schema_change_marks_stale_then_repairs(app):
    item = app.feedback(ALICE, fake_turn(app, ALICE), "correct")["item"]
    with app.store.tx() as db:  # pretend the table changed shape and the SQL now references a gone column
        db.execute("UPDATE cat_table SET fingerprint='changed' WHERE name='customer'")
        db.execute("UPDATE knowledge SET sql=REPLACE(sql, 'status =', 'gone_column =') WHERE id=?", (item["id"],))
    app.catalog.refresh()
    assert app.revalidate()["stale"] == 1
    assert app.knowledge.get(item["id"])["status"] == "stale"
    assert item["id"] not in app.knowledge.visible_ids(ALICE)
    with app.store.tx() as db:
        db.execute("UPDATE knowledge SET sql=? WHERE id=?", (SQL, item["id"]))
    assert app.revalidate()["repaired"] == 1
    assert app.knowledge.get(item["id"])["status"] == "active"


def test_roles_and_legacy_aliases():
    assert User("x", role="curator").role == "admin" and User("x", role="member").role == "user"
    assert User("x", role="owner").is_admin and User("x", role="owner").is_owner
    assert not User("x", role="admin").is_owner and not User("x", role="nonsense").is_admin
