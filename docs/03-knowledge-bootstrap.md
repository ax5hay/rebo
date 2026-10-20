# 03 · Knowledge bootstrap: learning the database without config

`reportsbot bootstrap [--describe]` → `App.bootstrap()` → `catalog.bootstrap(target, store, index, …)`.
It runs on first install, after migrations, and on a schedule (nightly is fine). It is idempotent:
the catalog is rebuilt, while learned knowledge and learned joins are untouched and then re-checked.

Research basis: profiling-generated metadata beat BIRD's hand-written metadata and held BIRD #1
(Shkapenyuk et al., arXiv 2505.19988). Value indexing is how CHESS and ktx map literals to
columns. Both are summarised in doc 16.

## Pipeline

```
introspect ─► profile (4 threads) ─► detect protected ─► [describe with LLM, 8 threads]
     ─► write catalog + FTS docs + value index ─► infer joins ─► [embed docs] ─► revalidate knowledge
```

### 1. Introspect (`TargetDB.introspect`)

SQLAlchemy `inspect(engine)` collects tables, columns (name, type string, nullability, comment),
primary keys, foreign keys and table comments. It is dialect-neutral (MySQL, MariaDB, Postgres,
SQLite, SQL Server, Snowflake, BigQuery through their SQLAlchemy dialects). `REPORTSBOT_ALLOW_TABLES`
limits the set.

### 2. Profile (`TargetDB.profile_table`)

Per table, one aggregate query plus one `GROUP BY` per categorical column:

| Statistic | SQL | Kept as |
|---|---|---|
| Row count | `COUNT(*)` on the full table | `cat_table.rows` |
| Null rate | `SUM(CASE WHEN c IS NULL …)/rows` | `stats.null_rate` |
| Distinct count | `COUNT(DISTINCT c)` (skipped for JSON/CLOB/binary) | `stats.distinct` |
| Min / max | numbers and dates | `stats.min`, `stats.max` |
| Average length | `AVG(CHAR_LENGTH(c))` for strings | `stats.avglen` |
| Top values | `GROUP BY c ORDER BY COUNT(*) DESC LIMIT 1000` when the column is a string with avg length ≤ 60, or an integer with ≤ 50 distinct values | `cat_column.top_values` = `[{value, count}]` |

Tables over 200,000 rows are profiled on a `LIMIT 200000` sample (the row count stays exact).
A failing table is logged and skipped, never fatal.

Free text is recognised by **measured average length**, not by type name, because `TEXT` is the
ordinary string type in SQLite and Postgres.

### 3. Detect protected columns

See doc 07 §2: name pattern, ciphertext/hash value pattern on 25 sampled rows, or
`REPORTSBOT_DENY_COLUMNS`. Protected columns keep their name and type in the catalog (so the
model can avoid them), but no values or statistics samples.

### 4. Draft descriptions (optional, `--describe`)

`App._describe_table(payload)` sends one table at a time to the **fast model** (Haiku 5.5) with
typed output `TableDoc {table: str, columns: {name: meaning}}`. The payload holds the table name,
row count, comment, foreign keys, and per column the type, statistics and up to 8 sample values
(never for protected columns). The instruction tells the model to describe only what the evidence
supports and never invent business rules.

- Descriptions are **drafts**. The prompt calls them "about", never authoritative. Users override
  them by teaching (`term` / `note`).
- They are cached by table fingerprint, so re-running bootstrap only re-describes changed tables.
- Cost on JMS staging (207 tables) is about 207 short Haiku calls.

### 5. Write the catalog and indexes

- `cat_table`, `cat_column`, `cat_join` (`source='fk'`, confidence 1.0).
- `schema_fts` has one **table doc** per table (split name + comment + description + split column
  names) and one **column doc** per column (split table and column name + comment + description +
  up to 12 sample string values). Identifiers are split for search: `gc_case.sperm_donor` →
  `gc case sperm donor`.
- `value_fts` has every top value (strings, 1–80 chars) of non-protected columns as
  `(value, table, column, freq)`. This is how "Screening", "sperm donor" or a status name
  resolves to `status.status = 'Psychological Screening'` with no glossary.

### 6. Infer undeclared joins (`_infer_joins`)

For each column that is not a declared FK, not the table's own single PK, integer- or string-typed,
and named like `*_id` / `*id`:

1. Candidate parents: tables whose single-column PK has **the same column name**, plus tables
   named after the stem (`status_id` → `status`, `statuses`, `statu`).
2. Skip columns with fewer than 3 distinct values.
3. `TargetDB.containment()`: the share of up to 500 sampled distinct child values that exist in the
   parent key, computed in SQL.
4. ≥ 0.90 → `cat_join(source='inferred', confidence=0.9 × share)`.

Inferred joins cost 1.5 in path finding, versus 1.0 for declared and 0.8 for learned, so a person's
teaching always wins. Joins that no name hints at (JMS: `family.ip_1_id → contact.contact_id` would
be one if it were not declared) are left to the agent's exploration and to user teaching; a wrong
guess would be worse than none.

### 7. Embed (optional, when `fastembed` is installed and `REPORTSBOT_EMBEDDINGS=true`)

Every `schema_fts` doc is embedded locally with `snowflake/snowflake-arctic-embed-s` (33M params,
384-d, ONNX, CPU, 0.13 GB download, MTEB retrieval NDCG@10 51.98) and stored as float32 BLOBs in
`embedding`. Knowledge items are embedded when created.

### 8. Re-check knowledge

`App.revalidate()` runs at the end (doc 05 §7), so a migration that broke a saved report is
caught on the next bootstrap.

## Output on JMS staging

The 2026-10-20 snapshot (`fixtures/jms_staging/manifest.json`) has 207 tables, 2,769 columns,
440 declared FKs and 554 categorical value catalogs. After `synth.py` fills the local copy,
`reportsbot bootstrap` prints its own counts (tables, columns, foreign_keys, inferred_joins,
protected_columns, indexed_values, described_tables). Doc 17 records the measured run.

## What bootstrap deliberately does not do

- It reads no business meaning from config files.
- It never copies rows out of the database beyond the catalog statistics and categorical values
  above. The catalog lives in the bot's own `state.db`, next to the database it describes.
- It never guesses a join that neither a name nor the data supports.
