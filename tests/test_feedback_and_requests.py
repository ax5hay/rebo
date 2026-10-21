"""Undoing feedback, feedback in the user's own words, and requests to admins/owners."""
import pytest

from reportsbot.knowledge import User
from test_learning import SQL, fake_turn

ALICE, BOB, CAROL = User("alice"), User("bob"), User("carol")
ADMIN, OWNER = User("ada", role="admin"), User("olga", role="owner")


def test_undo_a_confirmation_withdraws_the_item_it_created(app):
    tid = fake_turn(app, ALICE)
    item = app.feedback(ALICE, tid, "correct")["item"]
    assert "undone" in app.undo_feedback(ALICE, tid)["message"]
    assert app.knowledge.get(item["id"])["status"] == "retired"
    assert app.store.one("SELECT feedback FROM turn WHERE id=?", (tid,))["feedback"] is None
    with pytest.raises(ValueError):
        app.undo_feedback(ALICE, tid)  # nothing left to undo


def test_undo_reverses_auto_proposal_and_takes_back_the_confirmation(app):
    app.feedback(ALICE, fake_turn(app, ALICE), "correct")
    app.feedback(BOB, fake_turn(app, BOB), "correct")
    t3 = fake_turn(app, CAROL)
    app.feedback(CAROL, t3, "correct")
    assert len(app.review_queue(ADMIN)) == 1
    app.undo_feedback(CAROL, t3)
    assert app.review_queue(ADMIN) == []


def test_undo_a_wrong_report_lifts_the_quarantine(app):
    item = app.feedback(ALICE, fake_turn(app, ALICE), "correct")["item"]
    app.promote(ADMIN, item["id"])
    prov = {"item_ids": [item["id"]]}
    app.feedback(BOB, fake_turn(app, BOB, prov=prov), "wrong")
    t = fake_turn(app, CAROL, prov=prov)
    app.feedback(CAROL, t, "wrong")
    assert app.knowledge.get(item["id"])["status"] == "quarantined"
    app.undo_feedback(CAROL, t)
    after = app.knowledge.get(item["id"])
    assert after["status"] == "verified" and after["rejections"] == 1


def test_changing_your_mind_replaces_earlier_feedback(app):
    tid = fake_turn(app, ALICE)
    item = app.feedback(ALICE, tid, "correct")["item"]
    app.feedback(ALICE, tid, "wrong", "it should include paused customers")
    assert app.knowledge.get(item["id"])["status"] == "retired"


def test_feedback_in_full_words_becomes_the_correction(app):
    r = app.feedback(ALICE, fake_turn(app, ALICE), "wrong", "  include paused customers too ")
    assert r["correction"] == "Correction to the previous report: include paused customers too"
    assert "reworking" in r["message"]
    row = app.store.one("SELECT feedback_note FROM turn WHERE owner='alice' AND feedback='wrong'")
    assert row["feedback_note"] == "include paused customers too"


def test_requests_route_to_the_right_people(app):
    shared = app.add_knowledge(ADMIN, kind="term", title="vip", body="spent over 1000")["item"]
    fix = app.create_request(ALICE, kind="fix_knowledge", item_id=shared["id"], text="VIP should be over 500")
    access = app.create_request(ALICE, kind="access", text="I need the invoices table")
    assert "an admin" in fix["message"] and "an owner" in access["message"]
    assert [r["kind"] for r in app.list_requests(ADMIN)] == ["fix_knowledge"]
    assert {r["kind"] for r in app.list_requests(OWNER)} == {"fix_knowledge", "access"}
    assert len(app.list_requests(ALICE)) == 2 and app.list_requests(BOB) == []
    with pytest.raises(PermissionError):
        app.resolve_request(ADMIN, access["request"]["id"], "done")
    with pytest.raises(PermissionError):
        app.resolve_request(BOB, fix["request"]["id"], "done")
    app.resolve_request(ADMIN, fix["request"]["id"], "done", "changed to 500")
    mine = app.list_requests(ALICE, status=None)
    assert {r["status"] for r in mine} == {"open", "done"}
    with pytest.raises(ValueError):
        app.create_request(ALICE, kind="other", text="   ")
