"""Question masking for example retrieval (B-009): a stored value in the question stands for its column."""
import json

from rebo.knowledge import User
from test_learning import fake_turn


def _example(app, user, question, sql):
    t = fake_turn(app, user, sql)
    payload = json.loads(app.store.one("SELECT payload FROM turn WHERE id=?", (t,))["payload"])
    with app.store.tx() as db:
        db.execute("UPDATE turn SET question=?, payload=? WHERE id=?", (question, json.dumps({**payload,
                                                                                            "title": question}), t))
    app.feedback(user, t, "correct")
    return next(i["id"] for i in app.knowledge.visible(user, "example") if i["question"] == question)


def test_a_different_value_of_the_same_column_retrieves_the_example(app):
    alice = User("alice")
    active = _example(app, alice, "active customers", "SELECT full_name FROM customer WHERE status = 'active'")
    _example(app, alice, "customers", "SELECT full_name FROM customer")
    assert [i["id"] for i in app.knowledge.search(alice, "paused customers")][0] == active
    assert [i["id"] for i in app.knowledge.search(alice, "paused")] == [active]   # no shared word at all


def test_mask_leaves_questions_without_values_alone(app):
    assert app.index.masked_query("customers by month") is None
    assert '"active"' in app.index.masked_query("paused customers")
