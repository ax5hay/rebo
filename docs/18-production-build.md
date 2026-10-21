# 18 · Continuing to a production build (separate repo, small commits)

This is the plan to take `reports-bot/` from the working slim build to a product: a separate,
self-contained repository, no JMS RDS, JMS APIs mocked, configured by ~10 values, accurate, cheap
and asking as few questions as possible. Every step is a **small commit** with its own test and
doc change, so every behaviour change is traceable in `git log`.

## 0. Ground rules for every commit

The direction and the non-negotiables are in `AGENTS.md`. Tools and models named in this plan are
**suggestions**: research them again before adopting (`AGENTS.md` §4).


| Rule | Why |
|---|---|
| One behaviour change per commit; tests and docs for that change in the same commit | `git log -p <file>` explains every line; reverts are surgical |
| Commit message: `type(scope): what` + a body saying *why* and how it was measured | Conventional Commits; the body is the changelog |
| `uv run pytest` green before committing (offline, no network) | The suite runs on a SQLite fixture and mocked LLM/JMS, so it is fast and deterministic |
| Behaviour that changes answers: run `tools/eval_run.py` and commit the results file | Accuracy and cost are tracked like code |
| No domain words in `src/` (CI check, commit P0.4) | Keeps the product generic; JMS lives in fixtures, mocks and adapters only |
| Secrets never in files; config only in `reportsbot.yaml` | One place to look; nothing leaks into git |

Type prefixes: `feat` (behaviour), `fix`, `perf` (cost/latency), `eval` (eval sets/results), `docs`,
`test`, `build` (packaging/CI), `chore`.

## 1. Create the separate repository (commit P0.1)

```bash
# from this repo: export the folder with its history (every commit on feat/reports-bot-standalone)
git subtree split --prefix=reports-bot -b reports-bot-export
mkdir ../reportsbot && cd ../reportsbot && git init -b main
git pull ../orchid-ai-intake-bot reports-bot-export
# or, without history: copy the folder (excluding .venv/ data/ .env reportsbot.yaml) and `git init`
uv sync --all-extras && uv run pytest
```

The folder needs nothing from the parent repo. JMS appears only as:

| Path | Role | Needs JMS? |
|---|---|---|
| `fixtures/jms_staging/` | structure snapshot (no rows), stats profile, 18 eval prompts, measured results | No (static files) |
| `docker-compose.yml` `db` service | MySQL 8.0.44 loaded with that structure | No |
| `tools/synth/` | synthetic rows | No |
| `mocks/jms/server.py` | mock JMS host: token, admin directory, custom-report save + Builder-grammar check, re-run | No |
| `src/reportsbot/adapters/jms.py` | optional: speaks the JMS chat contract (`adapters: [jms]`) | No (tested against the mock) |
| `tools/snapshot/` | refresh the snapshot from a real MySQL | Only when refreshing (aws-vault + VPN) |

## 2. The configuration contract (≈10 values, final)

`reportsbot.yaml` (template: `reportsbot.example.yaml`; loader: `settings.py`, unknown keys are errors):

| # | Key | Example | What it controls |
|---|---|---|---|
| 1 | `database` | `postgresql+psycopg://ro@db/sales` | the database to report on (read-only user) |
| 2 | `models.agent` / `models.fast` / `models.escalate` / `models.fallback` | `openrouter:anthropic/claude-sonnet-5.5` … | who answers new questions / reuse turns and descriptions / failed turns / API outages |
| 3 | `lmstudio_url` | `http://127.0.0.1:1234/v1` | offline inference endpoint |
| 4 | `state_dir` | `data` | the bot's memory |
| 5 | `limits` (rows, probe_rows, query_timeout_s, tool_calls) | `500, 20, 30, 25` | safety and cost ceilings |
| 6 | `allowed_tables` | `[]` | optional allowlist |
| 7 | `protected_columns` | `"(salary\|dob)"` | extra columns to hide (secrets are auto-detected) |
| 8 | `sharing.threshold` | `3` | people agreeing before something is proposed to everyone |
| 9 | `embeddings` | `true` | local vectors on/off |
| 10 | `auth` (mode, issuer) + `adapters` | `jwt`, `orchid`, `[jms]` | identity source and host contracts |

