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
