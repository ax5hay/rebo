# 07 · SQL safety

Five independent walls. Any one of them alone stops a write. Code: `safety.py`, `target.py`,
`catalog.py` (protected-column detection), `tools/localdb/02-readonly-user.sql`.

| # | Wall | Stops | Code |
|---|---|---|---|
| 1 | **Database user with SELECT only** | Any write, DDL, grant: the database refuses | `GRANT SELECT, SHOW VIEW ON jms.* TO 'reports_ro'` |
| 2 | **Read-only session** on every connection | Writes even if the user had rights | `TargetDB._read_only_session`: MySQL `SET SESSION TRANSACTION READ ONLY`; Postgres `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY`; SQLite `PRAGMA query_only=ON` |
| 3 | **Statement timeout** | Runaway joins, `SLEEP` that slipped through | MySQL `max_execution_time` (ms), MariaDB `max_statement_time` (s), Postgres `statement_timeout`; `REBO_QUERY_TIMEOUT_S` (default 30) |
| 4 | **Syntax-tree guard** | Non-SELECT, multi-statement, locks, `INTO`, server functions, unknown tables/columns, protected columns, unbounded rows | `safety.guard()` |
| 5 | **Rollback + fetch cap** | Lingering transactions, giant result sets in memory | `TargetDB.run`: `fetchmany(max_rows+1)`, then `rollback()` and close |

## 1. The guard, step by step (`guard(sql, dialect, schema, sensitive, allowed_tables, row_cap)`)

1. Strip whitespace and a trailing `;`. Empty → `GuardError("Empty SQL.")`.
2. `sqlglot.parse(sql, read=dialect)`. A parse error → `"SQL does not parse: …"`.
3. Exactly one statement, or `"Send exactly one SELECT statement."`
4. The root must be `exp.Select` or `exp.SetOperation` (UNION / INTERSECT / EXCEPT; `WITH` hangs
   off the select). Otherwise `"Only SELECT queries are allowed (got DELETE)."`
5. Walk **every node**. Reject `Insert, Update, Delete, Merge, Create, Drop, Alter, Command, Into,
   Lock, Set, Transaction, Commit, Rollback, Use, Show, Describe, Pragma, Copy, LoadData, Grant`.
   `Command` is sqlglot's catch-all for statements it doesn't model, so anything unknown is denied.
6. Reject functions `SLEEP, BENCHMARK, LOAD_FILE, GET_LOCK, RELEASE_LOCK, PG_SLEEP, DBLINK, LO_IMPORT,
   LO_EXPORT, PG_READ_FILE, XP_CMDSHELL, SYS_EXEC, SYS_EVAL`, whether parsed as known functions or `Anonymous`.
7. Every `exp.Table` that is not a CTE name must exist in the catalog (case-insensitive), or
   `"Table 'x' does not exist. Use search_schema to find the right table."` If
   `REBO_ALLOW_TABLES` is set, it must also be on that list.
8. **Column validation:** `sqlglot.optimizer.qualify.qualify(tree, schema=catalog, validate_qualify_columns=True)`.
   An unresolvable or ambiguous column → `"Column 'nope' could not be resolved. Check the columns
   with describe_table."` Other qualify failures (a dialect feature sqlglot cannot model) do not
   block; they add a warning and the database validates instead.
9. From the qualified tree, map every column to its real table through table aliases. Any
   `(table, column)` in the protected set → `"Column(s) t.c hold protected data and cannot be used."`
   This includes columns reached through `SELECT *`, because qualify expands stars.
10. If any projection is a star, the **expanded** (qualified) SQL is what runs. That way a protected
    column can never come back through `*`.
11. Apply the row cap: keep the author's `LIMIT` when it is ≤ cap, otherwise set `LIMIT cap`.
    The caller passes `row_limit + 1` so that one extra row reveals truncation.
12. Return `Guarded(sql, tables, columns, warnings)`; `sql` is printed by sqlglot in the target dialect.

Error messages are written **for the model**. Each names the tool that fixes the problem, so the
agent corrects itself instead of giving up.

