# 13 · Operations

## 1. Configuration: `rebo.yaml` + secrets in the environment

The whole configuration is one small YAML file (template `rebo.example.yaml`; path from
`REBO_CONFIG`, default `./rebo.yaml`). Unknown keys are errors. Precedence:
`REBO_*` environment variables > YAML > defaults.

| YAML key | Env override | Default | Meaning |
|---|---|---|---|
| `database` | `REBO_DATABASE_URL` | required | SQLAlchemy URL; **read-only user** |
| `models.agent` | `REBO_MODEL` | `openrouter:anthropic/claude-sonnet-5.5` | new questions (doc 20) |
| `models.fast` | `REBO_FAST_MODEL` | `openrouter:anthropic/claude-haiku-5.5` | reuse turns, descriptions |
| `models.escalate` | `REBO_ESCALATE_MODEL` | empty | one retry of failed turns |
| `models.fallback` | `REBO_FALLBACK_MODELS` (JSON list) | `[]` | API-outage fallbacks |
| `lmstudio_url` | `REBO_LMSTUDIO_URL` | `http://127.0.0.1:1234/v1` | offline inference |
| `state_dir` | `REBO_STATE_DIR` | `data` | where `state.db` lives |
| `limits.rows` / `probe_rows` / `query_timeout_s` / `tool_calls` | `REBO_ROW_LIMIT` / `…PROBE_ROW_LIMIT` / `…QUERY_TIMEOUT_S` / `…MAX_TOOL_CALLS` | 500 / 20 / 30 / 25 | safety and cost ceilings |
| `allowed_tables` | `REBO_ALLOW_TABLES` (comma list) | all | allowlist |
| `protected_columns` | `REBO_DENY_COLUMNS` | empty | regex on `table.column`, added to auto-detected secrets |
| `sharing.threshold` | `REBO_SHARE_THRESHOLD` | 3 | distinct people before auto-propose |
| `embeddings` | `REBO_EMBEDDINGS` | true | local vectors |
| `auth.mode` / `auth.issuer` | `REBO_AUTH_MODE` / `REBO_JWT_ISSUER` | `headers` / `orchid` | identity source (doc 10) |
| `adapters` | `REBO_ADAPTERS` (JSON list) | `[]` | host contracts, e.g. `[jms]` |

Secrets (environment or `.env` only): `OPENROUTER_API_KEY` (or `REBO_OPENROUTER_API_KEY`),
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY`, `OPENAI_API_KEY`, `REBO_JWT_SECRET`.
Tracing: `OTEL_EXPORTER_OTLP_ENDPOINT`, `REBO_TRACE_CONTENT` (doc 11).
The only setting with business meaning (`protected_columns`) is a safety control, not domain knowledge.

## 2. CLI

| Command | Does |
|---|---|
| `rebo bootstrap [--describe]` | Introspect, profile, index, infer joins, optionally draft descriptions, then re-check knowledge. Safe to re-run. |
| `rebo serve [--host --port --no-ui]` | FastAPI + NiceGUI on one port (default 127.0.0.1:8080) |
| `rebo ask "question" [--user --role]` | One turn from the terminal, JSON output (first 20 rows) |
| `rebo revalidate` | Re-check saved knowledge against the current catalog |
| `rebo eval FILE.jsonl [--limit N]` | pydantic-evals run (doc 11) |
| `rebo mcp` | MCP server over stdio (needs `--extra mcp`) |
| `rebo knowledge export [file] [--all]` / `rebo knowledge import file [--as name]` | Everything learned as editable YAML, and back (acts as an owner) |
| `rebo config check` | Validate `rebo.yaml` |
| `python tools/export_bundle.py [--with-models \| --check-only]` | The checked zip for another machine (doc 23) |

## 3. Set up on a new PC (from the zip)

```bash
# prerequisites: Docker Desktop, uv (https://docs.astral.sh/uv/), Git (optional)
unzip rebo.zip && cd rebo
git init && git add -A && git commit -m "reports bot"      # optional: make it its own repo
uv sync --all-extras                                        # Python 3.13 is fetched by uv if missing
docker compose up -d db                                     # MySQL 8.0.44 with the JMS staging structure
uv run --extra synth python tools/synth/synth.py            # ~88k synthetic rows (≈5 min)
cp rebo.example.yaml rebo.yaml                 # ~10 values
cp .env.example .env                                        # API keys
uv run rebo bootstrap --describe                      # ≈4 min (≈1.5 min without --describe)
uv run rebo serve                                     # open http://127.0.0.1:8080/?user=alice
uv run pytest                                               # offline tests, no network needed
```

Nothing outside `rebo/` is needed. Refreshing the snapshot from staging is the only step that
needs AWS access and the VPN (doc 12 §1).

## 4. Backups and state

- `state.db` is the bot's memory. Back it up with SQLite's online backup:
  `sqlite3 data/state.db ".backup data/state-$(date +%F).db"` (safe while running, WAL mode).
- The catalog part can be rebuilt (`bootstrap`). Knowledge, events and suggestions cannot.
- **Postgres instead of the file** (B-026): `uv sync --extra postgres`, then set
  `state_url: postgresql://user:pw@host:5432/db` (or `REBO_STATE_URL`). The schema is created
  at start-up; any Postgres 13+ works, no extensions. Locally: `docker compose up -d state-db`
  (postgres:18.6 on port 5433, user/password/db `rebo`). Back it up with `pg_dump`. There is no
  copy tool from an existing `state.db` yet: knowledge can move with `rebo knowledge export`
  / `import` (admin), conversations do not.
