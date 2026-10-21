-- store.SCHEMA as of commit 9b81192^ (before in-place migrations existed); used by tests/test_store.py

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
