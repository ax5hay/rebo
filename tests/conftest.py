"""Offline fixtures: a tiny SQLite 'shop' database and an App on top of it (no LLM calls)."""
from __future__ import annotations

import os
import sqlite3
import uuid
from typing import Iterator

import pytest

from rebo.service import App
from rebo.settings import Settings

SHOP = """
CREATE TABLE customer (customer_id INTEGER PRIMARY KEY, full_name TEXT, email TEXT, status TEXT,
                       password_hash TEXT, created TEXT);
CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customer(customer_id),
                     amount REAL, state TEXT, placed_at TEXT);
CREATE TABLE note (note_id INTEGER PRIMARY KEY, author_id INTEGER, body TEXT);
"""


# State backends to run the suite on. Postgres joins when REBO_TEST_STATE_URL points at a server
# (docker compose up -d state-db); each test then gets its own schema, dropped afterwards.
PG_URL = os.environ.get("REBO_TEST_STATE_URL", "")
BACKENDS = ["sqlite", "postgres"] if PG_URL else ["sqlite"]


@pytest.fixture(params=BACKENDS)
def state_url(request) -> Iterator[str]:
    if request.param == "sqlite":
        yield ""
        return
    import psycopg
    schema = f"t_{uuid.uuid4().hex[:12]}"
    admin_url = PG_URL.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f"CREATE SCHEMA {schema}")
    yield f"{admin_url}{'&' if '?' in admin_url else '?'}options=-csearch_path%3D{schema}"
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f"DROP SCHEMA {schema} CASCADE")


@pytest.fixture()
def app(tmp_path, state_url) -> App:
    db = tmp_path / "shop.db"
    con = sqlite3.connect(db)
    con.executescript(SHOP)
    statuses = ["active", "active", "paused", "closed"]
    for i in range(1, 41):
        con.execute("INSERT INTO customer VALUES (?,?,?,?,?,?)",
                    (i, f"Person {i}", f"p{i}@example.com", statuses[i % 4],
                     "$2b$12$" + "x" * 53, f"2026-0{1 + i % 9}-01"))
    for i in range(1, 121):
        con.execute("INSERT INTO orders VALUES (?,?,?,?,?)",
                    (i, 1 + i % 40, 10.0 * i, "shipped" if i % 3 else "pending", f"2026-0{1 + i % 9}-15"))
    for i in range(1, 11):
        con.execute("INSERT INTO note VALUES (?,?,?)", (i, 1 + i % 40, "hello"))
    con.commit()
    con.close()
    settings = Settings(database_url=f"sqlite:///{db}", state_dir=tmp_path / "state", state_url=state_url,
                        embeddings=False)
    a = App(settings)
    a.bootstrap(progress=lambda *_: None)
    return a
