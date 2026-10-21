"""The bot's own state (catalog, knowledge, conversations, audit): one SQLite file by default, or a
Postgres database when `state_url` is set (B-026).

Layout and every column are documented in docs/09-data-model.md. Code everywhere writes SQLite-style
SQL with `?` placeholders; the Postgres connection translates it, and the FTS5 tables become plain
tables with a generated tsvector column (`Store.match` hides the difference).
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Catalog: what the target database contains (rebuilt by `rebo bootstrap`).
CREATE TABLE IF NOT EXISTS cat_table (
    name TEXT PRIMARY KEY,
    rows INTEGER,
    comment TEXT,
    description TEXT,            -- LLM draft, trust = draft
    fingerprint TEXT NOT NULL,   -- hash of column names + types; drives staleness
    profiled_at REAL
);
CREATE TABLE IF NOT EXISTS cat_column (
    table_name TEXT NOT NULL REFERENCES cat_table(name) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    nullable INTEGER NOT NULL,
    is_pk INTEGER NOT NULL DEFAULT 0,
    comment TEXT,
    description TEXT,
    sensitive INTEGER NOT NULL DEFAULT 0,  -- never selectable, values never shown
    stats TEXT,                  -- JSON: null_rate, distinct, min, max, avglen
    top_values TEXT,             -- JSON list of {value, count} for categorical columns
    pos INTEGER,                 -- column order in the table
    PRIMARY KEY (table_name, name)
);
CREATE TABLE IF NOT EXISTS cat_join (
    from_table TEXT NOT NULL, from_cols TEXT NOT NULL,
    to_table TEXT NOT NULL, to_cols TEXT NOT NULL,
    source TEXT NOT NULL,        -- fk | inferred | learned
    confidence REAL NOT NULL,
    PRIMARY KEY (from_table, from_cols, to_table, to_cols)
);
CREATE VIRTUAL TABLE IF NOT EXISTS schema_fts USING fts5(
    kind, table_name, column_name, text, tokenize='porter unicode61'
);
CREATE VIRTUAL TABLE IF NOT EXISTS value_fts USING fts5(
    value, table_name UNINDEXED, column_name UNINDEXED, freq UNINDEXED, tokenize='unicode61'
);
CREATE TABLE IF NOT EXISTS embedding (
    ref TEXT PRIMARY KEY,        -- 'schema:<table>.<col>' or 'knowledge:<id>'
    vector BLOB NOT NULL
);

-- Knowledge: everything learned from people. Never deleted, only closed (valid_to).
CREATE TABLE IF NOT EXISTS knowledge (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,          -- example | term | note | join
    status TEXT NOT NULL,        -- active | proposed | verified | stale | quarantined | retired
    scope TEXT NOT NULL,         -- personal | team | org
    owner TEXT NOT NULL,
    team TEXT,
    title TEXT NOT NULL,
    question TEXT,               -- example: the question it answered
    body TEXT,                   -- term/note: the definition or fact, in plain words
    sql TEXT,                    -- example: full SQL; term: predicate fragment; join: ON clause
    sql_canonical TEXT,          -- hash of normalised SQL, to recognise the same query
    tables TEXT,                 -- JSON list of tables it touches
    fingerprints TEXT,           -- JSON {table: fingerprint} at the time it was confirmed
    result_signature TEXT,       -- JSON {columns, row_count} at confirmation
    confirmations INTEGER NOT NULL DEFAULT 0,
    confirmers TEXT NOT NULL DEFAULT '[]',
    rejections INTEGER NOT NULL DEFAULT 0,
    uses INTEGER NOT NULL DEFAULT 0,
    last_used_at REAL,
    verified_by TEXT,
    verified_at REAL,
    source_turn TEXT,
    supersedes TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    valid_to REAL
);
CREATE INDEX IF NOT EXISTS knowledge_canonical ON knowledge(sql_canonical);
CREATE INDEX IF NOT EXISTS knowledge_owner ON knowledge(owner, status);
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    id UNINDEXED, title, question, body, tokenize='porter unicode61'
);
CREATE TABLE IF NOT EXISTS knowledge_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL,
    at REAL NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    note TEXT
);
-- Pending "remember this?" suggestions extracted from corrections.
CREATE TABLE IF NOT EXISTS suggestion (
    id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    owner TEXT NOT NULL,
    payload TEXT NOT NULL,       -- JSON candidate (kind, title, body, sql, tables)
    state TEXT NOT NULL DEFAULT 'open',  -- open | accepted | dismissed
    created_at REAL NOT NULL
);

-- Conversations.
CREATE TABLE IF NOT EXISTS conversation (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    messages TEXT NOT NULL DEFAULT '[]',  -- pydantic-ai message history JSON
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS turn (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversation(id),
    owner TEXT NOT NULL,
    question TEXT NOT NULL,
    kind TEXT NOT NULL,          -- report | clarify | answer | error
    payload TEXT NOT NULL,       -- JSON of what was shown
    sql TEXT,
    provenance TEXT,             -- JSON {label, item_ids}
    feedback TEXT,               -- correct | wrong | null
    usage TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- Requests from people who cannot make a change themselves (fix shared knowledge, access, config).
CREATE TABLE IF NOT EXISTS request (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,          -- fix_knowledge | fix_report | access | config | other
    target TEXT NOT NULL,        -- admin | owner (who can resolve it)
    requester TEXT NOT NULL,
    item_id TEXT,
    turn_id TEXT,
    text TEXT NOT NULL,          -- the request in the requester's own words
    status TEXT NOT NULL DEFAULT 'open',  -- open | done | declined
    resolver TEXT,
    resolution TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
-- Every configuration change (owners only), with the full previous file for rollback.
CREATE TABLE IF NOT EXISTS config_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL,
    actor TEXT NOT NULL,
    previous TEXT,
    current TEXT NOT NULL,
    note TEXT
);
"""