## 2. Protected columns (detected, not configured)

`catalog.bootstrap` marks a column `sensitive=1` when any of these is true:

- Its name matches `passw|secret|token|api_key|private_key|ssn|social_security|tax_id|encrypt|cipher|hash|salt|otp|mfa|cvv|card_num|iban|routing_num|account_num|session_key|credential`.
- At least half of 25 sampled values look like ciphertext or hashes: Fernet (`gAAAA…`), bcrypt
  (`$2a$/$2b$/$2y$`), argon2, PEM blocks, or base64 of 60+ characters. Example: on JMS this catches
  `user_form_answer.text_answer` when it holds Fernet ciphertext; the 2026-09 workbook audit found
  210 production reports selecting that column.
- It matches `REBO_DENY_COLUMNS`: an optional regex on `table.column`, for anything a
  customer wants hidden that detection misses.

Effects: values are never stored in the catalog, never sent to the LLM, never indexed for
search, and the guard refuses any query that touches the column. `describe_table` shows it with
`"protected": true`, so the model knows it exists and avoids it.

Contact data (names, emails, phones) is **not** protected by default: reports legitimately need
it. A deployment that must hide it lists it in `REBO_DENY_COLUMNS`.

## 3. Execution details (`TargetDB.run`)

- Uses `engine.raw_connection()` and a DBAPI cursor with **no parameters**, so `%` in `LIKE '%x%'`
  and `:` in `'10:30'` are never treated as bind markers. That bug class affects
  SQLAlchemy's `text()`.
- `fetchmany(max_rows + 1)`: truncation is detected without loading everything.
- Cells are converted to JSON-safe values (`target.cell`): ISO dates, Decimal → float (or string
  when very large), bytes → `<n bytes>`.
- `finally: rollback(); close()`. Read-only or not, nothing stays open.

## 3b. Row-level security: each person's own database role (B-058, 2026-10-21)

Optional, PostgreSQL only. With `database_role: "{user}"` (or a pattern such as `"rebo_{user}"`) every
query asked for a person runs inside `SET LOCAL ROLE <their role>`, so the database's own policies
(`CREATE POLICY ... USING (owner = current_user)`) decide which rows they see. Off by default.

- Covers every path that runs a query for a person: the agent's probes, the validator and its checks,
  saved-report reuse, re-run, drill-down and schedules (`App.ask`, `App.rerun`, `App.drill`).
- `LOCAL` means the role ends with the transaction, which is always rolled back, so a pooled
  connection never carries one person's role to the next. A person without a role gets an error,
  never the login's rows (`tests/test_rls.py`, run against PostgreSQL).
- Setup: create a role per person (`CREATE ROLE ada NOLOGIN`), grant it SELECT and the policies,
  and let the bot's login switch to it (`GRANT ada TO reports_ro`).
- Not covered: bootstrap profiling and the value index run as the login, so **common values the
  login can see appear as hints to everyone**. On tables with row-level policies, give the login
  only what everyone may see, or list those tables' sensitive columns in `protected_columns`. The MCP
  server's `run_sql` is refused while this is on (an MCP client is not a person).
- Also fixed on the way: PostgreSQL sessions now `SET TRANSACTION READ ONLY` for the current
  transaction too (the session default only applies from the next one).

## 4. Probes vs the final report

| | `run_sql` tool (probe) | Output validator (final report) |
|---|---|---|
| Row cap | `probe_row_limit` (20) | `row_limit` (500) |
| Count | at most 12 per turn | once per presented report (plus retries) |
| On error | returns `{"error": …}` to the model | `ModelRetry` (the model must fix it; Pydantic AI retries up to 2 times) |
| 0 rows | returned as-is | first time: `ModelRetry` asking it to re-check literals and joins; second time accepted |

## 5. Tests

`tests/test_safety.py`: 11 rejected statement shapes, unknown table/column hints, protected column
blocked through `SELECT *`, LIMIT capping, CTE/UNION allowed, `%`/`:` literals preserved, canonical
hash stability. `tests/test_catalog.py::test_target_session_is_read_only` proves wall 2 on its own.
