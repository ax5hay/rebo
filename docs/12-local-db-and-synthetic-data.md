# 12 · Local test database: snapshot and synthetic data

Goal: a database **structurally identical to JMS staging**, on any PC, with realistic rows and
**no real data**.

```
JMS staging RDS ──snapshot.py (aws-vault, VPN)──► fixtures/jms_staging/{schema.sql, profile.json, manifest.json}
                                                         │ (committed, portable)
docker compose up -d db ◄── schema.sql (initdb) ─────────┘
        │
synth.py ◄── profile.json ──► local MySQL 8.0.44 filled with synthetic rows
        │
reportsbot bootstrap ──► bot learns the local copy
```

## 1. The snapshot (`tools/snapshot/snapshot.py`)

### Run it (JMS staging)

```bash
# needs: AWS creds via aws-vault, the VPN, Python with pymysql + boto3
cd reports-bot/tools/snapshot
MSYS_NO_PATHCONV=1 aws-vault exec akshay-orchid -- \
  python snapshot.py --ssm /orchid/app-staging/JMS_DATABASE_URL --out ../../fixtures/jms_staging
```

- `MSYS_NO_PATHCONV=1` is needed in Git Bash on Windows; otherwise `/orchid/...` is rewritten to
  `C:/Program Files/Git/orchid/...`.
- The URL comes from SSM. If the public RDS endpoint is unreachable, the script looks up the RDS
  instance's private ENI IP through boto3 and connects over the VPN (the same approach as
  `backend/scripts/schema_harness/connection.py`, copied in so the tool is self-contained).
- Any other MySQL works with `--url mysql+pymysql://user:pass@host:3306/db`.
- The session is `SET SESSION TRANSACTION READ ONLY`. It takes about 15 minutes on staging
  (profiling 207 tables, then reference measurement).

### What it captures

| File | Content | Real data? |
|---|---|---|
| `schema.sql` | `SHOW CREATE` for every table (and views/triggers/routines when present) with `DEFINER` and `AUTO_INCREMENT=n` stripped, wrapped in `SET FOREIGN_KEY_CHECKS=0/1` | No |
| `profile.json` `tables.*` | row count, comment, FKs, and per column: type, nullability, key, default, extra, comment, `null_rate`, `distinct`, `min`/`max` (numbers/dates), `avglen`/`maxlen` (strings) | Aggregates only |
| `profile.json` `…columns[].values` | `{value, count}` catalog for categorical columns that pass the privacy filter below | Business vocabulary only |
| `profile.json` `implicit_refs` | Undeclared references: `{table, column, ref_table, ref_column, containment, by_name, alternatives}` | Names and a ratio only |
| `manifest.json` | server version, charset/collation, sql_mode, capture time, object counts, `row_data_copied: false` | No |

**Staging snapshot of 2026-10-20:** MySQL 8.0.44, 207 tables, 0 views/triggers/routines,
2,769 columns, 440 FKs, 1,014,560 rows (counted, not copied), 554 value catalogs, 51 implicit references.

### The privacy filter for value catalogs (`_catalogable`)

A column's values are catalogued only if **all** of these hold:

1. It has values and its type is `enum`, `set`, `tinyint`, `smallint`, `char`, `varchar` or `bit`.
2. It is not a primary key or an `*_id` / `id` column.
3. Its name does **not** match `_NEVER`: first/last/middle/maiden name, email, phone, mobile, fax,
   ssn, social, address, street, city, zip, postal, dob, birth, passport, license, token, password,
   secret, hash, salt, key, sid, domain, ip address, signature, account, routing, iban, card, cvv,
   latitude, longitude, geo, uuid, guid, session, cookie, url, link, file, path, `from_*`.
4. Then either
   - **lookup rule:** the table has ≤ 2,000 rows, the column name ends in `name|title|label|reason|status|stage|type|category|code`,
     the table name does **not** look like people or free text (`user, admin, contact, agency, clinic,
     provider, family, profile, person, member, party, lead, recipient, staff, employee, customer,
     patient, donor, parent, baby, child, spouse, partner, *_log, *_note, *_message, *_email, *_sms,
     *_text, *_history, *_chat`), and it has ≤ 200 distinct values. This captures `status.status`,
     `template_stage.title`, `service_level.name`, `archive_reason.reason`, `event.event_name`; **or**
   - **general rule:** ≤ 40 distinct values, varchar ≤ 64, and the name does not match `_PERSONAL`
     (`name, note, text, answer, desc, comment, body, html, content, message, subject, title, label, question, agent, referrer`).
5. Finally, if **any** value looks like an email, Fernet ciphertext, phone number or SSN, the whole
   catalog for that column is dropped.

The filter was tightened in three passes during the first capture, after manual review of the
catalogued column list:
1. A Twilio messaging-service SID and agency subdomains were blocked (`sid`, `domain`).
2. Lookup-table labels were allowed, because the bot needs them to resolve phrases like "in Screening".
3. `delivery_baby.baby_name` and free-text log titles were blocked (`baby`, `child`, log/note/history tables).