# Postgres stand-ins for the FTS5 tables: same columns plus a generated tsvector (english = stemmed
# like FTS5 "porter", simple = unstemmed like "unicode61"), searched by Store.match.
_PG_FTS = {
    "schema_fts": ("english", "kind TEXT, table_name TEXT, column_name TEXT, text TEXT",
                   "coalesce(kind,'') || ' ' || coalesce(table_name,'') || ' ' || coalesce(column_name,'') || ' ' "
                   "|| coalesce(text,'')"),
    "value_fts": ("simple", "value TEXT, table_name TEXT, column_name TEXT, freq INTEGER", "coalesce(value,'')"),
    "knowledge_fts": ("english", "id TEXT, title TEXT, question TEXT, body TEXT",
                      "coalesce(title,'') || ' ' || coalesce(question,'') || ' ' || coalesce(body,'')"),
}


def _pg_schema() -> str:
    def fts(m: re.Match) -> str:
        cfg, cols, doc = _PG_FTS[m.group(1)]
        return (f"CREATE TABLE IF NOT EXISTS {m.group(1)} ({cols}, tsv tsvector GENERATED ALWAYS AS "
                f"(to_tsvector('{cfg}', {doc})) STORED);\n"
                f"CREATE INDEX IF NOT EXISTS {m.group(1)}_tsv ON {m.group(1)} USING gin(tsv);")
    s = re.sub(r"PRAGMA [^;]*;", "", SCHEMA)
    s = re.sub(r"CREATE VIRTUAL TABLE IF NOT EXISTS (\w+) USING fts5\([^()]*\);", fts, s)
    s = s.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY")
    return re.sub(r"\bBLOB\b", "BYTEA", re.sub(r"\bREAL\b", "DOUBLE PRECISION", s))


