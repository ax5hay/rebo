# ReBo

**ReBo** is a self-contained, self-learning reports bot for any SQL database: ask in plain words,
get one read-only query, the rows, and how your question was read. It learns from the people who
use it, not from configuration.

- **No domain config.** It learns the database by reading it (structure, statistics, stored
  values, joins), and learns the business from people in the chat.
- **Learns safely.** A confirmed report or a taught definition tunes the bot *for that person* at
  once. It reaches everyone only after independent agreement and a curator's approval.
- **Read-only by construction.** SELECT-only DB user, read-only session, timeout, and a sqlglot
  syntax-tree guard that validates every table and column and blocks protected data.
- **Honest answers.** Every report shows where it came from (verified / yours / built from saved
  knowledge / new) and how the question was read, in plain words.

JMS is the first test database (`fixtures/jms_staging/`). Nothing in `src/` is JMS-specific.

Read **AGENTS.md** first (direction and rules), then **CONTRIBUTING.md** (checks, evals, commit rules). Roles: users ask and teach for themselves, admins manage
learned knowledge, owners manage the configuration of about 20 values (docs/22).

## Continue on another machine

Unzip the bundle (`tools/export_bundle.py`), open the folder in your AI coder and say **continue**.
`AGENTS.md` §0 tells it to run `tools/doctor.py` and work through `BACKLOG.md` in small commits,
keeping `HANDOFF.md` up to date. Add API keys to `.env` to unlock LLM measurements.

## Quick start

```bash
uv sync --all-extras                                     # Python 3.13, everything incl. tracing
cp rebo.example.yaml rebo.yaml                           # the whole config (about 20 values)
cp .env.example .env                                     # API keys only (OpenRouter is enough)
(cd web && npm ci && npm run build)                      # the product UI
docker compose --profile bot up -d phoenix               # traces (optional, picked up automatically)
uv run rebo bootstrap --describe                         # learn the database
uv run rebo serve                                        # http://127.0.0.1:8080 (pick who you are at the top)
```

No database at hand? The made-up demo: `uv run python fixtures/demo_property/build.py`, then prefix
the last two commands with `REBO_CONFIG=fixtures/demo_property/rebo.yaml`. The JMS-shaped local
database: `docker compose up -d db && uv run --extra synth python tools/synth/synth.py`.

Tests: `uv run pytest` (offline), `cd web && npx playwright test` (UI), and with
`docker compose up -d state-db` plus `REBO_TEST_STATE_URL=postgresql://rebo:rebo@127.0.0.1:5433/rebo`
the suite runs on Postgres + pgvector too.

![ReBo answering a question](docs/screenshots/02-answer.png)

## What is inside

| Part | What it is |
|---|---|
| Product UI | `web/`: Ask, What I taught, Review, Admin, Insights, Configuration (React 19, react-aria) |
| Observability | Phoenix traces (one trace per question, every model call and query), people's feedback and eval verdicts on the traces, Insights page with live health checks, accuracy history, cost |
| Retrieval | SQLite FTS5 or Postgres full text + vectors (in-process, or pgvector on Postgres), RRF |
| Models | Claude via OpenRouter or Anthropic, Gemini, OpenAI, LM Studio (local); rate limits waited out |
| State | SQLite file or Postgres (+ pgvector), Alembic migrations |
| Production | `compose.prod.yml`: bot, Postgres, oauth2-proxy login, Phoenix; `deploy/auth/` for Pocket ID |

## Layout

```
src/rebo/            the bot (settings, store, target, safety, catalog, retrieval, knowledge,
                     agent, service, jobs, messages, api, ui, mcp_server, evals, observability, cli)
web/                 the product UI (React); served at / when built
tests/               offline tests on a SQLite "shop" database
tools/snapshot/      capture any MySQL database's structure + statistics (no rows)
tools/synth/         fill a structure-only MySQL database with synthetic rows
tools/localdb/       read-only DB user for the local test database
fixtures/jms_staging/ JMS staging snapshot, 18 PO-validated eval prompts, measured eval results
docs/                design and operations documentation (start at docs/README.md)
```

Models: Claude (OpenRouter or Anthropic), Gemini, LM Studio (offline) or OpenAI: see docs/20.
JMS integration without JMS: `mocks/jms/` + `adapters: [jms]`: see docs/18 §4.
A second, made-up domain: `fixtures/demo_property/` (docs/23 §4). Shipping it: `tools/export_bundle.py` (docs/23).

## Documentation

See [docs/README.md](docs/README.md).
