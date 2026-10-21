"""The same bot on a made-up, non-JMS domain: only the config changes."""
import importlib.util
from pathlib import Path

from rebo.service import App
from rebo.settings import Settings, validate_yaml

ROOT = Path(__file__).resolve().parents[1]


def _build(tmp_path):
    spec = importlib.util.spec_from_file_location("demo_build", ROOT / "fixtures" / "demo_property" / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build(tmp_path / "greenleaf.db")


def test_demo_config_is_valid():
    validate_yaml((ROOT / "fixtures" / "demo_property" / "rebo.yaml").read_text(encoding="utf-8"))


def test_bot_learns_a_different_domain_from_the_database_alone(tmp_path):
    db = _build(tmp_path)
    app = App(Settings(database_url=f"sqlite:///{db}", state_dir=tmp_path / "state", embeddings=False))
    counts = app.bootstrap(progress=lambda *_: None)
    assert counts["tables"] == 9
    assert ("tenant", "password_hash") in app.catalog.sensitive
    hits = app.index.search_values("month to month")
    assert any(h["table"] == "lease_status" and h["value"] == "Active - Month to Month" for h in hits)
    assert app.index.search_schema("maintenance request priority")[0]["table"] == "maintenance"
    # maintenance.assigned_to -> staff has no declared key and no name hint: left for people to teach
    assert app.catalog.join_path("maintenance", "staff") is None or all(
        j["from_cols"] != "assigned_to" for j in app.catalog.join_path("maintenance", "staff"))


def test_drill_through_from_a_summary_cell_to_its_rows(tmp_path):
    import json
    import sqlite3

    import pytest

    from rebo.knowledge import User
    from rebo.store import new_id, now
    db = _build(tmp_path)
    app = App(Settings(database_url=f"sqlite:///{db}", state_dir=tmp_path / "state", embeddings=False))
    app.bootstrap(progress=lambda *_: None)
    sql = ("SELECT b.name AS building, COUNT(*) AS open_requests FROM maintenance m JOIN unit u ON u.unit_id = m.unit_id "
           "JOIN building b ON b.building_id = u.building_id WHERE m.state <> 'closed' GROUP BY b.name ORDER BY 2 DESC")
    res = app._run_report_sql(sql)
    alice, tid = User("alice"), new_id("turn")
    with app.store.tx() as s:
        s.execute("INSERT INTO conversation(id, owner, created_at, updated_at) VALUES(?,?,?,?)", ("c1", "alice", now(), now()))
        s.execute("INSERT INTO turn(id, conversation_id, owner, question, kind, payload, sql, created_at) "
                  "VALUES(?,?,?,?,?,?,?,?)", (tid, "c1", "alice", "open maintenance per building", "report",
                                              json.dumps({"title": "Open requests", "columns": res.columns,
                                                          "rows": res.rows, "truncated": False}), sql, now()))
    building, count = res.rows[0]
    r = app.drill(alice, tid, row=0, column="open_requests")
    assert r["kind"] == "report" and len(r["rows"]) == count and "request_id" in r["columns"]
    con = sqlite3.connect(db)
    expected = {x[0] for x in con.execute(
        "SELECT m.request_id FROM maintenance m JOIN unit u ON u.unit_id = m.unit_id JOIN building b "
        "ON b.building_id = u.building_id WHERE m.state <> 'closed' AND b.name = ?", (building,))}
    assert {row[r["columns"].index("request_id")] for row in r["rows"]} == expected
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert usage["route"] == "drill" and usage["requests"] == 0 and building in r["assumptions"][0]
    with pytest.raises(ValueError):
        app.drill(alice, tid, row=99, column="open_requests")
    from fastapi.testclient import TestClient

    from rebo.api import create_app
    client = TestClient(create_app(app, with_ui=False))
    ok = client.post(f"/api/turns/{tid}/drill", json={"row": 1}, headers={"X-User-Id": "alice"})
    assert ok.status_code == 200 and len(ok.json()["rows"]) == res.rows[1][1]
    assert client.post(f"/api/turns/{tid}/drill", json={"row": 1}, headers={"X-User-Id": "bob"}).status_code == 403


def test_a_value_filter_can_be_switched_without_a_model(tmp_path):
    """B-060: 'still open' read as state = 'open' is one click away from 'everything but closed'."""
    import json

    import pytest

    from rebo.knowledge import User
    from rebo.store import new_id, now
    db = _build(tmp_path)
    app = App(Settings(database_url=f"sqlite:///{db}", state_dir=tmp_path / "state", embeddings=False))
    app.bootstrap(progress=lambda *_: None)
    sql = ("SELECT b.name AS building, COUNT(m.request_id) AS open_requests FROM building b "
           "LEFT JOIN unit u ON u.building_id = b.building_id "
           "LEFT JOIN maintenance m ON m.unit_id = u.unit_id AND m.state = 'open' GROUP BY b.name")
    choices = app.filter_choices(sql)
    assert [(c["column"], c["values"], c["negated"]) for c in choices] == [("state", ["open"], False)]
    assert {"closed", "in_progress", "waiting_parts"} <= {o["value"] for o in choices[0]["options"]}
    res = app._run_report_sql(sql)
    alice, tid = User("alice"), new_id("turn")
    with app.store.tx() as s:
        s.execute("INSERT INTO conversation(id, owner, created_at, updated_at) VALUES(?,?,?,?)", ("c1", "alice", now(), now()))
        s.execute("INSERT INTO turn(id, conversation_id, owner, question, kind, payload, sql, created_at) "
                  "VALUES(?,?,?,?,?,?,?,?)", (tid, "c1", "alice", "open requests per building", "report",
                                              json.dumps({"title": "Open requests", "columns": res.columns,
                                                          "rows": res.rows, "assumptions": ["Open means state open."]}), sql, now()))
    r = app.refine(alice, tid, 0, ["closed"], negated=True)
    gold = app._run_report_sql("SELECT b.name, COUNT(*) FROM maintenance m JOIN unit u ON u.unit_id=m.unit_id "
                               "JOIN building b ON b.building_id=u.building_id WHERE m.state <> 'closed' GROUP BY b.name")
    assert sorted(map(tuple, r["rows"])) == sorted(map(tuple, gold.rows))
    assert r["filters"][0]["negated"] and r["assumptions"][-1].startswith("You switched state")
    with pytest.raises(ValueError):
        app.refine(alice, tid, 0, ["'; DROP TABLE x; --"], negated=False)
    with pytest.raises(PermissionError):
        app.refine(User("bob"), tid, 0, ["closed"], negated=True)
