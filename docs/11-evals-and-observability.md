# 11 · Evals and observability

## 1. Eval runner (`evals.py`, pydantic-evals 2.58)

```bash
uv run rebo eval fixtures/jms_staging/eval.jsonl          # all cases
uv run rebo eval fixtures/jms_staging/eval.jsonl --limit 3
```

**Case format** (JSONL, one per line; only `id` and `question` are required):

```json
{"id": "validated-01", "question": "Show me all active surrogates in Screening and list their current substage.",
 "gold_sql": "optional reference SELECT", "min_rows": 1, "max_rows": null,
 "tables": ["optional", "tables", "that must appear"], "hint_tables": ["informational only"]}
```

**Evaluators** (each case gets all of them):

| Evaluator | Passes when |
|---|---|
| `IsReport` | the turn ended in a `report` (not clarify/answer/error) |
| `RowsInRange` | row count is within `min_rows`..`max_rows` (missing bounds = open) |
| `UsesTables` | every table in `tables` appears in the SQL (`tables_in` via sqlglot) |
| `ExecutionMatch` | with `gold_sql`: same multiset of rows, ignoring column order and names (BIRD-style execution accuracy) |

Each run asks as a new person (`eval-<8 hex>`, so the per-person answer cache cannot replay an earlier
run) through the real `App.ask`, so retrieval, knowledge visibility,
guard and validator are all exercised. Output is pydantic-evals' table plus JSON
`{cases: [{id, kind, rows, scores, seconds}], failures}`.

**Clarify is not automatically a failure.** For prompts like "cases assigned to [admin name]",
asking is correct. Read `kind` alongside the scores.

### 1.1 Multi-turn eval (`run_conversations`, `tools/eval_conversations.py`; B-011)

Single questions miss what people actually do: ask vaguely, answer a clarification, click a
follow-up chip, rephrase. `fixtures/*/conversations.jsonl` holds scripted conversations:

```json
{"id": "dc-01", "gold_sql": "the report the person is after",
 "turns": [{"say": "Show me the tenants"}, {"pick": 0}, {"say": "Only tenants with a lease right now, ..."}]}
```

`pick` chooses option *i* of every clarifying question (sent the way the UI sends it); `follow_up`
clicks chip *i* under the last report; a step that does not fit the previous turn is skipped and
recorded. Each conversation stops at the first report whose rows match `gold_sql`
(`columns_match`). Per conversation: `turns_to_first_correct` (null = never), asked turns, clarify
turns, cost. Summary: solved, mean turns to the first correct report, clarify rate (clarify turns /
asked turns), total cost. `fixtures/demo_property/conversations.jsonl` has 5 conversations built
on demo gold gp-02/03/04/05/06. Measured 2026-10-21b with Sonnet
(`fixtures/demo_property/eval_conversations_sonnet.json`): 4 of 5 solved, all at turn 2, clarify rate
0.1, $0.19; dc-05 (late payers in 2026) never matched gold. Command:

```bash
uv run python tools/eval_conversations.py fixtures/demo_property/conversations.jsonl \
    fixtures/demo_property/eval_conversations_sonnet.json
```

Prices for the cost estimate live in `llm.PRICES` (shared with `tools/eval_run.py` and the usage dashboard).

## 2. The eval set grows from use

`evals.export_confirmed(app, path)` writes every **verified** example as a case with its SQL as
`gold_sql`. This is Snowflake's verified-query evaluation pattern: run it after a model upgrade,
prompt change or schema migration, and any drop in `ExecutionMatch` is a regression. Personal
(unverified) items are not exported, because one person's confirmation is not ground truth.

## 3. Offline tests (`uv run pytest`, no network, no LLM)

| File | Covers |
|---|---|
| `tests/test_safety.py` | guard rejections, hints, protected columns via `*`, LIMIT, CTE/UNION, literal safety, canonical hash |
| `tests/test_catalog.py` | profiling, value lists, secret detection, FK join paths, value search, schema search ranking, read-only session |
| `tests/test_learning.py` | every trust transition: personal visibility, reinforcement, auto-propose at 3 (including differently written SQL with identical rows, and not for different rows), curator-only promotion, flag → quarantine, owner retire + undo, term replace, conflict with shared term (and that the shared one wins in retrieval), learned joins per owner, stale → repaired |

They run against a 3-table SQLite "shop" database built in `tests/conftest.py`, which also shows
the bot is not tied to MySQL.

