# 13 · Operations

## 1. Configuration: `reportsbot.yaml` + secrets in the environment

The whole configuration is one small YAML file (template `reportsbot.example.yaml`; path from
`REPORTSBOT_CONFIG`, default `./reportsbot.yaml`). Unknown keys are errors. Precedence:
`REPORTSBOT_*` environment variables > YAML > defaults.

| YAML key | Env override | Default | Meaning |
|---|---|---|---|
| `database` | `REPORTSBOT_DATABASE_URL` | required | SQLAlchemy URL; **read-only user** |
| `models.agent` | `REPORTSBOT_MODEL` | `openrouter:anthropic/claude-sonnet-5.5` | new questions (doc 20) |
| `models.fast` | `REPORTSBOT_FAST_MODEL` | `openrouter:anthropic/claude-haiku-5.5` | reuse turns, descriptions |
| `models.escalate` | `REPORTSBOT_ESCALATE_MODEL` | empty | one retry of failed turns |
| `models.fallback` | `REPORTSBOT_FALLBACK_MODELS` (JSON list) | `[]` | API-outage fallbacks |
| `lmstudio_url` | `REPORTSBOT_LMSTUDIO_URL` | `http://127.0.0.1:1234/v1` | offline inference |
| `state_dir` | `REPORTSBOT_STATE_DIR` | `data` | where `state.db` lives |
| `limits.rows` / `probe_rows` / `query_timeout_s` / `tool_calls` | `REPORTSBOT_ROW_LIMIT` / `…PROBE_ROW_LIMIT` / `…QUERY_TIMEOUT_S` / `…MAX_TOOL_CALLS` | 500 / 20 / 30 / 25 | safety and cost ceilings |
| `allowed_tables` | `REPORTSBOT_ALLOW_TABLES` (comma list) | all | allowlist |
| `protected_columns` | `REPORTSBOT_DENY_COLUMNS` | empty | regex on `table.column`, added to auto-detected secrets |
| `sharing.threshold` | `REPORTSBOT_SHARE_THRESHOLD` | 3 | distinct people before auto-propose |
| `embeddings` | `REPORTSBOT_EMBEDDINGS` | true | local vectors |
| `auth.mode` / `auth.issuer` | `REPORTSBOT_AUTH_MODE` / `REPORTSBOT_JWT_ISSUER` | `headers` / `orchid` | identity source (doc 10) |
| `adapters` | `REPORTSBOT_ADAPTERS` (JSON list) | `[]` | host contracts, e.g. `[jms]` |

Secrets (environment or `.env` only): `OPENROUTER_API_KEY` (or `REPORTSBOT_OPENROUTER_API_KEY`),
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY`, `OPENAI_API_KEY`, `REPORTSBOT_JWT_SECRET`.
Tracing: `OTEL_EXPORTER_OTLP_ENDPOINT`, `REPORTSBOT_TRACE_CONTENT` (doc 11).
The only setting with business meaning (`protected_columns`) is a safety control, not domain knowledge.

## 2. CLI

| Command | Does |
|---|---|
| `reportsbot bootstrap [--describe]` | Introspect, profile, index, infer joins, optionally draft descriptions, then re-check knowledge. Safe to re-run. |
| `reportsbot serve [--host --port --no-ui]` | FastAPI + NiceGUI on one port (default 127.0.0.1:8080) |
| `reportsbot ask "question" [--user --role]` | One turn from the terminal, JSON output (first 20 rows) |
| `reportsbot revalidate` | Re-check saved knowledge against the current catalog |
| `reportsbot eval FILE.jsonl [--limit N]` | pydantic-evals run (doc 11) |
| `reportsbot mcp` | MCP server over stdio (needs `--extra mcp`) |
| `reportsbot knowledge export [file] [--all]` / `reportsbot knowledge import file [--as name]` | Everything learned as editable YAML, and back (acts as an owner) |
| `reportsbot config check` | Validate `reportsbot.yaml` |
| `python tools/export_bundle.py [--with-models \| --check-only]` | The checked zip for another machine (doc 23) |

## 3. Set up on a new PC (from the zip)

```bash
# prerequisites: Docker Desktop, uv (https://docs.astral.sh/uv/), Git (optional)
unzip reports-bot.zip && cd reports-bot
git init && git add -A && git commit -m "reports bot"      # optional: make it its own repo
uv sync --all-extras                                        # Python 3.13 is fetched by uv if missing
docker compose up -d db                                     # MySQL 8.0.44 with the JMS staging structure
uv run --extra synth python tools/synth/synth.py            # ~88k synthetic rows (≈5 min)
cp reportsbot.example.yaml reportsbot.yaml                 # ~10 values
cp .env.example .env                                        # API keys
uv run reportsbot bootstrap --describe                      # ≈4 min (≈1.5 min without --describe)
uv run reportsbot serve                                     # open http://127.0.0.1:8080/?user=alice
uv run pytest                                               # offline tests, no network needed
```

Nothing outside `reports-bot/` is needed. Refreshing the snapshot from staging is the only step that
needs AWS access and the VPN (doc 12 §1).

## 4. Backups and state

- `state.db` is the bot's memory. Back it up with SQLite's online backup:
  `sqlite3 data/state.db ".backup data/state-$(date +%F).db"` (safe while running, WAL mode).
- The catalog part can be rebuilt (`bootstrap`). Knowledge, events and suggestions cannot.
- **Postgres instead of the file** (B-026): `uv sync --extra postgres`, then set
  `state_url: postgresql://user:pw@host:5432/db` (or `REPORTSBOT_STATE_URL`). The schema is created
  at start-up; any Postgres 13+ works, no extensions. Locally: `docker compose up -d state-db`
  (postgres:18.6 on port 5433, user/password/db `reportsbot`). Back it up with `pg_dump`. There is no
  copy tool from an existing `state.db` yet: knowledge can move with `reportsbot knowledge export`
  / `import` (admin), conversations do not.
- Tests on both backends: `REPORTSBOT_TEST_STATE_URL=postgresql://reportsbot:reportsbot@127.0.0.1:5433/reportsbot uv run pytest`
  runs every test that uses the `app` fixture a second time on Postgres, each in its own schema.

## 5. Deployment

- `Dockerfile` (python:3.13-slim + uv, `--extra embed`), `docker compose --profile bot up`. State
  goes in the `botstate` volume.
- **One bot process per target database.** For JMS's per-agency databases, run one instance per
  agency (or per agency DB URL), each with its own `state.db`. Knowledge is then naturally
  tenant-isolated: one agency's teaching can never reach another.
- Scaling: the process is I/O-bound on the LLM. One instance serves dozens of concurrent users.
  SQLite WAL handles the write rate of feedback easily.
- Schedule: `bootstrap` nightly (or after migrations), and `revalidate` after every deploy of the
  target application.

## 6. Security checklist

- [ ] The DB user has only `SELECT` (tools/localdb/02-readonly-user.sql is the template).
- [ ] `/api` is reachable only through the host's authenticated proxy, which sets the `X-User-*` headers.
- [ ] `REPORTSBOT_DENY_COLUMNS` covers anything the auto-detection may miss for this customer.
- [ ] The OpenRouter key is in a secret store, not in `.env` in production.
- [ ] Turn retention is configured (doc 09).
- [ ] Tracing content is off (`REPORTSBOT_TRACE_CONTENT` unset) unless the trace store is approved for business data.