Secrets: `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY`, `REPORTSBOT_JWT_SECRET`.
**Nothing about the meaning of the data is configured.** Adding a semantic YAML is out of scope by
design: meaning is learned (doc 05).

Production commits may add at most these keys (each in its own commit, with a default that keeps
behaviour unchanged): `state_url` (Postgres instead of SQLite, P2.1), `embeddings_url` (TEI, P2.3),
`tracing_url` (P3.2). The total stays ≤ 13.

## 3. Where the build stands (done, on branch `feat/reports-bot-standalone`)

| Commit | What |
|---|---|
| `b5704ed1` | slim bot: catalog bootstrap, agent loop, guard, knowledge lifecycle, API/UI/MCP, evals, snapshot, synth, docs 01–17 |
| `6ac74b63` | single `reportsbot.yaml` (~10 keys), secrets in env |
| `bba41e4f` | model registry: OpenRouter, Anthropic, Gemini, LM Studio, OpenAI, FallbackModel |
| `eeb9ba64` | one-turn clarifications (≤ 3 questions) + drill-down follow-ups |
| `908a47dc` | JWT auth, JMS chat-contract adapter, mock JMS host |
| `f8672333` | no JMS table names in model-facing text |
| `c0f10b3e` | cost cascade: failed turns re-run on `models.escalate` |
| `0bd04df1` | knowledge-aware routing (reuse → fast model) + eval cost reporting |
| `f29f5a78` | docs 18–21 |
| `e71e15b6`, `9c498508` | captured from JMS while reachable: 79 human-built reports (gold SQL), the chat contract (schemas, JWT, WS, Builder rules) |
| `047e3f09` | roles user / admin / owner |
| `e0d24266` | admins add/edit learned knowledge; history and undo; in-place migrations |
| `0185c8fc` | undo feedback, feedback in full words, fix/access requests |
| `cd5c1dfb` | owner config editing (audit, rollback); knowledge export/import; CLI |
| `445219b3` | UI for roles and aids; CSV; starter questions |
| `01258676`, `a7335fde`, `c4633ac0` | made-up Greenleaf demo domain + gold; content-not-presentation metric; JMS gold labelled |
| `2edaeb5c` | export_bundle: the checked zip that leaves this machine |

79 offline tests. Live measurements in doc 20 §5, doc 17 and doc 23 §4. Direction and rules: `AGENTS.md`.

## 4. JMS without JMS: what is mocked and how it maps

| Real JMS behaviour | Mock / adapter | Test |
|---|---|---|
| JMS signs HS256 JWT (`iss=orchid`, `bot_type=reports`, `user_id`, `tenant_id`, `db_schema`, …) | `POST /mock/token` | `test_jms_adapter.py` |
| Widget calls `POST /api/v1/chat/{id}` with `reports.action` (query/freetext/select_option/confirm/reject/new_report) | `adapters/jms.py` | `test_jms_chat_contract_report_confirm_and_remember` |
| Response fields `sql, columns, rows, row_count, truncated, reports_phase, reports_session_id, reports_awaiting, reports_options, reports_allow_freetext, reports_freetext_prompt` | `adapters.jms.to_jms` | same |
| Reports admin picker lists admins | `GET /mock/admins` (from the local DB) | manual |
| `admin_reports_chat.report_action` saves `custom_report.report_query` | `POST /mock/custom-reports` | `test_mock_builder_grammar` |
| Builder re-translates on open; untranslatable = view-only | `builder_grammar_problem()` (staging grammar: flat SELECT, plain columns, INNER/LEFT joins, AND-ed simple filters, `lower(col) LIKE` only) | 8 cases |
| Live re-run of a saved report | `GET /mock/custom-reports/{id}/run` | manual |
| Per-agency databases (`db_schema`) | one bot instance per database (doc 13 §5); the claim is carried, not used for routing | — |
| SQS job + API Gateway WebSocket push for long runs | not mocked yet (P2.5) | — |