## 4. Observability (`observability.py`): traces, verdicts and insights

**On by default.** With `OTEL_EXPORTER_OTLP_ENDPOINT` set, spans go there (any OTLP backend). Without
it, the bot probes Phoenix on `127.0.0.1:6006` at start-up and traces there when it answers
(`docker compose --profile bot up -d phoenix`); `REBO_TRACING=off` disables. The OpenTelemetry SDK
is part of the core install.

**What a trace holds.** Each question is one `rebo.ask` span (user, model, kind). Under it: the
agent run, every model request (tokens, cost, model), every tool call (`search_schema`,
`describe_table`, `run_sql`, …), the second-opinion review, and the HTTP request it came in on.
The trace id is kept on the turn (`usage.trace_id`); admins open it from the answer ("Open trace",
`GET /api/trace/{id}`; the browser link uses `PHOENIX_URL`). Prompts and rows stay out of spans
unless `REBO_TRACE_CONTENT=true`, because they contain the reported database's data.

**Verdicts on traces.** `annotate_trace` posts to Phoenix's `/v1/trace_annotations`: a person's "Yes,
this is right" / "No, fix it" (with their words) becomes a HUMAN "user feedback" annotation and undo
changes it to "withdrawn"; `tools/eval_run.py` adds a CODE "gold match" (match / miss) to every eval
question's trace. In Phoenix you can filter traces by those verdicts.

**Insights page (`/app/insights`, `GET /api/insights`).** For admins and owners: live, timed health
checks (reported database, state store and schema revision, catalog, search index with a dense-search
probe, model keys, LM Studio when used, tracing, background jobs, stale knowledge), headline figures,
accuracy over time from recorded eval runs (`eval_run` table; `tools/record_eval_results.py` imports
older results files), weekly confirmations, provenance, most asked, most reported wrong, cost per
day. Each answer's details stay in Phoenix; the page links there.

**Why Phoenix** (re-checked 2026-10-21): one container with SQLite, OpenTelemetry-native, traces +
annotations + datasets/experiments; ELv2 permits self-hosting (not offering it as a service).
Langfuse v3 needs Postgres, ClickHouse, Redis and S3; Opik also needs a multi-service stack.

Verified live 2026-10-21 (demo DB, Sonnet via OpenRouter, Phoenix 20.23.0): one question = one trace
of 13 spans (cost $0.04, 15.8 s); the answer's "Open trace" link opened it; confirming the answer
put `{label: correct, score: 1.0, explanation}` on the trace; Insights showed nine green checks.

### Tracing on by default in the compose files (B-035)

Both `docker-compose.yml` (profile `bot`) and `compose.prod.yml` run Phoenix 20.23.0 and give the bot
`OTEL_EXPORTER_OTLP_ENDPOINT=http://phoenix:6006` plus `openinference.project.name=rebo`; the
image installs the `otel` extra. Content stays out of spans unless `REBO_TRACE_CONTENT=true`.
Verified 2026-10-21: one scripted turn (tests/web_server.py model) exported to a Phoenix 20.23.0
container showed the spans `invoke_agent rebo` (AGENT) and the model call (LLM) through
Phoenix's REST API (`/v1/projects/default/spans`, run without the project attribute). A trace from the
containerised bot with a real model was not produced (no LLM key).

## 5. Always-on lightweight telemetry

- Every turn stores `usage` (`requests`, `input_tokens`, `output_tokens`, `tool_calls`) and the
  `trace` of tool names, arguments and hit counts in `turn` (doc 09).
- Useful queries:
  ```sql
  -- confirmation rate per week
  SELECT strftime('%Y-%W', created_at,'unixepoch') wk, AVG(feedback='correct'), COUNT(*) FROM turn WHERE kind='report' GROUP BY wk;
  -- answers served from shared knowledge
  SELECT json_extract(provenance,'$.label') label, COUNT(*) FROM turn WHERE kind='report' GROUP BY label;
  ```

## 6. What to watch in production

| Signal | Healthy | Action when not |
|---|---|---|
| Share of reports with `feedback='wrong'` | falling over time | read the traces of the failing questions; teach terms; check value matches |
| Share of `verified`/`yours` badges | rising | curators are not reviewing the queue |
| `stale` items | near zero | run `rebo revalidate` after migrations; fix and re-confirm |
| Median tool calls per report | ≤ 8 | the schema search is missing tables; add descriptions (`--describe`) |