Use `--no-values` to omit all catalogs.

### Implicit references (`implicit_refs`)

For integer columns named like `*_id|*id|*_by|*_to|*_owner` that are not declared FKs and have at
least 3 distinct non-zero values: compare their distinct staging values (up to 5,000) with every
single-column integer primary key, in Python. A key qualifies with containment ≥ 0.95 and at least
as many keys as the child has values. The ranking key is (name match: same column name = 2.0,
table-name stem = 1.5, none = 0) → containment → tighter parent. `by_name=false` matches are
recorded with alternatives but are **not trusted**: small dense id ranges overlap by coincidence.
For example, `activity_feed.action_by_id` matched a profile-answer table only by value overlap.
This metadata is used only by the synthetic generator. The bot never reads it; it must infer or
learn joins itself.

## 2. Local MySQL (`docker-compose.yml`)

```bash
docker compose up -d db     # mysql:8.0.44 on host port 3307, db "jms", root/root
```

- First start runs `fixtures/jms_staging/schema.sql` and then `tools/localdb/02-readonly-user.sql`
  (creates `reports_ro` / `reports_ro` with `SELECT, SHOW VIEW` on `jms.*`).
- `--sql-mode=NO_ENGINE_SUBSTITUTION`, `utf8mb4_0900_ai_ci`: the same as staging (`manifest.json`).
- Data lives in the `dbdata` volume. `docker compose down -v` resets everything.

## 3. Synthetic rows (`tools/synth/synth.py`)

```bash
uv run --extra synth python tools/synth/synth.py                  # defaults: local db, cap 3000, seed 7
uv run --extra synth python tools/synth/synth.py --cap 20000 --scale 2 --seed 42
```

### Algorithm

1. **Structure** from the local `information_schema`: columns (type, nullability, key, extra,
   lengths, precision), declared FKs (composite aware), unique indexes.
2. **Row counts:** `min(cap, round(staging_rows × scale))`. Tables empty on staging get
   `--min-rows` (default 0). Any parent of a NOT NULL FK gets at least 1 row.
3. **Keys first:** every single-column integer PK gets keys `1..n` before any row is generated,
   so references can point at parents generated later (FK cycles), with FK checks off during load.
4. **Order:** `graphlib.TopologicalSorter` over FK edges; a cycle is broken by dropping one of
   its edges and retrying.
5. **Per column, in priority order:**
   - integer single PK → row number;
   - declared FK → a random parent key (composite FKs take all columns from one parent row);
     NULL at the staging null rate if nullable;
   - trusted implicit reference (`by_name`, not self unless `parent*`) → a random parent key;
   - `auto_increment` → row number;
   - staging null rate → NULL;
   - **value catalog** → weighted choice with the staging frequencies (this is how `gc_case.case_type`
     comes out as donor/surrogate/sperm_donor in staging proportions);
   - enum/set → one of the declared options;
   - `tinyint(1)` / bit → 0/1;
   - integers and decimals → uniform within the staging min/max (clamped to type range);
   - dates and times → uniform within the staging min/max;
   - strings by name semantics (Faker `en_US`): email, first/last name, phone, zip, state, city,
     address, url, color, uuid, ssn, names, titles; otherwise text sized to the staging average
     length; JSON → `{}`.
6. **Uniqueness:** PK (non-simple) and every unique index are tracked. String collisions get a
   `-n` suffix, integer collisions take the row number, and anything else drops the row
   (up to 3n attempts).
7. **Load:** `DELETE` all tables, `FOREIGN_KEY_CHECKS=0`, `UNIQUE_CHECKS=0`, batched `executemany`
   of 1,000 rows, commit.

Deterministic: Faker and `random` are both seeded with `--seed`.

### Result on this machine (2026-10-21)

`{"database": "jms", "tables": 207, "rows": 87941, "seed": 7, "cap": 3000}` in about 5 minutes.
Spot checks:
- `gc_case` breakdown: donor/intake/active 175, surrogate/intake/active 118, sperm_donor/intake/active 48, …
- 411 of 413 `gc_case` rows join to both `contact` (via `gc_id`) and `status`.
- Contact names and emails are Faker values.

### Known limits (by design)

- **Columns are independent.** Each column follows its own staging distribution, but
  correlations between columns are not modelled (for example `stage` vs `case_type`, or dates that
  should be ordered such as created < completed). Queries still run and return plausible counts;
  exact staging proportions per combination are not reproduced. The next step, if needed, is
  LLM-written column-group generators (NeMo Data Designer pattern), described in doc 15.
- Ciphertext columns get Faker text, so the bot's ciphertext detector will not fire on the local
  copy (it does on staging).
- Free-text columns are lorem-style text.