Run the whole JMS-shaped stack locally:

```bash
docker compose up -d db
export REPORTSBOT_JWT_SECRET=$(python -c "import secrets;print(secrets.token_hex(32))")
uv run python mocks/jms/server.py &                               # :8090
# reportsbot.yaml: auth: {mode: jwt, issuer: orchid}, adapters: [jms]
uv run reportsbot serve --no-ui &                                  # :8080
TOKEN=$(curl -s -X POST localhost:8090/mock/token -H 'content-type: application/json' -d '{"user_id": 7}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s -X POST localhost:8080/api/v1/chat/0 -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
     -d '{"message":"active surrogates in screening","reports":{"action":"query"}}'
```

## 5. The plan: phases and commits

Each line is one commit. "Gate" is the measurable condition to merge the phase.

### Phase P0: separate repo hygiene (½ day)
- **P0.1** `build: initial import from orchid-ai-intake-bot reports-bot/` (section 1)
- **P0.2** `build: GitHub Actions: uv sync --frozen, pytest, ruff (F,E9,B)`
- **P0.3** `build: pre-commit with ruff + a 'no secrets' check (detect-secrets)`
- **P0.4** `test: forbid domain words in src/ (a test that greps src/ for fixture table names from fixtures/*/profile.json)`
- **P0.5** `docs: CONTRIBUTING with the commit rules of section 0`
- *Gate:* CI green on a fresh clone with no network except PyPI.

