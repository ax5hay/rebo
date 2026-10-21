# 11 · Evals and observability

## 1. Eval runner (`evals.py`, pydantic-evals 2.58)

```bash
uv run reportsbot eval fixtures/jms_staging/eval.jsonl          # all cases
uv run reportsbot eval fixtures/jms_staging/eval.jsonl --limit 3
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

Each case runs as user `eval` through the real `App.ask`, so retrieval, knowledge visibility,
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
on demo gold gp-02/03/04/05/06. Offline test with a FunctionModel; no results file yet (needs an
LLM key):

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

## 4. Tracing (`observability.py`)

Off by default. To turn it on:

```bash
uv sync --extra otel
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:6006   # e.g. Arize Phoenix: `uvx arize-phoenix serve`
export OTEL_SERVICE_NAME=reportsbot
# optional: include prompts/results in spans (contains business data)
export REPORTSBOT_TRACE_CONTENT=true
```

`setup_tracing()` (called once from `App.__init__`) installs an OTLP/HTTP exporter and calls
`Agent.instrument_all(InstrumentationSettings(include_content=…))`. You get one span per agent
run, per model request (tokens, cost, model) and per tool call (arguments, duration), using the
OpenTelemetry GenAI conventions. Phoenix (Elastic-2.0, one container) is the lightest self-hosted
viewer. Langfuse works too but needs Postgres, ClickHouse, Redis and S3 to self-host.

Content is excluded from traces by default because prompts and tool results contain the target
database's data.

### Tracing on by default in the compose files (B-035)

Both `docker-compose.yml` (profile `bot`) and `compose.prod.yml` run Phoenix 20.23.0 and give the bot
`OTEL_EXPORTER_OTLP_ENDPOINT=http://phoenix:6006` plus `openinference.project.name=reportsbot`; the
image installs the `otel` extra. Content stays out of spans unless `REPORTSBOT_TRACE_CONTENT=true`.
Verified 2026-10-21: one scripted turn (tests/web_server.py model) exported to a Phoenix 20.23.0
container showed the spans `invoke_agent reportsbot` (AGENT) and the model call (LLM) through
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
| `stale` items | near zero | run `reportsbot revalidate` after migrations; fix and re-confirm |
| Median tool calls per report | ≤ 8 | the schema search is missing tables; add descriptions (`--describe`) |
