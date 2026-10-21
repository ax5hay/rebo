# ReBo: operations guide

Day-to-day running of a ReBo server. For development, checks and evals, see
[CONTRIBUTING.md](CONTRIBUTING.md); the full runbook with every procedure is
[docs/24-runbook.md](docs/24-runbook.md).

ReBo needs no cloud service except the model API you choose (or none, with LM Studio). It never
writes to the database it reports on.

## Where things live

| Path | Contents |
|------|----------|
| `rebo.yaml` | The whole configuration, about 20 values: database, models, limits, who is admin or owner. Never what the data means. |
| `.env` | Secrets only: model API keys, `REBO_DATABASE_URL` in production, login-proxy settings. Never committed. |
| `data/state.db` (or Postgres via `state_url`) | ReBo's memory: catalog, learned knowledge with its history, feedback, conversations, requests, jobs, schedules. |
| `web/dist/` | The built web app, served at `/`. Built into the Docker image. |

## Starting

| How | Command | Open |
|-----|---------|------|
| Local | `uv run rebo serve` | http://127.0.0.1:8080 |
| Production | `docker compose -f compose.prod.yml up -d` | http://localhost:4180 (login first) |

In production only the login proxy (oauth2-proxy) is published. The bot, its Postgres + pgvector
store and Phoenix stay on the internal network; Phoenix is bound to `127.0.0.1:6006`. Roles come
from the identity provider's groups (`reportsbot-admins`, `reportsbot-owners`).

## First run

1. Point `database:` in `rebo.yaml` (or `REBO_DATABASE_URL`) at a **read-only** user.
2. `rebo bootstrap --describe`: reads structure, statistics and values, drafts table descriptions.
3. `rebo config check`, then ask one question you know the answer to.
4. Confirm the first good answers. That is how ReBo starts learning.

## When the reported database changes

Run `rebo bootstrap` again. Saved knowledge that touches changed tables becomes **stale** and stops
being used until it is re-checked; renamed columns usually come back by themselves. Admins see the
rest on the Review page.

## Backups

Only ReBo's state needs a backup; the reported database is never written.

| State | Back up | Restore |
|-------|---------|---------|
| SQLite | `sqlite3 data/state.db ".backup data/state-$(date +%F).db"` (safe while running) | stop, copy over `data/state.db`, start |
| Postgres | `pg_dump -Fc -d "$STATE_URL" > state-$(date +%F).dump` | stop, `pg_restore --clean --if-exists -d "$STATE_URL" …`, start |

A readable copy of what was learned: `rebo knowledge export knowledge-$(date +%F).yaml`.

## Updating

Back up, pull or rebuild (`docker compose -f compose.prod.yml build bot`), start. The state store is
migrated in place at start-up (Alembic); there is no downgrade, so to go back restore the backup and
the old version together.

## Watching it

- **Insights** (admins and owners): health checks, accuracy over measured runs, confirmation rate,
  cost, most asked and most rejected.
- **Phoenix** (http://127.0.0.1:6006): one trace per question with every model call and query, and
  people's feedback attached. Prompts and rows are left out unless `REBO_TRACE_CONTENT=true`.
- `GET /api/health` for the container health check.

## Running without a model API

Point `models:` at LM Studio (`lmstudio:<model>`) and embeddings at a local model. Saved reports,
repeat questions and schedules never call a model in any setup.
