"""Copy the bot's whole state (knowledge with history, conversations, turns, catalog, jobs, ...) from
one store to another, e.g. from data/state.db to Postgres. Stop the bot first.

    uv run python tools/copy_state.py data/state.db postgresql://user:pw@host/db

The target is created/upgraded to the latest schema and must hold no knowledge yet. Search indexes
are copied as rows; on Postgres their tsvector is generated again. See docs/24-runbook.md.
"""
from __future__ import annotations

import sys

from rebo.store import _PG_FTS, Store

FTS_COLUMNS = {t: [c.split()[0] for c in cols.split(", ")] for t, (_, cols, _) in _PG_FTS.items()}


def tables(store: Store) -> list[str]:
    from sqlalchemy import create_engine, inspect
    names = inspect(create_engine(store.sqlalchemy_url)).get_table_names()
    shadow = tuple(f"{t}_{s}" for t in FTS_COLUMNS for s in ("data", "idx", "content", "docsize", "config"))
    fts = [t for t in FTS_COLUMNS if store.dialect == "sqlite" or t in names]
    return sorted({n for n in names if n != "alembic_version" and not n.startswith(shadow)} - set(FTS_COLUMNS)) + fts


def copy(src: Store, dst: Store) -> dict[str, int]:
    if dst.one("SELECT COUNT(*) AS n FROM knowledge")["n"]:
        raise SystemExit("The target already holds knowledge; copy only into an empty store.")
    counts = {}
    order = ["cat_table", "cat_column"]  # parents before children (foreign keys)
    for table in order + [t for t in tables(src) if t not in order]:
        sample = src.all(f"SELECT * FROM {table} LIMIT 1")
        cols = FTS_COLUMNS.get(table) or (list(sample[0]) if sample else [])
        rows = src.all(f"SELECT {', '.join(cols)} FROM {table}") if sample else []
        with dst.tx() as db:
            db.execute(f"DELETE FROM {table}")
            if rows:
                db.executemany(f"INSERT INTO {table}({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})",
                               [tuple(r[c] for c in cols) for r in rows])
        counts[table] = len(rows)
    if dst.pgvector:  # vectors searched in the database: fill the pgvector column from the copied bytes
        import numpy as np

        from rebo.retrieval import _pgvec
        rows = dst.all("SELECT ref, vector FROM embedding")
        with dst.tx() as db:
            db.executemany("UPDATE embedding SET vec=?::vector WHERE ref=?",
                           [(_pgvec(np.frombuffer(bytes(r["vector"]), dtype=np.float32)), r["ref"]) for r in rows])
    if dst.dialect == "postgresql":  # identity columns continue after the copied ids
        for table in ("knowledge_event", "config_event"):
            dst.db.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                           f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
    return counts


if __name__ == "__main__":
    print(copy(Store(sys.argv[1]), Store(sys.argv[2])))
