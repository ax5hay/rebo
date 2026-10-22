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

## The image, and running on AWS

The `Dockerfile` is built for fast rebuilds and fast, offline-capable starts (measured 2026-10-22 on
an M-series Mac, Docker 28):

| | Before | Now |
|---|---|---|
| Rebuild after a source change | 16 s, every dependency reinstalled | **7 s**; only the source layer (about 2.5 MB) changes |
| What a deploy pushes to the registry after a code change | the 380 MB dependency layer again | about 2.5 MB |
| Embedding model | downloaded by every new container at start-up (0.13 GB) | **baked in**: a container starts and searches with no network |
| Runtime | root, with uv and build caches | non-root user `rebo`, no build tools, health check on `/api/health` |
| Cold build, no cache | 23 s | 48 s (includes the model download, once per lock change) |
| Image size | 781 MB | 1.13 GB (+134 MB model, +120 MB precompiled bytecode for faster starts) |

Checked: with `--network none` the container bootstraps a database, searches with vectors and turns
healthy. On AWS:

- **Compute:** ECS Fargate (or App Runner) running the image; one task is enough to start, add tasks
  behind the load balancer for more people. The health check is built in.
- **The bot's memory:** `state_url` pointing at RDS PostgreSQL with the `vector` extension
  (pgvector), so every task shares learned knowledge, conversations and vectors. Without it, mount
  `/data` on EFS (single task only).
- **The reported database:** a read-only login in `database:`, reachable from the task's subnet;
  optionally `database_role: "{user}"` for row-level security (docs/07 §3b).
- **Secrets:** model API keys and `REBO_JWT_SECRET` from Secrets Manager as environment variables;
  never in `rebo.yaml`.
- **Bootstrap:** run `rebo bootstrap` as a one-off task after deploys that change the database
  schema. Re-bootstrap embeds only changed schema text (Orbitra, 221 tables: 13.1 s first, 3.1 s
  unchanged).
- **CI image builds:** use BuildKit with a registry cache (`--cache-from/--cache-to type=registry`) so
  CodeBuild or GitHub Actions reuse the dependency and model layers between builds.

## A public demo

For a demo anyone can open (no company login), three settings keep it safe and its bill bounded:

```yaml
limits:
  daily_budget_usd: 2          # model spend for the whole site per UTC day; after that only free routes answer
  per_visitor_per_minute: 4    # by client address (Cloudflare's CF-Connecting-IP): new names do not get around it
auth:
  max_role: admin              # nobody can sign in as owner, so the configuration cannot be changed
```

Saved reports, re-runs, drill-downs and the Read as switches keep working past the budget (no model).
The welcome screen hides roles above `max_role`; the server enforces it too. Example:
`fixtures/orbitra/rebo.public.yaml`.
