# 13 · Operations

## 1. Configuration (environment only)

| Variable | Default | Kind | Meaning |
|---|---|---|---|
| `REPORTSBOT_DATABASE_URL` | — (required) | wiring | SQLAlchemy URL of the database to report on. **Use a read-only user.** |
| `REPORTSBOT_OPENROUTER_API_KEY` | empty | wiring | Needed for chat and `bootstrap --describe` |
| `REPORTSBOT_MODEL` | `anthropic/claude-sonnet-5.5` | wiring | Agent model (any OpenRouter model with tool calling) |
| `REPORTSBOT_FAST_MODEL` | `anthropic/claude-haiku-5.5` | wiring | Description drafting |
| `REPORTSBOT_STATE_DIR` | `data` | wiring | Where `state.db` lives |
| `REPORTSBOT_ROW_LIMIT` | 500 | limit | Rows returned per report |
| `REPORTSBOT_PROBE_ROW_LIMIT` | 20 | limit | Rows per exploratory query |
| `REPORTSBOT_QUERY_TIMEOUT_S` | 30 | limit | Per-statement timeout in the DB |
| `REPORTSBOT_ALLOW_TABLES` | empty (all) | limit | Comma-separated table allowlist |
| `REPORTSBOT_DENY_COLUMNS` | empty | limit | Regex on `table.column` to protect, on top of auto-detection |
| `REPORTSBOT_MAX_TOOL_CALLS` | 25 | limit | Per user turn |
| `REPORTSBOT_SHARE_THRESHOLD` | 3 | learning | Distinct confirmers before auto-propose |
| `REPORTSBOT_EMBEDDINGS` | true | feature | Use fastembed if installed |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | feature | Turn on tracing (doc 11) |
| `REPORTSBOT_TRACE_CONTENT` | false | feature | Include prompts/results in traces |

Read from the process environment or `.env` in the working directory (`settings.py`). The only
setting with business meaning (`DENY_COLUMNS`) is a safety control, not domain knowledge.

## 2. CLI

| Command | Does |
|---|---|
| `reportsbot bootstrap [--describe]` | Introspect, profile, index, infer joins, optionally draft descriptions, then re-check knowledge. Safe to re-run. |
| `reportsbot serve [--host --port --no-ui]` | FastAPI + NiceGUI on one port (default 127.0.0.1:8080) |
| `reportsbot ask "question" [--user --role]` | One turn from the terminal, JSON output (first 20 rows) |
| `reportsbot revalidate` | Re-check saved knowledge against the current catalog |
| `reportsbot eval FILE.jsonl [--limit N]` | pydantic-evals run (doc 11) |
| `reportsbot mcp` | MCP server over stdio (needs `--extra mcp`) |

## 3. Set up on a new PC (from the zip)

```bash
# prerequisites: Docker Desktop, uv (https://docs.astral.sh/uv/), Git (optional)
unzip reports-bot.zip && cd reports-bot
git init && git add -A && git commit -m "reports bot"      # optional: make it its own repo
uv sync --all-extras                                        # Python 3.13 is fetched by uv if missing
docker compose up -d db                                     # MySQL 8.0.44 with the JMS staging structure
uv run --extra synth python tools/synth/synth.py            # ~88k synthetic rows (≈5 min)
cp .env.example .env                                        # then fill REPORTSBOT_OPENROUTER_API_KEY
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
- Moving to Postgres later: the schema in `store.SCHEMA` is plain SQL apart from FTS5. Replace
  FTS5 with `tsvector` and the BLOB vectors with pgvector (doc 15).

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
