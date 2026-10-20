import json

import pytest


def test_bootstrap_profiles_and_indexes(app):
    t = app.store.one("SELECT * FROM cat_table WHERE name='customer'")
    assert t["rows"] == 40
    status = app.store.one("SELECT * FROM cat_column WHERE table_name='customer' AND name='status'")
    assert {v["value"] for v in json.loads(status["top_values"])} == {"active", "paused", "closed"}


def test_secret_columns_detected_by_name_and_value(app):
    assert ("customer", "password_hash") in app.catalog.sensitive
    col = app.store.one("SELECT top_values FROM cat_column WHERE table_name='customer' AND name='password_hash'")
    assert col["top_values"] is None  # values of protected columns are never stored


def test_declared_join_found(app):
    joins = {(j["from_table"], j["from_cols"], j["to_table"], j["source"])
             for j in app.store.all("SELECT * FROM cat_join")}
    assert ("orders", "customer_id", "customer", "fk") in joins
    assert app.catalog.join_path("orders", "customer")[0]["source"] == "fk"


def test_value_index_finds_stored_spelling(app):
    hits = app.index.search_values("paused customers")
    assert any(h["value"] == "paused" and h["table"] == "customer" for h in hits)


def test_schema_search_ranks_relevant_table(app):
    hits = app.index.search_schema("order amount")
    assert hits and hits[0]["table"] == "orders"


def test_describe_hides_protected_values(app):
    d = app.catalog.describe("customer")
    secret = next(c for c in d["columns"] if c["name"] == "password_hash")
    assert secret.get("protected") and "values" not in secret


def test_target_session_is_read_only(app):
    with pytest.raises(Exception):
        app.target.run("DELETE FROM customer", max_rows=1)
