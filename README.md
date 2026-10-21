# reportsbot

A self-contained, self-learning natural-language reports bot for any SQL database.

- **No domain config.** It learns the database by reading it (structure, statistics, stored
  values, joins), and learns the business from people in the chat.
- **Learns safely.** A confirmed report or a taught definition tunes the bot *for that person* at
  once. It reaches everyone only after independent agreement and a curator's approval.
- **Read-only by construction.** SELECT-only DB user, read-only session, timeout, and a sqlglot
  syntax-tree guard that validates every table and column and blocks protected data.
- **Honest answers.** Every report shows where it came from (verified / yours / built from saved
  knowledge / new) and how the question was read, in plain words.

JMS is the first test database (`fixtures/jms_staging/`). Nothing in `src/` is JMS-specific.

Read **AGENTS.md** first (direction and rules). Roles: users ask and teach for themselves, admins manage
learned knowledge, owners manage the ~10–20 line configuration (docs/22).

## Quick start

```bash
uv sync --all-extras
docker compose up -d db                                  # MySQL 8.0.44 with the JMS staging structure
uv run --extra synth python tools/synth/synth.py         # synthetic rows (≈88k, ≈5 min)
cp reportsbot.example.yaml reportsbot.yaml               # the whole config (~10 values)
cp .env.example .env                                     # API keys only
uv run reportsbot bootstrap --describe                   # learn the database
uv run reportsbot serve                                  # http://127.0.0.1:8080/?user=alice
uv run pytest                                            # offline tests (no network, no LLM)
```

Curator view: `http://127.0.0.1:8080/review?user=cora&role=curator`.

## Layout

```
src/reportsbot/      the bot (settings, store, target, safety, catalog, retrieval, knowledge,
                     agent, service, messages, api, ui, mcp_server, evals, observability, cli)
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
