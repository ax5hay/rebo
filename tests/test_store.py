"""The state store itself: upgrades of existing state files."""
import sqlite3

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
