# 09 · Data model (`state.db`)

One SQLite file at `$REPORTSBOT_STATE_DIR/state.db`, WAL mode, foreign keys on, or a Postgres database
when `state_url` is set (B-026). DDL: `store.SCHEMA` (created idempotently at start-up; for Postgres
`store._pg_schema()` derives it: `REAL` → `DOUBLE PRECISION`, `BLOB` → `BYTEA`, autoincrement →
identity, and each FTS5 table becomes a plain table with the same columns plus a generated `tsv
tsvector` and a GIN index). Code writes SQLite-style SQL with `?`; the Postgres connection translates
it, and full-text search goes through `Store.match`. Timestamps are Unix seconds. JSON columns are
TEXT. `cat_column.pos` keeps the column order (it was SQLite's `rowid`).

## Catalog (rebuilt by bootstrap)

### `cat_table`
| Column | Type | Meaning |
|---|---|---|
| `name` | TEXT PK | Table name as the DB reports it |
| `rows` | INTEGER | Exact row count at profiling time |
| `comment` | TEXT | DB table comment, if any |
| `description` | TEXT | LLM draft (doc 03 §4); NULL without `--describe` |
| `fingerprint` | TEXT | sha256(sorted `name:type`)[:16]; drives staleness |
| `profiled_at` | REAL | When |

### `cat_column`
| Column | Type | Meaning |
|---|---|---|
| `table_name`, `name` | PK | |
| `type` | TEXT | Lower-cased SQLAlchemy type string, e.g. `varchar(45)` |
| `nullable`, `is_pk` | INTEGER 0/1 | |
| `comment` / `description` | TEXT | DB comment / LLM draft |
| `sensitive` | INTEGER 0/1 | Protected: never selectable; values never stored |
| `stats` | JSON | `{null_rate, distinct, min, max, avglen}` (keys present when measured) |
| `top_values` | JSON | `[{value, count}]`, ≤ 1000, most frequent first; NULL for protected or free-text columns |

### `cat_join`
| Column | Meaning |
|---|---|
| `from_table`, `from_cols`, `to_table`, `to_cols` (PK) | Comma-joined for composite keys |
| `source` | `fk` (declared), `inferred` (doc 03 §6), `learned` (reserved; learned joins currently live in `knowledge` and are merged at query time) |
| `confidence` | 1.0 for fk; 0.9 × containment for inferred |

### Search tables
- `schema_fts(kind, table_name, column_name, text)`: FTS5; `kind` is `table` or `column`.
- `value_fts(value, table_name, column_name, freq)`: FTS5; only `value` is indexed.
- `embedding(ref TEXT PK, vector BLOB)`: `schema:<table>.<column or empty>` or `knowledge:<id>`; float32 × 384.

## Knowledge (never rebuilt; back it up)

### `knowledge`
| Column | Meaning |
|---|---|
| `id` | `ex_…` / `te_…` / `no_…` / `jo_…` + 12 hex |
| `kind` | `example` / `term` / `note` / `join` |
| `status` | `active` / `proposed` / `verified` / `stale` / `quarantined` / `retired` (doc 05 §2) |
| `scope` | `personal` / `team` / `org` |
| `owner`, `team` | Who taught it; their team at that time |
| `title` | Report title or the term itself |
| `question` | example: the user's original question |
| `body` | term/note/join: plain-language meaning |
| `sql` | example: full SQL; term: predicate; join: `a.x = b.y` |
| `sql_canonical` | `canonical_hash(sql)` for examples (indexed) |
| `tables` | JSON list of tables touched |
| `fingerprints` | JSON `{table: fingerprint}` at confirmation / last successful re-check |
| `result_signature` | JSON `{columns, rows, truncated}` at confirmation |
| `confirmations`, `confirmers` | Count; JSON list of distinct user ids |
| `rejections` | Times reported wrong |
| `uses`, `last_used_at` | Provenance hits |
| `verified_by`, `verified_at` | Curator and time of the last promotion |
| `source_turn` | Turn that created it |
| `supersedes` | Item this one replaced |
| `created_at`, `updated_at`, `valid_to` | `valid_to` is set when retired |

Indexes: `knowledge_canonical(sql_canonical)`, `knowledge_owner(owner, status)`.

### `knowledge_event` (append-only audit)
`id, item_id, at, actor ('system' or a user id), action ('created' | 'confirmed' | 'reported_wrong' | 'status:<new>'), from_status, to_status, note`.
Undo reads the last `status:%` event's `from_status`.

### `knowledge_fts(id UNINDEXED, title, question, body)`: FTS5 mirror of searchable text.

### `suggestion`
`id, turn_id, owner, payload (JSON Learnable: kind, title, body, sql), state ('open' | 'accepted' | 'dismissed'), created_at`.

## Conversations

### `conversation`
`id, owner, messages (Pydantic AI ModelMessages JSON, full history including tool calls), created_at, updated_at`.

### `turn`
| Column | Meaning |
|---|---|
| `id`, `conversation_id`, `owner`, `question` | |
| `kind` | `report` / `clarify` / `answer` / `error` |
| `payload` | JSON of exactly what was shown (incl. rows) |
| `sql` | Report SQL as written by the model (before the row cap) |
| `provenance` | JSON `{label, item_ids, text}` |
| `feedback` | `correct` / `wrong` / NULL |
| `usage` | JSON `{requests, input_tokens, output_tokens, tool_calls}` |

### `meta`
`key, value(JSON)`: `bootstrapped_at`, `dialect`.

## Retention

Turns hold result rows, which may include personal data from the target DB. Purge old turns with
a scheduled `DELETE FROM turn WHERE created_at < …` according to the host's retention policy;
knowledge items keep only SQL, titles and definitions, never rows.

## Added later (in-place migrations in `store.MIGRATIONS`)

- `knowledge_event.turn_id`: the turn whose feedback caused the event, so `undo_feedback` reverses exactly that.
- `turn.feedback_note`: feedback in the user's own words.
- `request(id, kind, target, requester, item_id, turn_id, text, status, resolver, resolution, created_at, updated_at)`:
  fix/access/config requests. `kind` is `fix_knowledge`, `fix_report`, `access`, `config` or `other`;
  `target` is `admin` or `owner`; `status` is `open`, `done` or `declined`.
- `config_event(id, at, actor, previous, current, note)`: every configuration change made through
  the API, with the full previous file for rollback.