### Phase P1: accuracy and fewest turns (the product core, 1–2 weeks)
- **P1.1** `eval: JMS gold questions`: a PO writes one real question for each of the 79 captured reports (`fixtures/jms_staging/gold_custom_reports.jsonl`: 67 are only `Show me <title>` today) and confirms the 18 validated prompts in the UI (`evals.export_confirmed`). Execution match (`evals.columns_match`) and the runner already exist; the demo domain already scores 7/10 (doc 23 §4)
- **P1.2** `feat(agent): deterministic ask-gate` (CIGAsk: prompting alone over- or under-asks). When the model returns `Clarify`, run the top option of each question as SQL; if all readings return the same rows, answer instead of asking and state the assumption. Measure clarify rate vs execution match.
- **P1.3** `feat(knowledge): remember clarification answers per user` (a `note` like "for me, 'active' = not archived") so the same question is never asked twice
- **P1.4** `feat(agent): low-confidence second opinion`: when provenance is `new` and assumptions > 2, a fast-model reviewer gets question + SQL + 10 rows → `ok | concern`; concerns shown as assumptions (about +6 points in Anthropic's data-team report; only on these turns)
- **P1.5** `feat(knowledge): parameterised examples`: sqlglot extracts literals of confirmed SQL into named parameters; a reuse turn becomes "fill parameters → run" with **no LLM call** when the question differs only in literals (Genie trusted-asset pattern)
- **P1.6** `feat(retrieval): question masking for example retrieval` (DAIL-SQL: mask schema/value words)
- **P1.7** `feat(agent): grain check`: if the result has more rows than distinct values of the requested entity key, warn "one row per X" (catches the fan-out seen with Haiku on validated-01)
- **P1.8** `perf(llm): stable cacheable prefix`: instructions + table list ≥ 4,096 tokens and byte-identical across turns, so the Gemini implicit cache and the Claude 1h cache both hit (`anthropic_cache_instructions='1h'`)
- **P1.9** `eval: multi-turn eval`: scripted conversations (clarify → answer → drill-down) scored on turns-to-correct-answer
- **P1.10** `feat(llm): per-model profiles`: thinking level (`low` for Gemini 3.x), tool budget, parallel tool calls and output mode (ToolOutput, or PromptedOutput for weak local models), chosen by model family in `llm.py`. Re-measure Gemini 3.8 Flash (10/18 errors as-is, doc 20 §5) and an LM Studio model
- *Gate:* execution match ≥ 85% on the confirmed set; ≤ 1 clarification per question on average; median cost per question ≤ $0.03 with the cascade.

- **P1.11–P1.20** `feat(aids): …` one commit per user aid in doc 22 §3, in this order: remember clarification answers (= P1.3), re-run with today's data, favourites, "what do you know about X", explain this number, personal defaults, see-as-user (admin), import diff preview (admin), bulk review (admin), config change preview (owner)

### Phase P2: production plumbing (1–2 weeks)
- **P2.1** `feat(store): Postgres state backend` (`state_url`): Postgres 18 + pgvector 0.8.7 + pg_textsearch 1.5.1 (BM25, PostgreSQL licence) with RRF in SQL; SQLite stays the default (doc 19 §3)
- **P2.2** `build: alembic migrations for the state schema` (one migration per later schema change)
- **P2.3** `feat(retrieval): optional TEI embeddings service` (`embeddings_url`) with Qwen3-Embedding-0.6B (CPU) or 4B (GPU); fastembed default switched to EmbeddingGemma-300m or Qwen3-0.6B after an eval
- **P2.4** `feat(api): streaming` with Pydantic AI's AG-UI adapter (`/api/agui`): live tool progress, faster first byte
- **P2.5** `feat(jobs): durable long runs` with DBOS (library, SQLite/Postgres) for scheduled reports and slow queries; mock for JMS's SQS + WebSocket push in `mocks/jms`
- **P2.6** `feat(api): exact answer cache` keyed by normalised question + knowledge version + user scope + SQL hash (never a semantic cache for SQL, doc 19 §5)
- **P2.7** `feat(api): rate limits and per-user budgets` (UsageLimits.cost_limit with genai-prices, which already prices Claude 5.5 and Gemini 3.8)
- **P2.8** `build: production compose` (bot, Postgres, TEI, Phoenix, oauth2-proxy; doc 19 §11)
- *Gate:* load test of 20 concurrent users; p95 first token < 3 s with streaming; restart-safe.

### Phase P3: product UI and operations (1–2 weeks)
- **P3.1** `feat(web): assistant-ui (React) front end on AG-UI` (tables, confirm/fix, option chips, follow-up chips, remember cards); NiceGUI remains the admin/curator UI
- **P3.2** `feat(obs): Phoenix tracing by default in compose` (`tracing_url`), plus `openinference-instrumentation-pydantic-ai`
- **P3.3** `feat(admin): curator dashboard` (queue size, stale items, confirmation rate, cost per day)
- **P3.4** `feat(auth): oauth2-proxy + Pocket ID recipe` for standalone installs (no host app)
- **P3.5** `docs: operator runbook` (backup, restore, upgrade, revalidate after migrations)
- *Gate:* a non-developer can install from the README in < 30 minutes.

### Phase P4: JMS go-live track (separate, after P1 gate)
- **P4.1** `feat(adapters/jms): Builder-grammar output profile`: when enabled, the guard rejects SQL outside the staging Builder grammar (same checks as `mocks/jms.builder_grammar_problem`) so saved reports open editable
- **P4.2** `feat(adapters/jms): save-to-Builder` call (mocked in CI; real JMS URL in config)
- **P4.3** `test(adapters/jms): replay of recorded JMS widget sessions` against the adapter
- **P4.4** run the bot read-only against staging (snapshot refreshed) for a pilot; promote verified knowledge from the pilot as the starting memory

## 6. How to know each change helped (the measurement loop)

1. `uv run pytest` (offline, ~10 s).
2. `uv run python tools/eval_run.py fixtures/jms_staging/eval.jsonl fixtures/jms_staging/eval_results_<change>.json`
   with the model setup in env (`REPORTSBOT_MODEL`, `REPORTSBOT_FAST_MODEL`, `REPORTSBOT_ESCALATE_MODEL`).
3. Compare `summary` (reports / clarify / errors / escalated / median seconds / total cost) and, after
   P1.1, execution match against the gold set. Commit the results file with the change.
4. Run-to-run variance is real (doc 20 §5: the same model gave 55 rows one run and 5 the next on one
   prompt), so compare on the confirmed gold set, not on row counts of unconfirmed answers.
