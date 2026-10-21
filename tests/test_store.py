"""The state store itself: upgrades of existing state files."""
import sqlite3
from pathlib import Path

import pytest

from reportsbot import store as store_module
from reportsbot.store import Store


def test_existing_catalog_keeps_its_column_order_after_upgrade(tmp_path):
    path = tmp_path / "state.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE cat_table (name TEXT PRIMARY KEY, rows INTEGER, comment TEXT, description TEXT,
                                fingerprint TEXT NOT NULL, profiled_at REAL);
        CREATE TABLE cat_column (table_name TEXT NOT NULL, name TEXT NOT NULL, type TEXT NOT NULL,
                                 nullable INTEGER NOT NULL, is_pk INTEGER NOT NULL DEFAULT 0, comment TEXT,
                                 description TEXT, sensitive INTEGER NOT NULL DEFAULT 0, stats TEXT, top_values TEXT,
                                 PRIMARY KEY (table_name, name));
        INSERT INTO cat_table(name, fingerprint) VALUES ('t', 'x');
        INSERT INTO cat_column(table_name, name, type, nullable) VALUES ('t', 'zeta', 'int', 0), ('t', 'alpha', 'int', 0);
    """)
    con.commit()
    con.close()
    store = Store(path)
    assert [r["name"] for r in store.all("SELECT name FROM cat_column ORDER BY pos")] == ["zeta", "alpha"]


def test_a_state_file_from_before_migrations_upgrades_in_place(tmp_path):
    from pathlib import Path

    from sqlalchemy import create_engine, inspect, text
    path = tmp_path / "state.db"
    con = sqlite3.connect(path)
    con.executescript((Path(__file__).parent / "fixtures" / "state_schema_v0.sql").read_text(encoding="utf-8"))
    con.execute("INSERT INTO knowledge(id, kind, status, scope, owner, title, created_at, updated_at) "
                "VALUES ('te_1', 'term', 'active', 'personal', 'alice', 'paused', 1, 1)")
    con.execute("INSERT INTO knowledge_event(item_id, at, actor, action) VALUES ('te_1', 1, 'alice', 'created')")
    con.commit()
    con.close()
    store = Store(path)
    assert store.one("SELECT title FROM knowledge WHERE id='te_1'")["title"] == "paused"
    assert store.one("SELECT pinned FROM knowledge WHERE id='te_1'")["pinned"] == 0
    cols = {t: {c["name"] for c in inspect(create_engine(f"sqlite:///{path}")).get_columns(t)}
            for t in ("knowledge_event", "turn", "knowledge", "cat_column")}
    assert {"turn_id"} <= cols["knowledge_event"] and {"feedback_note"} <= cols["turn"]
    assert {"sql_template", "params", "pinned"} <= cols["knowledge"] and "pos" in cols["cat_column"]
    with create_engine(f"sqlite:///{path}").connect() as c:
        from alembic.script import ScriptDirectory
        head = ScriptDirectory(str(Path(store_module.__file__).parent / "migrations")).get_current_head()
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == head
    Store(path)                                                   # second start: nothing to do, no error
    assert store.one("SELECT COUNT(*) AS n FROM knowledge_event")["n"] == 1


def test_copy_state_moves_everything_to_another_store(app, tmp_path):
    import importlib.util

    from reportsbot.knowledge import User
    spec = importlib.util.spec_from_file_location("copy_state", Path(__file__).parents[1] / "tools" / "copy_state.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    alice = User("alice")
    item = app.add_knowledge(alice, kind="term", title="paused", body="a customer on hold")["item"]
    app.edit_knowledge(alice, item["id"], {"body": "status is paused"})
    dst = Store(tmp_path / "copy.db")
    counts = tool.copy(app.store, dst)
    assert counts["knowledge"] == 1 and counts["knowledge_event"] >= 2 and counts["cat_column"] > 0
    assert dst.one("SELECT body, scope, owner FROM knowledge")["owner"] == "alice"
    assert [r["id"] for r in dst.match("knowledge_fts", '"paused"*', "id", limit=5)] == [item["id"]]
    with pytest.raises(SystemExit):
        tool.copy(app.store, dst)                                    # never into a store with knowledge
