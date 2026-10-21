# 24 · Operator runbook

Routine tasks for whoever runs the bot. Commands assume the repository folder; in the production
stack prefix them with `docker compose -f compose.prod.yml exec bot uv run --no-sync`. Settings and
deployment are in doc 13; roles in doc 22.

## 1. Back up and restore

**What matters.** The bot's memory is the state store: knowledge with its full history, feedback,
conversations, requests, jobs and schedules. The catalog inside it can be rebuilt (`bootstrap`);
nothing else can. The reported database is never written, so it needs no backup from us.

| State store | Back up | Restore |
|---|---|---|
| SQLite (`data/state.db`, default) | `sqlite3 data/state.db ".backup data/state-$(date +%F).db"`: safe while the bot runs (WAL) | stop the bot, copy the backup over `data/state.db`, start |
| Postgres (`state_url`) | `pg_dump -Fc -d "$STATE_URL" > state-$(date +%F).dump` | stop the bot, `pg_restore --clean --if-exists -d "$STATE_URL" state-….dump`, start |

Also keep a copy of `reportsbot.yaml` (the configuration page keeps every version in
`config_event`, but that table is inside the store). An editable copy of what was learned, readable
without the bot: `reportsbot knowledge export knowledge-$(date +%F).yaml`.

## 2. Upgrade the bot

1. Back up (§1).
2. Get the new version (`git pull`, a new bundle, or a new image) and `uv sync --frozen --all-extras`
   (images: `docker compose -f compose.prod.yml build bot`).
3. Start it. The state store is upgraded in place to the latest schema at start-up (Alembic,
   doc 09); there is no separate migrate command and no downgrade: to go back, restore the backup
   and the old version together.
4. `reportsbot config check`, then ask one known question and confirm it answers.

## 3. After the reported database changes (migrations of the host application)

1. `reportsbot bootstrap` (add `--describe` to draft descriptions of new tables with the fast model).
   It re-reads structure, statistics and values, and then re-checks saved knowledge.
2. Or, when only knowledge must be re-checked: `reportsbot revalidate`.
3. Items whose tables changed become **stale** and stop being used; their owners see "N of your
   saved items need a re-check". Renamed columns usually come back by themselves once fixed
   (doc 17 §4). Admins find the rest on the review page.
4. With `notify_url` set, every item that goes stale is announced as `item_stale`.

## 4. Rotate keys and secrets

| Secret | Where | Rotate |
|---|---|---|
| LLM keys (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`) | environment / `.env` only | create the new key at the provider, replace it in `.env`, restart the bot, revoke the old key |
| `REPORTSBOT_JWT_SECRET` (JMS adapter) | environment | change it in JMS and the bot together; tokens signed with the old secret stop working at once |
| Read-only database password (inside `database` / `REPORTSBOT_DATABASE_URL`) | environment or `reportsbot.yaml` | add the new password in the database, update the URL, restart, drop the old one |
| `STATE_DB_PASSWORD` (Postgres state) | `.env` | `ALTER USER reportsbot PASSWORD '…'` in `state-db`, update `.env`, restart `bot` |
| `OAUTH2_PROXY_CLIENT_SECRET`, `OAUTH2_PROXY_COOKIE_SECRET` | `.env` | update and restart `auth`; a new cookie secret signs everyone out |

Keys never go into `reportsbot.yaml` or git (`tools/export_bundle.py --check-only` and the
pre-commit hook refuse files that contain them).

## 5. Move the state from SQLite to Postgres

1. `docker compose up -d state-db` (or any Postgres 13+), `uv sync --extra postgres`.
2. Stop the bot.
3. `uv run python tools/copy_state.py data/state.db postgresql://user:pw@host:5432/db`: copies every
   table (knowledge with history, conversations, turns, catalog, jobs, schedules, cache) into an
   empty store and prints the row counts. It refuses a target that already holds knowledge.
4. Set `state_url: postgresql://…` (or `REPORTSBOT_STATE_URL`) and start the bot. Keep
   `data/state.db` until you are satisfied.

Verified 2026-10-21: the JMS catalogue (207 tables, 2,769 columns, 439 joins, 2,976 embeddings and
search rows) copied from SQLite to Postgres 18.6 and searched there. The copy tool upgrades the
source file to the current schema when it opens it (as the bot would).

## 6. Export and import knowledge

- Everything learned, as editable YAML: Admin page → Export / import, or
  `reportsbot knowledge export knowledge.yaml` (`--all` includes withdrawn items).
- Edit titles, questions, definitions and SQL; set `status: verified` to share or `retired` to
  withdraw; add new items without an `id`. Deleting an entry from the file does nothing.
- Admin page: **Preview changes** lists every change before **Import** is allowed. CLI:
  `reportsbot knowledge import knowledge.yaml` (acts as an owner; recorded under `--as <name>`).
- Every imported change is in the item's history and can be undone like an edit in the UI.

## 7. Health and routine checks

- `GET /api/health` (the compose health checks use it), Phoenix on `127.0.0.1:6006` for traces.
- Admin page → Usage: confirmation rate per week, what is reported wrong, open requests by age,
  cost per day. Requests older than 7 days are highlighted.
- Background jobs: `SELECT status, COUNT(*) FROM job GROUP BY status`; `failed` jobs keep their error.
- Logs: the bot logs to stdout (`docker compose logs bot`).