class _PgConnection:
    """A psycopg connection that takes the sqlite3-style calls this code base makes: `?` placeholders,
    execute/executemany returning a cursor, executescript, commit/rollback (autocommit outside
    Store.tx, so no idle transactions hold locks)."""

    def __init__(self, url: str):
        import psycopg
        from psycopg.rows import dict_row
        self.conn = psycopg.connect(re.sub(r"^postgres(ql)?(\+\w+)?://", "postgresql://", url),
                                    row_factory=dict_row, autocommit=True)

    @staticmethod
    def _sql(sql: str) -> str:
        return sql.replace("%", "%%").replace("?", "%s")

    def execute(self, sql: str, args: tuple | list = ()):
        cur = self.conn.cursor()
        cur.execute(self._sql(sql), tuple(args)) if args else cur.execute(sql)
        return cur

    def executemany(self, sql: str, rows):
        cur = self.conn.cursor()
        cur.executemany(self._sql(sql), [tuple(r) for r in rows])
        return cur

    def executescript(self, script: str) -> None:
        self.conn.execute(script)

    def commit(self) -> None:  # autocommit: statements outside Store.tx are already committed
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.conn.close()


def migrate(store: "Store") -> None:
    """Bring the state store to the latest Alembic revision (src/rebo/migrations). A state file from
    before Alembic has no Alembic version stamp: the idempotent baseline and the add-if-missing column
    revision upgrade it in place, then it is stamped."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    engine = create_engine(store.sqlalchemy_url)
    try:
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
    finally:
        engine.dispose()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Store:
    """Thin wrapper over sqlite3 (a file path) or Postgres (a postgresql:// URL). One connection per
    thread; SQLite runs in WAL mode so readers run alongside the writer."""

    def __init__(self, path: Path | str):
        self.url = str(path)
        self.dialect = "postgresql" if re.match(r"postgres(ql)?(\+\w+)?://", self.url) else "sqlite"
        if self.dialect == "sqlite":
            self.path = Path(path)
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        if self.dialect == "sqlite":
            self.db.execute("PRAGMA journal_mode=WAL")  # persistent per file; cannot run inside a migration
        migrate(self)

    @property
    def sqlalchemy_url(self) -> str:
        if self.dialect == "sqlite":
            return f"sqlite:///{self.path}"
        return re.sub(r"^postgres(ql)?(\+\w+)?://", "postgresql+psycopg://", self.url)

    @property
    def db(self) -> Any:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            if self.dialect == "postgresql":
                conn = _PgConnection(self.url)
            else:
                conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    @contextmanager
    def tx(self) -> Iterator[Any]:
        db = self.db
        if self.dialect == "postgresql":
            with db.conn.transaction():
                yield db
            return
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise

    def all(self, sql: str, args: tuple | dict = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def one(self, sql: str, args: tuple | dict = ()) -> dict[str, Any] | None:
        row = self.db.execute(sql, args).fetchone()
        return dict(row) if row else None

    def match(self, table: str, fts: str, columns: str, *, limit: int) -> list[dict[str, Any]]:
        """Full-text search on one of the *_fts tables, best match first. `fts` is the FTS5-style query
        built by retrieval.fts_query: quoted tokens, optionally prefix-starred, joined by OR."""
        if self.dialect == "sqlite":
            return self.all(f"SELECT {columns} FROM {table} WHERE {table} MATCH ? ORDER BY bm25({table}) LIMIT ?",
                            (fts, limit))
        terms = [re.sub(r"\W", "", w) + (":*" if star else "") for w, star in re.findall(r'"([^"]*)"(\*?)', fts)]
        query = " | ".join(t for t in terms if t and not t.startswith(":"))
        if not query:
            return []
        cfg = _PG_FTS[table][0]
        return self.all(f"SELECT {columns} FROM {table} WHERE tsv @@ to_tsquery('{cfg}', ?) "
                        f"ORDER BY ts_rank(tsv, to_tsquery('{cfg}', ?)) DESC LIMIT ?", (query, query, limit))

    def meta_get(self, key: str, default: Any = None) -> Any:
        row = self.one("SELECT value FROM meta WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def meta_set(self, key: str, value: Any) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, json.dumps(value)))


def now() -> float:
    return time.time()