- Tests on both backends: `REBO_TEST_STATE_URL=postgresql://rebo:rebo@127.0.0.1:5433/rebo uv run pytest`
  runs every test that uses the `app` fixture a second time on Postgres, each in its own schema.

## 5. Deployment

- `Dockerfile` (python:3.13-slim + uv 0.13, `--extra embed --extra postgres`). Local trial:
  `docker compose --profile bot up` (state in the `botstate` volume).
- **Production stack: `compose.prod.yml`** (B-033). Services: `bot` (not published), `state-db`
  (postgres:18.6, the bot's memory via `state_url`), `auth` (oauth2-proxy v7.15.5, the only
  published port, 4180), `phoenix` (arizephoenix/phoenix 20.23.0 on 127.0.0.1:6006; traces are wired
  in B-035), and `tei` under `--profile tei` (amd64 image). Health checks on bot, Postgres and the
  proxy; named volumes for each. Fill `.env` (LLM key, `REBO_DATABASE_URL`, `OAUTH2_PROXY_*`,
  `STATE_DB_PASSWORD`; `REBO_ENV_FILE` points elsewhere), then
  `docker compose -f compose.prod.yml up -d`. Behind the proxy the bot takes the user from
  `X-Forwarded-Email` / `X-Forwarded-User` when `X-User-Id` is absent (everyone is a `user` until
  B-036 maps groups to roles). Verified on 2026-10-21 (arm64, Docker Desktop) with throw-away
  OAuth values: `config` valid, all four services healthy, the proxy answers 403 without a login,
  the bot is unreachable from the host, the state DB is at Alembic 0004, Phoenix answers on 6006.
  A real sign-in was not tested (needs an identity provider).
- **One bot process per target database.** For JMS's per-agency databases, run one instance per
  agency (or per agency DB URL), each with its own `state.db`. Knowledge is then naturally
  tenant-isolated: one agency's teaching can never reach another.
- Scaling: the process is I/O-bound on the LLM. One instance serves dozens of concurrent users.
  SQLite WAL handles the write rate of feedback easily.
- Schedule: `bootstrap` nightly (or after migrations), and `revalidate` after every deploy of the
  target application.

### 5.1 Login for standalone installs (B-036)

See `deploy/auth/README.md`. oauth2-proxy signs people in with any OIDC provider; with none,
`deploy/auth/compose.pocket-id.yml` adds Pocket ID (passkeys). Roles come from IdP groups
`rebo-owners` / `rebo-admins` (fixed names; everyone else is a user). Behind the proxy the
bot ignores client-sent `X-User-*` headers (verified against oauth2-proxy v7.15.5 that it strips
forged `X-Forwarded-*` but passes `X-User-*` through). Keep the bot reachable only via the proxy.

## 6. Security checklist

- [ ] The DB user has only `SELECT` (tools/localdb/02-readonly-user.sql is the template).
- [ ] `/api` is reachable only through the host's authenticated proxy, which sets the `X-User-*` headers.
- [ ] `REBO_DENY_COLUMNS` covers anything the auto-detection may miss for this customer.
- [ ] The OpenRouter key is in a secret store, not in `.env` in production.
- [ ] Turn retention is configured (doc 09).
- [ ] Tracing content is off (`REBO_TRACE_CONTENT` unset) unless the trace store is approved for business data.

## 7. Background jobs and schedules (`jobs.py`, B-030)

`rebo serve` runs a worker next to the server (`create_app(with_worker=True)`). It queues due
schedules and runs jobs from the `job` table, one at a time:

- `ask`: a question answered in the background (`POST /api/jobs`, or the JMS adapter with
  `reports.async: true`).
- `scheduled`: a saved report re-run with today's data, no model call.

A worker takes a job with a 5-minute lease. If the process stops, the lease runs out and the next
worker (after a restart) runs the job again from the start; failures retry 3 times with back-off,
then the job is `failed` with its error. Results go to `notify_url` as `report_ready` (with a
host-formatted `response` when an adapter registered one, e.g. the JMS ChatResponse). Run one
server per state store: the lease prevents double runs, but a second worker is not tested.
DBOS (3.3.0, MIT) was considered and not adopted; the reasons are in the `jobs.py` docstring.
